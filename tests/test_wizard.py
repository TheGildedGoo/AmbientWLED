# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
sys.path.insert(0, os.path.abspath(ROOT))

from ambientwled.wizard import (  # noqa: E402
    STEP_NAMES,
    WizardActions,
    WizardStore,
    WizardUI,
    _step_picture,
    _step_wled,
    run_wizard,
)


class AutoUI(WizardUI):
    def __init__(self):
        self.messages = []

    def ok(self, title, message):
        self.messages.append(message)

    def notify(self, title, message):
        self.messages.append(message)

    def yesno(self, title, message, no, yes):
        return True

    def select(self, title, options):
        for index, label in enumerate(options):
            name = label.lower()
            if name.startswith("next") or name.startswith("enable") or name.startswith("finish"):
                return index
        return 0

    def numeric(self, title, default):
        return int(default)

    def input_text(self, title, default):
        return default or "192.168.1.50"


class TestWizard(unittest.TestCase):
    def test_seven_steps(self):
        self.assertEqual(
            STEP_NAMES,
            ("welcome", "wled", "strip", "geometry", "picture", "behavior", "done"),
        )

    def test_walk_enables_264_layout(self):
        store = WizardStore()
        finished = run_wizard(AutoUI(), store, WizardActions())
        self.assertTrue(finished)
        cfg = store.export()
        self.assertTrue(cfg.enabled)
        self.assertTrue(cfg.configured)
        self.assertTrue(cfg.video_only)
        self.assertTrue(cfg.rgbw)
        self.assertFalse(cfg.white_extract)
        self.assertFalse(cfg.fake_cycle)
        self.assertEqual(cfg.led_count, 264)
        self.assertEqual((cfg.leds_left, cfg.leds_top, cfg.leds_right, cfg.leds_bottom), (47, 85, 47, 85))
        self.assertEqual(cfg.edge_sum(), 264)
        self.assertEqual(cfg.start_corner, "bottom_left")
        self.assertEqual(cfg.direction, "cw")
        self.assertEqual(cfg.edge_depth_pct, 10)
        self.assertEqual(cfg.sync_delay_ms, 40)
        self.assertEqual(cfg.capture_mode, "auto")
        self.assertEqual(cfg.capture_fps, 25)
        self.assertEqual(cfg.capture_long_edge, 96)
        self.assertEqual(cfg.pause_mode, "freeze")
        self.assertEqual(cfg.fail_soft, "off")
        self.assertEqual(cfg.hyperion_host, "127.0.0.1")
        self.assertEqual(cfg.hyperion_port, 8090)
        self.assertEqual(cfg.ddp_port, 4048)

    def test_test_connection_action_is_safe(self):
        class TestUI(AutoUI):
            def __init__(self):
                AutoUI.__init__(self)
                self.calls = 0

            def select(self, title, options):
                self.calls += 1
                if self.calls == 1:
                    return 0  # Test connection
                return 3  # Next

        class Actions(WizardActions):
            def __init__(self):
                self.tested = 0

            def test_connection(self, store, ui):
                self.tested += 1
                ui.ok("AmbientWLED", "stub ok")

        ui = TestUI()
        actions = Actions()
        self.assertEqual(_step_wled(ui, WizardStore(), actions), "next")
        self.assertEqual(actions.tested, 1)
        self.assertIn("stub ok", ui.messages)

    def test_picture_step_launches_calibrate_sync(self):
        class UI(AutoUI):
            def __init__(self):
                AutoUI.__init__(self)
                self.calls = 0
                self.options = []

            def select(self, title, options):
                self.calls += 1
                if self.calls == 1:
                    self.options = list(options)
                    for index, label in enumerate(options):
                        if label.lower().startswith("calibrate"):
                            return index
                for index, label in enumerate(options):
                    if label.lower().startswith("next"):
                        return index
                return -1

        class Actions(WizardActions):
            def __init__(self):
                self.calibrated = 0

            def calibrate_sync(self, store, ui):
                self.calibrated += 1
                store.set("sync_delay_ms", 80)

        store = WizardStore()
        ui = UI()
        actions = Actions()
        self.assertEqual(_step_picture(ui, store, actions), "next")
        self.assertEqual(actions.calibrated, 1)
        self.assertEqual(store.get("sync_delay_ms"), 80)
        self.assertIn("Calibrate sync", ui.options)

    def test_cancel_does_not_enable(self):
        class CancelUI(AutoUI):
            def yesno(self, title, message, no, yes):
                return False

        store = WizardStore()
        self.assertFalse(run_wizard(CancelUI(), store, WizardActions()))
        self.assertFalse(store.export().enabled)


if __name__ == "__main__":
    unittest.main()
