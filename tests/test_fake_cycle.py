# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
sys.path.insert(0, os.path.abspath(ROOT))

from ambientwled.fake_cycle import hsv_to_rgb, rainbow_frame, edge_demo_frame  # noqa: E402


class TestFakeCycle(unittest.TestCase):
    def test_hsv_red(self):
        self.assertEqual(hsv_to_rgb(0.0, 1.0, 1.0), (255, 0, 0))

    def test_rainbow_length(self):
        f = rainbow_frame(12, 0.0, 0.5)
        self.assertEqual(len(f), 12)
        self.assertTrue(all(0 <= c <= 255 for p in f for c in p))

    def test_edge_length(self):
        f = edge_demo_frame(40, 0.1, 0.5)
        self.assertEqual(len(f), 40)


if __name__ == "__main__":
    unittest.main()
