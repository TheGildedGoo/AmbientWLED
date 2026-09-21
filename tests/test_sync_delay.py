# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
sys.path.insert(0, os.path.abspath(ROOT))

from ambientwled.sync_delay import SyncDelay  # noqa: E402


class TestSyncDelay(unittest.TestCase):
    def test_holds_until_delay(self):
        delay = SyncDelay()
        frame = [(1, 2, 3)]
        delay.push(frame, now=1.0, delay_s=0.04)
        self.assertIsNone(delay.pop_ready(1.03))
        self.assertEqual(delay.pop_ready(1.04), frame)

    def test_depth_one_after_delay_keeps_newest(self):
        delay = SyncDelay()
        a = [(1, 0, 0)]
        b = [(0, 1, 0)]
        c = [(0, 0, 1)]
        delay.push(a, now=0.00, delay_s=0.04)
        delay.push(b, now=0.01, delay_s=0.04)
        delay.push(c, now=0.02, delay_s=0.04)
        self.assertEqual(delay.pop_ready(0.05), b)
        self.assertIsNone(delay.pop_ready(0.05))
        self.assertEqual(delay.pop_ready(0.06), c)

    def test_zero_delay_sends_immediately(self):
        delay = SyncDelay()
        frame = [(9, 9, 9)]
        delay.push(frame, now=5.0, delay_s=0.0)
        self.assertEqual(delay.pop_ready(5.0), frame)


if __name__ == "__main__":
    unittest.main()
