# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
sys.path.insert(0, os.path.abspath(ROOT))

from ambientwled.calibrate import (  # noqa: E402
    BAR_THICKNESS_FRAC,
    REVOLUTION_S,
    CalibrateClock,
    bar_rect,
    clamp_delay_ms,
    classify_remote_action,
    hotspot_frame,
    perimeter_led_index,
    perimeter_location,
    step_delay_ms,
)

GEO = dict(
    leds_left=47,
    leds_top=85,
    leds_right=47,
    leds_bottom=85,
    start_corner="bottom_left",
    direction="cw",
)


def _brightest(frame):
    best = 0
    level = -1
    for index, pixel in enumerate(frame):
        if pixel[0] > level:
            best = index
            level = pixel[0]
    return best


class TestPerimeterMapping(unittest.TestCase):
    def test_revolution_is_two_to_three_seconds(self):
        self.assertGreaterEqual(REVOLUTION_S, 2.0)
        self.assertLessEqual(REVOLUTION_S, 3.0)

    def test_progress_zero_is_first_led_at_bottom_of_left(self):
        self.assertEqual(perimeter_led_index(0.0, **GEO), 0)
        loc = perimeter_location(0.0, **GEO)
        self.assertEqual(loc["edge"], "left")
        self.assertEqual(loc["led_index"], 0)
        self.assertGreater(loc["along"], 0.9)

    def test_clockwise_walks_left_then_top_then_right(self):
        left = perimeter_location(10 / 264, **GEO)
        top = perimeter_location(47 / 264, **GEO)
        right = perimeter_location((47 + 85) / 264, **GEO)
        bottom = perimeter_location((47 + 85 + 47) / 264, **GEO)
        self.assertEqual(left["edge"], "left")
        self.assertEqual(top["edge"], "top")
        self.assertEqual(top["led_index"], 47)
        self.assertLess(top["along"], 0.02)
        self.assertEqual(right["edge"], "right")
        self.assertEqual(right["led_index"], 47 + 85)
        self.assertLess(right["along"], 0.05)
        self.assertEqual(bottom["edge"], "bottom")
        self.assertGreater(bottom["along"], 0.9)

    def test_end_of_left_edge_is_near_the_top(self):
        loc = perimeter_location(46 / 264, **GEO)
        self.assertEqual(loc["edge"], "left")
        self.assertEqual(loc["led_index"], 46)
        self.assertLess(loc["along"], 0.05)

    def test_counter_clockwise_starts_along_the_bottom(self):
        geo = dict(GEO, direction="ccw")
        loc = perimeter_location(0.0, **geo)
        self.assertEqual(loc["led_index"], 0)
        self.assertEqual(loc["edge"], "bottom")
        self.assertLess(loc["along"], 0.02)
        later = perimeter_location(90 / 264, **geo)
        self.assertEqual(later["edge"], "right")

    def test_top_right_clockwise_starts_at_the_top_of_the_right(self):
        geo = dict(GEO, start_corner="top_right")
        loc = perimeter_location(0.0, **geo)
        self.assertEqual(loc["edge"], "right")
        self.assertEqual(loc["led_index"], 0)
        self.assertLess(loc["along"], 0.05)

    def test_hotspot_center_matches_led_index(self):
        for progress in (0.0, 0.25, 0.5, 0.9, 1.0):
            frame = hotspot_frame(progress, **GEO)
            self.assertEqual(len(frame), 264)
            expected = perimeter_led_index(0.0 if progress == 1.0 else progress, **GEO)
            self.assertEqual(_brightest(frame), expected)
            center = frame[expected]
            self.assertEqual(center, (255, 255, 255))
            self.assertEqual(frame[(expected + 50) % 264], (0, 0, 0))

    def test_bar_thickness_is_two_to_four_percent_of_the_short_edge(self):
        width, height = 1920, 1080
        short = min(width, height)
        for progress in (0.0, 0.2, 0.55, 0.8):
            loc = perimeter_location(progress, **GEO)
            x, y, w, h = bar_rect(loc, width, height)
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + w, width)
            self.assertLessEqual(y + h, height)
            thickness = w if loc["edge"] in ("left", "right") else h
            frac = thickness / float(short)
            self.assertGreaterEqual(frac, 0.02)
            self.assertLessEqual(frac, 0.04)
            self.assertAlmostEqual(frac, BAR_THICKNESS_FRAC, delta=0.005)
            if loc["edge"] == "left":
                self.assertEqual(x, 0)
            elif loc["edge"] == "right":
                self.assertEqual(x + w, width)
            elif loc["edge"] == "top":
                self.assertEqual(y, 0)
            else:
                self.assertEqual(y + h, height)


class TestEntryPoints(unittest.TestCase):
    def test_settings_action_and_wizard_label(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        settings = open(
            os.path.join(root, "script.service.ambientwled", "resources", "settings.xml"),
            encoding="utf-8",
        ).read()
        run_py = open(os.path.join(root, "script.service.ambientwled", "run.py"), encoding="utf-8").read()
        self.assertIn("RunScript(script.service.ambientwled,calibrate_sync)", settings)
        self.assertIn('id="calibrate_sync"', settings)
        self.assertIn('args[0] == "calibrate_sync"', run_py)
        self.assertIn("svc.calibrate_sync()", run_py)


class TestDelayQueue(unittest.TestCase):
    def test_slider_steps(self):
        self.assertEqual(clamp_delay_ms(40), 40)
        self.assertEqual(clamp_delay_ms(45), 40)
        self.assertEqual(clamp_delay_ms(199), 190)
        self.assertEqual(step_delay_ms(40, 1), 50)
        self.assertEqual(step_delay_ms(0, -1), 0)
        self.assertEqual(step_delay_ms(200, 1), 200)
        self.assertEqual(step_delay_ms(200, -1), 190)

    def test_remote_actions(self):
        self.assertEqual(classify_remote_action(1), "decrease")
        self.assertEqual(classify_remote_action(2), "increase")
        for close_id in (7, 9, 10, 13, 92):
            self.assertEqual(classify_remote_action(close_id), "close")
        self.assertEqual(classify_remote_action(3), "ignore")

    def test_zero_delay_sends_the_current_phase(self):
        clock = CalibrateClock(GEO, delay_ms=0, started=0.0, period_s=2.5)
        frame = clock.tick(1.0)
        self.assertIsNotNone(frame)
        self.assertEqual(_brightest(frame), perimeter_led_index(clock.phase(1.0), **GEO))

    def test_delay_releases_the_older_hotspot(self):
        clock = CalibrateClock(GEO, delay_ms=100, started=0.0, period_s=2.5)
        self.assertIsNone(clock.tick(0.0))
        frame = clock.tick(0.1)
        self.assertIsNotNone(frame)
        # The frame captured at t=0 is the one whose delay has elapsed.
        self.assertEqual(_brightest(frame), perimeter_led_index(0.0, **GEO))
        self.assertNotEqual(_brightest(frame), perimeter_led_index(clock.phase(0.1), **GEO))

    def test_lowering_delay_drops_frames_queued_at_the_old_delay(self):
        clock = CalibrateClock(GEO, delay_ms=200, started=0.0, period_s=2.5)
        self.assertIsNone(clock.tick(0.0))
        self.assertEqual(clock.set_delay_ms(0), 0)
        frame = clock.tick(0.05)
        self.assertIsNotNone(frame)
        self.assertEqual(_brightest(frame), perimeter_led_index(clock.phase(0.05), **GEO))
