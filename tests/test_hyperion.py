# -*- coding: utf-8 -*-
import io
import json
import os
import sys
import unittest
import urllib.request
from pathlib import Path

ROOT = os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
sys.path.insert(0, os.path.abspath(ROOT))

from ambientwled.capture.hyperion import HyperionClient  # noqa: E402
from ambientwled.capture.ws import decode_server_frames  # noqa: E402
from ambientwled.imageio import encode_png  # noqa: E402
import base64


class _Resp:
    def __init__(self, payload):
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self):
        return self._buf.read()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestHyperion(unittest.TestCase):
    def test_bridge_turns_leddevice_off_and_grabber_on(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode("utf-8"))
            calls.append(body)
            return _Resp({"success": True, "info": {}})

        orig = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            client = HyperionClient("127.0.0.1", 8090, timeout=0.2)
            self.assertTrue(client.ensure_bridge_mode())
        finally:
            urllib.request.urlopen = orig
        states = {
            (body["componentstate"]["component"], body["componentstate"]["state"])
            for body in calls
        }
        self.assertIn(("LEDDEVICE", False), states)
        self.assertIn(("GRABBER", True), states)
        self.assertIn(("BLACKBORDER", False), states)
        self.assertIn(("SMOOTHING", False), states)

    def test_snapshot_png_becomes_bgra(self):
        png = encode_png(bytes((255, 0, 0)) * 4, 2, 2, color_type=2)
        payload = {
            "success": True,
            "info": {"data": base64.b64encode(png).decode("ascii"), "format": "PNG", "width": 2, "height": 2},
        }

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode("utf-8"))
            self.assertEqual(body["command"], "instance-data")
            self.assertEqual(body["subcommand"], "getImageSnapshot")
            self.assertNotIn("amvideocap", json.dumps(body))
            return _Resp(payload)

        orig = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            frame = HyperionClient().get_image_snapshot()
        finally:
            urllib.request.urlopen = orig
        self.assertIsNotNone(frame)
        bgra, width, height = frame
        self.assertEqual((width, height), (2, 2))
        self.assertEqual(bgra[0], 0)  # B
        self.assertEqual(bgra[2], 255)  # R

    def test_sources_do_not_open_grabber_device(self):
        root = Path(ROOT) / "ambientwled" / "capture"
        text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
        self.assertNotIn("amvideocap", text)
        self.assertNotIn("/dev/amvideo", text)

    def test_ws_text_frame_roundtrip_decode(self):
        payload = b'{"ok":true}'
        raw = bytes((0x81, len(payload))) + payload
        frames, rest = decode_server_frames(raw)
        self.assertEqual(rest, b"")
        self.assertEqual(frames, [(0x1, payload)])


if __name__ == "__main__":
    unittest.main()
