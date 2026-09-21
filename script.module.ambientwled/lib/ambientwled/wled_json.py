"""WLED JSON HTTP helpers — stdlib urllib only, no xbmc.

Endpoints used (LAN only, no phone-home):
  GET  /json/info   — discover / version / LED count hint
  GET  /json/state  — current on/brightness/live
  POST /json/state  — set brightness, on/off, live override
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class WledError(Exception):
    """Raised when WLED HTTP/JSON call fails."""


class WledClient:
    """Thin JSON client for a single WLED instance on the LAN."""

    def __init__(self, host: str, timeout: float = 2.0):
        host = (host or "").strip()
        if host.startswith("http://") or host.startswith("https://"):
            self.base = host.rstrip("/")
        else:
            self.base = f"http://{host}".rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base + path

    def _get_json(self, path: str) -> Dict[str, Any]:
        req = urllib.request.Request(
            self._url(path),
            headers={"Accept": "application/json", "User-Agent": "AmbientWLED/0.1"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise WledError(f"HTTP {e.code} GET {path}") from e
        except urllib.error.URLError as e:
            raise WledError(f"unreachable: {e.reason}") from e
        except TimeoutError as e:
            raise WledError("timeout") from e
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise WledError("invalid JSON") from e

    def _post_json(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self._url(path),
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "AmbientWLED/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise WledError(f"HTTP {e.code} POST {path}") from e
        except urllib.error.URLError as e:
            raise WledError(f"unreachable: {e.reason}") from e
        except TimeoutError as e:
            raise WledError("timeout") from e
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def get_info(self) -> Dict[str, Any]:
        """GET /json/info — version, LED count, name, etc."""
        return self._get_json("/json/info")

    def get_state(self) -> Dict[str, Any]:
        """GET /json/state."""
        return self._get_json("/json/state")

    def set_brightness(self, bri: int) -> Dict[str, Any]:
        """Set master brightness 0–255."""
        bri = max(0, min(255, int(bri)))
        return self._post_json("/json/state", {"bri": bri})

    def set_on(self, on: bool = True) -> Dict[str, Any]:
        """Turn LEDs on or off."""
        return self._post_json("/json/state", {"on": bool(on)})

    def set_off(self) -> Dict[str, Any]:
        return self.set_on(False)

    def set_live(self, live: bool = True) -> Dict[str, Any]:
        """Enable/disable WLED realtime (live) override.

        When AmbientWLED streams DDP, set live True so effects do not fight.
        On stop/screensaver, set live False to release override.
        """
        # WLED accepts {"live": true/false} in state; some builds use "lor".
        return self._post_json("/json/state", {"live": bool(live)})

    def test_connection(self) -> Dict[str, Any]:
        """Convenience: fetch /json/info and return a small summary dict."""
        info = self.get_info()
        leds = info.get("leds") or {}
        return {
            "ok": True,
            "name": info.get("name") or info.get("ver") or "WLED",
            "version": info.get("ver"),
            "led_count": leds.get("count"),
            "raw": info,
        }
