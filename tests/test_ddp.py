# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
sys.path.insert(0, os.path.abspath(ROOT))

from ambientwled.ddp import build_ddp_packet, DDP_PORT  # noqa: E402


class TestDdp(unittest.TestCase):
    def test_rgb_header_and_payload(self):
        pkt = build_ddp_packet([(10, 20, 30), (1, 2, 3)], rgbw=False)
        self.assertEqual(len(pkt), 10 + 6)
        self.assertEqual(pkt[0] & 0x40, 0x40)  # version nibble
        self.assertEqual(pkt[0] & 0x01, 0x01)  # push
        self.assertEqual(pkt[2], 0x0B)  # DDP_TYPE_RGB24
        self.assertEqual(pkt[8:10], b"\x00\x06")
        self.assertEqual(pkt[10:], bytes([10, 20, 30, 1, 2, 3]))

    def test_rgbw_expands_min(self):
        pkt = build_ddp_packet([(100, 50, 25)], rgbw=True)
        self.assertEqual(len(pkt), 10 + 4)
        self.assertEqual(pkt[2], 0x1B)  # DDP_TYPE_RGBW32
        self.assertEqual(pkt[10:], bytes([100, 50, 25, 25]))  # W = min

    def test_led_offset_becomes_byte_offset(self):
        pkt = build_ddp_packet([(1, 2, 3)], rgbw=False, offset=2)
        # 2 LEDs * 3 channels = byte offset 6
        self.assertEqual(pkt[4:8], b"\x00\x00\x00\x06")

    def test_port_constant(self):
        self.assertEqual(DDP_PORT, 4048)


if __name__ == "__main__":
    unittest.main()
