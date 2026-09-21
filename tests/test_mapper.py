# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
sys.path.insert(0, os.path.abspath(ROOT))

from ambientwled.colors.mapper import map_frame  # noqa: E402


def _bgra(width, height, paint):
    buf = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            r, g, b = paint(x, y)
            i = (y * width + x) * 4
            buf[i] = b
            buf[i + 1] = g
            buf[i + 2] = r
            buf[i + 3] = 255
    return bytes(buf)


class TestMapper(unittest.TestCase):
    def _edges(self, width=100, height=80):
        depth_x = 10
        depth_y = 8

        def paint(x, y):
            if x < depth_x:
                return (255, 0, 0)
            if x >= width - depth_x:
                return (0, 0, 255)
            if y < depth_y:
                return (0, 255, 0)
            if y >= height - depth_y:
                return (255, 220, 0)
            return (20, 20, 20)

        return _bgra(width, height, paint)

    def test_default_clockwise_bottom_left(self):
        frame = self._edges()
        colours = map_frame(
            frame,
            100,
            80,
            leds_left=5,
            leds_top=5,
            leds_right=5,
            leds_bottom=5,
            start_corner="bottom_left",
            direction="cw",
            edge_depth_pct=10,
            black_threshold=8,
        )
        self.assertEqual(len(colours), 20)
        self.assertGreater(colours[2][0], 200)  # left middle
        self.assertGreater(colours[7][1], 200)  # top middle
        self.assertGreater(colours[12][2], 200)  # right middle
        self.assertGreater(colours[17][0], 200)  # bottom middle
        self.assertGreater(colours[17][1], 150)

    def test_counter_clockwise_starts_on_bottom(self):
        frame = self._edges()
        colours = map_frame(
            frame,
            100,
            80,
            leds_left=5,
            leds_top=5,
            leds_right=5,
            leds_bottom=5,
            start_corner="bottom_left",
            direction="ccw",
            edge_depth_pct=10,
        )
        # First edge is the bottom, left to right. Middle LED is yellow.
        self.assertGreater(colours[2][0], 200)
        self.assertGreater(colours[2][1], 150)
        self.assertLess(colours[2][2], 40)

    def test_264_is_per_edge_not_32_percent(self):
        width, height = 200, 120

        def paint(x, y):
            if x < 20:
                return (255, 0, 0)
            if y < 12:
                return (0, 255, 0)
            if x >= width - 20:
                return (0, 0, 255)
            if y >= height - 12:
                return (255, 200, 0)
            return (30, 30, 30)

        colours = map_frame(
            _bgra(width, height, paint),
            width,
            height,
            leds_left=47,
            leds_top=85,
            leds_right=47,
            leds_bottom=85,
            start_corner="bottom_left",
            direction="cw",
            edge_depth_pct=10,
        )
        self.assertEqual(len(colours), 264)
        self.assertNotEqual(len(colours[: int(264 * 0.32)]), 47)
        # Middle of the left edge is red. A 32% top-first split would not
        # put 47 left samples at the start of the buffer.
        self.assertGreater(colours[23][0], 200)
        self.assertLess(colours[23][1], 40)
        self.assertGreater(colours[47 + 42][1], 200)

    def test_letterbox_239_samples_picture_not_bars(self):
        width, height = 96, 54
        content_h = int(round(height * (16 / 9) / 2.39))
        bar = (height - content_h) // 2
        top = bar
        bottom = height - bar

        def paint(x, y):
            if y < top or y >= bottom:
                return (0, 0, 0)
            if y < top + 4:
                return (0, 255, 0)
            if y >= bottom - 4:
                return (255, 180, 0)
            if x < 8:
                return (255, 0, 0)
            if x >= width - 8:
                return (0, 0, 255)
            return (80, 80, 80)

        colours = map_frame(
            _bgra(width, height, paint),
            width,
            height,
            leds_left=4,
            leds_top=8,
            leds_right=4,
            leds_bottom=8,
            start_corner="bottom_left",
            direction="cw",
            edge_depth_pct=10,
            black_threshold=8,
        )
        top_mid = colours[4 + 4]
        bottom_mid = colours[4 + 8 + 4 + 4]
        self.assertGreater(top_mid[1], 180)
        self.assertLess(top_mid[0], 40)
        self.assertGreater(bottom_mid[0], 180)
        self.assertGreater(bottom_mid[1], 100)


if __name__ == "__main__":
    unittest.main()
