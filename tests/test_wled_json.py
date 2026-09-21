# -*- coding: utf-8 -*-
"""Unit tests for WledClient using a fake urllib opener (stdlib only)."""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
import urllib.error
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
sys.path.insert(0, os.path.abspath(ROOT))

from ambientwled.wled_json import WledClient, WledError  # noqa: E402


class _FakeResp:
    def __init__(self, payload, code=200):
        if isinstance(payload, (dict, list)):
            raw = json.dumps(payload).encode("utf-8")
        elif isinstance(payload, bytes):
            raw = payload
        else:
            raw = str(payload).encode("utf-8")
        self._buf = io.BytesIO(raw)
        self.status = code

    def read(self):
        return self._buf.read()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestWledJson(unittest.TestCase):
    def test_get_info_ok(self):
        info = {"name": "TV-bias", "ver": "0.14.0", "leds": {"count": 150}}

        def fake_urlopen(req, timeout=None):
            if req.full_url.endswith("/json/state"):
                return _FakeResp({"on": True, "bri": 90, "live": False})
            self.assertIn("/json/info", req.full_url)
            return _FakeResp(info)

        orig = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            c = WledClient("192.168.1.50")
            got = c.get_info()
            self.assertEqual(got["name"], "TV-bias")
            summary = c.test_connection()
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["led_count"], 150)
            self.assertEqual(summary["bri"], 90)
            self.assertFalse(summary["live"])
        finally:
            urllib.request.urlopen = orig

    def test_base_url_strips_trailing_slash(self):
        c = WledClient("http://wled.local/")
        self.assertEqual(c.base, "http://wled.local")

    def test_set_brightness_clamps(self):
        bodies = []

        def fake_urlopen(req, timeout=None):
            bodies.append(json.loads(req.data.decode("utf-8")))
            return _FakeResp({"success": True})

        orig = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            c = WledClient("10.0.0.1")
            c.set_brightness(999)
            c.set_on(True)
            c.set_off()
            c.set_live(False)
            self.assertEqual(bodies[0]["bri"], 255)
            self.assertTrue(bodies[1]["on"])
            self.assertFalse(bodies[2]["on"])
            self.assertFalse(bodies[3]["live"])
        finally:
            urllib.request.urlopen = orig

    def test_unreachable(self):
        def fake_urlopen(req, timeout=None):
            raise urllib.error.URLError("timed out")

        orig = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            c = WledClient("10.255.255.1", timeout=0.1)
            with self.assertRaises(WledError) as cm:
                c.get_info()
            self.assertIn("unreachable", str(cm.exception))
        finally:
            urllib.request.urlopen = orig

    def test_invalid_json(self):
        def fake_urlopen(req, timeout=None):
            return _FakeResp(b"not-json")

        orig = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            with self.assertRaises(WledError):
                WledClient("h").get_info()
        finally:
            urllib.request.urlopen = orig


if __name__ == "__main__":
    unittest.main()
