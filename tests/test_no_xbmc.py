# -*- coding: utf-8 -*-
import unittest
from pathlib import Path


class TestLibraryBoundary(unittest.TestCase):
    def test_shared_library_does_not_import_xbmc(self):
        root = Path(__file__).resolve().parents[1] / "script.module.ambientwled" / "lib"
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("import xbmc", text, str(path))
