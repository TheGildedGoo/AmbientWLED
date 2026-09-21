"""Hyperion.ng JSON / WebSocket client for CoreELEC service.hyperion.ng.

Talks to 127.0.0.1:8090. LEDDEVICE is forced off and GRABBER on so Hyperion
owns the grabber and AmbientWLED owns DDP. This module never opens a video
capture device; it only speaks HTTP and WebSocket.
"""

from __future__ import annotations

import base64
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from ambientwled.imageio import png_to_bgra
from ambientwled.latest import LatestSlot
from ambientwled.capture.ws import WsConnection

Frame = Tuple[bytes, int, int]


class HyperionError(Exception):
    pass


class HyperionClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 8090, timeout: float = 1.5) -> None:
        self.host = (host or "127.0.0.1").strip()
        self.port = int(port or 8090)
        self.timeout = timeout
        self.last_error = ""
        self._tan = 1

    def _next_tan(self) -> int:
        self._tan = (self._tan % 100000) + 1
        return self._tan

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = dict(payload)
        body.setdefault("tan", self._next_tan())
        data = json.dumps(body).encode("utf-8")
        url = "http://%s:%s/json-rpc" % (self.host, self.port)
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "AmbientWLED/0.2",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            self.last_error = "HTTP %s" % exc.code
            raise HyperionError(self.last_error) from exc
        except urllib.error.URLError as exc:
            self.last_error = "unreachable: %s" % exc.reason
            raise HyperionError(self.last_error) from exc
        except TimeoutError as exc:
            self.last_error = "timeout"
            raise HyperionError(self.last_error) from exc
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.last_error = "invalid JSON"
            raise HyperionError(self.last_error) from exc
        if not isinstance(parsed, dict):
            self.last_error = "invalid JSON"
            raise HyperionError(self.last_error)
        if parsed.get("success") is False:
            self.last_error = str(parsed.get("error") or "hyperion error")
            raise HyperionError(self.last_error)
        self.last_error = ""
        return parsed

    def server_info(self) -> Dict[str, Any]:
        return self.call({"command": "serverinfo", "subcommand": "getInfo"})

    def set_component(self, name: str, enabled: bool) -> bool:
        try:
            self.call(
                {
                    "command": "componentstate",
                    "componentstate": {"component": name, "state": bool(enabled)},
                }
            )
            return True
        except HyperionError:
            return False

    def ensure_bridge_mode(self) -> bool:
        """LED output off, grabber on. AmbientWLED maps and sends DDP itself."""
        ok = True
        for name, enabled in (
            ("LEDDEVICE", False),
            ("BLACKBORDER", False),
            ("SMOOTHING", False),
            ("GRABBER", True),
        ):
            ok = self.set_component(name, enabled) and ok
        return ok

    def release_grabber(self) -> None:
        self.set_component("GRABBER", False)

    def get_image_snapshot(self) -> Optional[Frame]:
        """HTTP PNG snapshot → BGRA bytes, width, height."""
        try:
            parsed = self.call(
                {
                    "command": "instance-data",
                    "subcommand": "getImageSnapshot",
                    "instance": 0,
                    "format": "PNG",
                }
            )
        except HyperionError:
            return None
        info = parsed.get("info") or {}
        b64 = info.get("data") or info.get("image")
        if isinstance(b64, dict):
            b64 = b64.get("data")
        if not b64 or not isinstance(b64, str):
            self.last_error = "snapshot missing"
            return None
        try:
            raw = base64.b64decode(b64)
        except (ValueError, TypeError):
            self.last_error = "snapshot decode"
            return None
        decoded = png_to_bgra(raw)
        if decoded is None:
            self.last_error = "snapshot png"
            return None
        bgra, width, height = decoded
        return bgra, width, height


class HyperionSource:
    """Prefer a WebSocket image stream; poll HTTP snapshots if it is quiet.

    ``read`` returns the newest frame only (the slot depth is 1).
    """

    def __init__(self, client: HyperionClient, prefer_ws: bool = True) -> None:
        self.client = client
        self._slot: LatestSlot = LatestSlot()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ws: Optional[WsConnection] = None
        self._ws_alive = False
        self._last_ws = 0.0
        if prefer_ws:
            self._start_ws()

    def _start_ws(self) -> None:
        ws = WsConnection(self.client.host, self.client.port, timeout=self.client.timeout, path="/")
        try:
            ws.connect()
            ws.send_text(
                json.dumps({"command": "ledcolors", "subcommand": "imagestream-start", "tan": 20})
            )
        except OSError as exc:
            self.client.last_error = str(exc)
            ws.close()
            return
        self._ws = ws
        self._ws_alive = True
        self._thread = threading.Thread(target=self._reader, name="AmbientWLED-hyperion", daemon=True)
        self._thread.start()

    def _reader(self) -> None:
        ws = self._ws
        if ws is None:
            return
        while not self._stop.is_set():
            try:
                frames = ws.recv_data()
            except OSError:
                self._ws_alive = False
                return
            for opcode, payload in frames:
                if opcode == 0x8:
                    self._ws_alive = False
                    return
                if opcode == 0x9 and self._ws is not None:
                    try:
                        from ambientwled.capture.ws import encode_client_frame

                        if ws._sock is not None:
                            ws._sock.sendall(encode_client_frame(payload, 0xA))
                    except OSError:
                        self._ws_alive = False
                        return
                    continue
                if opcode != 0x1 or not payload:
                    continue
                frame = _frame_from_message(payload)
                if frame is not None:
                    self._last_ws = time.monotonic()
                    self._slot.put(frame)

    def read(self, timeout: float = 0.05) -> Optional[Frame]:
        frame = self._slot.get(timeout)
        if frame is not None:
            self._last_ws = time.monotonic()
            return frame
        if self._ws_alive and self._last_ws and (time.monotonic() - self._last_ws) < 2.0:
            return None
        return self.client.get_image_snapshot()

    def close(self) -> None:
        self._stop.set()
        self._slot.close()
        if self._ws is not None:
            try:
                self._ws.send_text(
                    json.dumps({"command": "ledcolors", "subcommand": "imagestream-stop", "tan": 21})
                )
            except OSError:
                pass
            self._ws.close()
            self._ws = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        try:
            self.client.release_grabber()
        except Exception:
            pass


def _frame_from_message(payload: bytes) -> Optional[Frame]:
    try:
        msg = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(msg, dict):
        return None
    info = msg.get("info") or msg.get("data") or {}
    if isinstance(info, dict) and "image" in info and isinstance(info["image"], dict):
        info = info["image"]
    if not isinstance(info, dict):
        return None
    b64 = info.get("data") or info.get("image")
    if not isinstance(b64, str) or not b64:
        return None
    try:
        raw = base64.b64decode(b64)
    except (ValueError, TypeError):
        return None
    decoded = png_to_bgra(raw)
    if decoded is None:
        return None
    bgra, width, height = decoded
    return bgra, width, height
