# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
sys.path.insert(0, os.path.abspath(ROOT))

from ambientwled.colors import trivial_mean_rgb  # noqa: E402


class TestColorsStub(unittest.TestCase):
    def test_trivial_mean_rgb(self):
        self.assertEqual(trivial_mean_rgb([]), (0, 0, 0))
        self.assertEqual(trivial_mean_rgb([(10, 20, 30), (30, 40, 50)]), (20, 30, 40))


if __name__ == "__main__":
    unittest.main()
