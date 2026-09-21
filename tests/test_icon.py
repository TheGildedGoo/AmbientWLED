# -*- coding: utf-8 -*-
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = [
    ROOT / "script.service.ambientwled" / "resources" / "icon.png",
    ROOT / "script.module.ambientwled" / "resources" / "icon.png",
    ROOT / "plugin.program.ambientwled" / "resources" / "icon.png",
    ROOT / "repository.ambientwled" / "icon.png",
]


def _png_size(path: Path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("not a png: %s" % path)
    width, height = struct.unpack(">II", data[16:24])
    return width, height


class TestIcons(unittest.TestCase):
    def test_icons_are_real_pngs(self):
        for path in ICONS:
            width, height = _png_size(path)
            self.assertGreaterEqual(width, 64, path)
            self.assertGreaterEqual(height, 64, path)
            self.assertGreater(path.stat().st_size, 500, path)
