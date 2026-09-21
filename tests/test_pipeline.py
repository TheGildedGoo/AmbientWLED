# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
sys.path.insert(0, os.path.abspath(ROOT))

from ambientwled.colors.pipeline import ColorPipeline, pack_rgbw  # noqa: E402


def _neutral(**kwargs):
    base = dict(
        black_threshold=0,
        white_suppression=0,
        saturation=100,
        contrast=100,
        gamma=10,
        brightness=255,
        smoothing=0,
        rgbw=True,
        white_extract=False,
    )
    base.update(kwargs)
    return ColorPipeline(**base)


class TestPipeline(unittest.TestCase):
    def test_identity_rgbw_min_white(self):
        out = _neutral().process([(100, 50, 25)])
        self.assertEqual(out, [(100, 50, 25, 25)])

    def test_white_extract_subtracts(self):
        out = _neutral(white_extract=True).process([(100, 50, 25)])
        self.assertEqual(out, [(75, 25, 0, 25)])

    def test_pack_rgbw_default_keeps_rgb(self):
        self.assertEqual(pack_rgbw(100, 50, 25, False), (100, 50, 25, 25))
        self.assertEqual(pack_rgbw(100, 50, 25, True), (75, 25, 0, 25))

    def test_black_threshold(self):
        out = _neutral(black_threshold=40).process([(10, 10, 10)])
        self.assertEqual(out, [(0, 0, 0, 0)])

    def test_rgb_mode_has_three_channels(self):
        out = _neutral(rgbw=False).process([(10, 20, 30)])
        self.assertEqual(out, [(10, 20, 30)])

    def test_ema_blends_second_frame(self):
        pipe = _neutral(smoothing=50)
        first = pipe.process([(100, 0, 0)])
        second = pipe.process([(0, 0, 0)])
        self.assertEqual(first, [(100, 0, 0, 0)])
        self.assertEqual(second[0][0], 50)

    def test_reset_clears_ema(self):
        pipe = _neutral(smoothing=50)
        pipe.process([(100, 0, 0)])
        pipe.reset()
        again = pipe.process([(0, 0, 0)])
        self.assertEqual(again[0][0], 0)

    def test_brightness_cap(self):
        out = _neutral(brightness=128).process([(200, 0, 0)])
        self.assertLess(out[0][0], 200)
        self.assertGreater(out[0][0], 90)


if __name__ == "__main__":
    unittest.main()
