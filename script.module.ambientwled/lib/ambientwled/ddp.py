"""DDP (Distributed Display Protocol) UDP sender for WLED.

Primary: DDP on UDP port 4048 (RGB and RGBW).
Stub comment only for DRGB / DRGBW on UDP 21324 (Week 2+ fallback).

DDP header (10 bytes) + pixel data:
  byte 0: flags (version=1 in high nibble, push bit, etc.)
  byte 1: sequence (0 = unused / no sequencing)
  byte 2: data type (1 = RGB, 6? custom — WLED treats length carefully)
  byte 3: destination ID (1 = default)
  bytes 4-7: data offset (big-endian)
  bytes 8-9: data length (big-endian)
  then: pixel bytes

WLED DDP RGB: 3 bytes/LED. RGBW: 4 bytes/LED when strip is RGBW.
We pack explicitly; do not rely on WLED auto-white for RGBW double-compute.
"""

from __future__ import annotations

import socket
from typing import Iterable, List, Sequence, Tuple, Union

DDP_PORT = 4048
# Fallback (not implemented Week 1):
# DRGB / DRGBW realtime protocol typically uses UDP 21324.
# DRGB_PORT = 21324  # stub — Week 2+ if DDP unavailable

PixelRGB = Tuple[int, int, int]
PixelRGBW = Tuple[int, int, int, int]
Pixel = Union[PixelRGB, PixelRGBW]


def _clamp_byte(v: int) -> int:
    return max(0, min(255, int(v)))


# WLED constants (ESPAsyncE131.h): RGB24=0x0B, RGBW32=0x1B. Legacy 0x01 still
# accepted as RGB by many builds; 0x0A is NOT RGBW (wrong TTT/SSS encoding).
DDP_TYPE_RGB24 = 0x0B
DDP_TYPE_RGBW32 = 0x1B


def build_ddp_packet(
    pixels: Sequence[Pixel],
    *,
    rgbw: bool = False,
    offset: int = 0,
    sequence: int = 0,
    push: bool = True,
    offset_is_leds: bool = True,
) -> bytes:
    """Build one DDP datagram for ``pixels``.

    ``offset`` is a LED index by default (converted to DDP byte/channel offset).
    Pass ``offset_is_leds=False`` if you already have a byte offset.
    """
    channels = 4 if rgbw else 3
    payload = bytearray()
    for p in pixels:
        if rgbw:
            if len(p) == 4:
                r, g, b, w = p
            else:
                r, g, b = p[0], p[1], p[2]
                w = min(r, g, b)
            payload.extend(
                (_clamp_byte(r), _clamp_byte(g), _clamp_byte(b), _clamp_byte(w))
            )
        else:
            r, g, b = p[0], p[1], p[2]
            payload.extend((_clamp_byte(r), _clamp_byte(g), _clamp_byte(b)))

    length = len(payload)
    byte_offset = int(offset) * channels if offset_is_leds else int(offset)
    # flags: version 1 (0x40) | push (0x01)
    flags = 0x40 | (0x01 if push else 0x00)
    data_type = DDP_TYPE_RGBW32 if rgbw else DDP_TYPE_RGB24
    dest_id = 1
    # DDP seq is 4-bit (1–15); 0 means unused
    seq = 0 if sequence == 0 else ((sequence - 1) % 15) + 1
    header = bytearray(10)
    header[0] = flags
    header[1] = seq & 0x0F
    header[2] = data_type
    header[3] = dest_id
    header[4] = (byte_offset >> 24) & 0xFF
    header[5] = (byte_offset >> 16) & 0xFF
    header[6] = (byte_offset >> 8) & 0xFF
    header[7] = byte_offset & 0xFF
    header[8] = (length >> 8) & 0xFF
    header[9] = length & 0xFF
    return bytes(header) + bytes(payload)


class DdpSender:
    """Fire-and-forget UDP DDP sender. Non-blocking enough for a worker thread."""

    def __init__(self, host: str, port: int = DDP_PORT, rgbw: bool = False):
        self.host = (host or "").strip()
        self.port = int(port)
        self.rgbw = bool(rgbw)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._seq = 0

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass

    def send(self, pixels: Sequence[Pixel], offset: int = 0, push: bool = True) -> int:
        """Send one DDP frame. Returns bytes sent (best-effort; may be 0 if buffer full)."""
        if not self.host:
            return 0
        self._seq = self._seq + 1
        if self._seq > 15:
            self._seq = 1
        packet = build_ddp_packet(
            pixels,
            rgbw=self.rgbw,
            offset=offset,
            sequence=self._seq,
            push=push,
        )
        try:
            return self._sock.sendto(packet, (self.host, self.port))
        except (BlockingIOError, OSError):
            return 0

    def send_solid(self, color: Pixel, count: int) -> int:
        """Fill ``count`` LEDs with a single color."""
        pixels: List[Pixel] = [color] * max(0, int(count))
        return self.send(pixels)


# --- DRGB / DRGBW stub (UDP 21324) ---
# WLED also accepts the older "DRGB" / "DRGBW" realtime protocols on port 21324:
#   DRGB:  [timeout][R][G][B]...
#   DRGBW: [timeout][R][G][B][W]...
# AmbientWLED Week 1 uses DDP only. Implement DRGB/DRGBW here later if a
# controller or firmware build lacks DDP.
