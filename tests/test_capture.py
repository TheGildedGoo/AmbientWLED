# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
sys.path.insert(0, os.path.abspath(ROOT))

from ambientwled.capture.black_detect import BlackDetector  # noqa: E402
from ambientwled.capture.native import capture_size, recommend_fps  # noqa: E402


def _frame(width, height, rgb):
    r, g, b = rgb
    pixel = bytes((b, g, r, 255))
    return pixel * (width * height)


class TestNativeSizing(unittest.TestCase):
    def test_long_edge_96_16_9(self):
        width, height = capture_size(16 / 9, 96)
        self.assertEqual((width, height), (96, 54))
        self.assertEqual(max(width, height), 96)

    def test_fps_drops_when_over_budget(self):
        self.assertEqual(recommend_fps(9.0, 25), 15)
        self.assertEqual(recommend_fps(3.0, 25), 25)
        self.assertEqual(recommend_fps(20.0, 15), 15)


class TestBlackDetector(unittest.TestCase):
    def test_fails_when_three_quarters_black(self):
        det = BlackDetector(frames=12, fail_ratio=0.75)
        for _ in range(9):
            det.add(_frame(16, 16, (0, 0, 0)), 16, 16)
        for _ in range(3):
            det.add(_frame(16, 16, (200, 40, 40)), 16, 16)
        self.assertTrue(det.ready)
        self.assertTrue(det.failed())

    def test_passes_when_picture_is_present(self):
        det = BlackDetector(frames=12, fail_ratio=0.75)
        for _ in range(12):
            det.add(_frame(16, 16, (20, 80, 40)), 16, 16)
        self.assertFalse(det.failed())

    def test_empty_buffer_counts_as_black(self):
        det = BlackDetector(frames=4, fail_ratio=0.75)
        for _ in range(4):
            det.add(b"", 16, 16)
        self.assertTrue(det.failed())


if __name__ == "__main__":
    unittest.main()
