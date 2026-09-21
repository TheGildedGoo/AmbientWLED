"""DDP (Distributed Display Protocol) UDP sender for WLED.

Primary path: DDP on UDP port 4048.
DRGB / DRGBW on UDP 21324 is not the live sender.

Header (10 bytes) + pixel bytes:
  byte 0: flags — version 1 (0x40) and push (0x01) → 0x41 on the last fragment
  byte 1: sequence (low nibble; 0 = unused)
  byte 2: data type — 0x0B RGB24 or 0x1B RGBW32
  byte 3: destination ID 1
  bytes 4-7: byte offset (big-endian)
  bytes 8-9: payload length in BYTES (big-endian)
  then: R,G,B or R,G,B,W

Payloads larger than 1440 bytes are fragmented. Offset of each fragment is a
byte offset. Only the last fragment sets the push bit.
"""

from __future__ import annotations

import socket
from typing import List, Sequence, Tuple, Union

DDP_PORT = 4048
# WLED rejects DDP payloads above 480*3 bytes. 1440 divides both 3 and 4.
MAX_DDP_PAYLOAD = 1440
DDP_FLAGS_VERSION = 0x40
DDP_FLAGS_PUSH = 0x01
DDP_FLAGS = DDP_FLAGS_VERSION | DDP_FLAGS_PUSH  # 0x41
DDP_TYPE_RGB24 = 0x0B
DDP_TYPE_RGBW32 = 0x1B
DDP_DEST_ID = 1

# DRGB / DRGBW realtime on UDP 21324 is intentionally not implemented.
# DRGB_PORT = 21324

PixelRGB = Tuple[int, int, int]
PixelRGBW = Tuple[int, int, int, int]
Pixel = Union[PixelRGB, PixelRGBW]


def _clamp_byte(v: int) -> int:
    return max(0, min(255, int(v)))


def _pack_pixels(pixels: Sequence[Pixel], rgbw: bool) -> bytes:
    payload = bytearray()
    for p in pixels:
        if rgbw:
            if len(p) >= 4:
                r, g, b, w = p[0], p[1], p[2], p[3]
            else:
                r, g, b = p[0], p[1], p[2]
                w = min(r, g, b)
            payload.extend(
                (_clamp_byte(r), _clamp_byte(g), _clamp_byte(b), _clamp_byte(w))
            )
        else:
            r, g, b = p[0], p[1], p[2]
            payload.extend((_clamp_byte(r), _clamp_byte(g), _clamp_byte(b)))
    return bytes(payload)


def build_ddp_packet(
    pixels: Sequence[Pixel],
    *,
    rgbw: bool = False,
    offset: int = 0,
    sequence: int = 0,
    push: bool = True,
    offset_is_leds: bool = True,
) -> bytes:
    """Build one DDP datagram.

    ``offset`` is a LED index when ``offset_is_leds`` is true (converted to a
    byte offset). Pass ``offset_is_leds=False`` to supply a byte offset.
    A single call does not fragment; use ``build_ddp_packets`` for that.
    """
    channels = 4 if rgbw else 3
    payload = _pack_pixels(pixels, rgbw)
    length = len(payload)
    byte_offset = int(offset) * channels if offset_is_leds else int(offset)
    flags = DDP_FLAGS_VERSION | (DDP_FLAGS_PUSH if push else 0)
    data_type = DDP_TYPE_RGBW32 if rgbw else DDP_TYPE_RGB24
    seq = 0 if sequence == 0 else ((int(sequence) - 1) % 15) + 1
    header = bytearray(10)
    header[0] = flags
    header[1] = seq & 0x0F
    header[2] = data_type
    header[3] = DDP_DEST_ID
    header[4] = (byte_offset >> 24) & 0xFF
    header[5] = (byte_offset >> 16) & 0xFF
    header[6] = (byte_offset >> 8) & 0xFF
    header[7] = byte_offset & 0xFF
    header[8] = (length >> 8) & 0xFF
    header[9] = length & 0xFF
    return bytes(header) + payload


def build_ddp_packets(
    pixels: Sequence[Pixel],
    *,
    rgbw: bool = False,
    offset: int = 0,
    sequence: int = 0,
    push: bool = True,
    offset_is_leds: bool = True,
    max_payload: int = MAX_DDP_PAYLOAD,
) -> List[bytes]:
    """Fragment ``pixels`` so each datagram payload is at most ~1440 bytes."""
    channels = 4 if rgbw else 3
    limit = max(channels, int(max_payload) - (int(max_payload) % channels))
    max_pixels = max(1, limit // channels)
    total = len(pixels)
    if total == 0:
        return [
            build_ddp_packet(
                [],
                rgbw=rgbw,
                offset=offset,
                sequence=sequence,
                push=push,
                offset_is_leds=offset_is_leds,
            )
        ]
    packets: List[bytes] = []
    index = 0
    while index < total:
        chunk = pixels[index : index + max_pixels]
        is_last = (index + len(chunk)) >= total
        if offset_is_leds:
            off = int(offset) + index
            off_leds = True
        else:
            off = int(offset) + index * channels
            off_leds = False
        packets.append(
            build_ddp_packet(
                chunk,
                rgbw=rgbw,
                offset=off,
                sequence=sequence,
                push=bool(push and is_last),
                offset_is_leds=off_leds,
            )
        )
        index += len(chunk)
    return packets


class DdpSender:
    """Fire-and-forget UDP DDP sender for a worker thread."""

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
        """Send one frame, fragmented if needed. Returns bytes handed to UDP."""
        if not self.host:
            return 0
        self._seq = self._seq + 1
        if self._seq > 15:
            self._seq = 1
        packets = build_ddp_packets(
            pixels,
            rgbw=self.rgbw,
            offset=offset,
            sequence=self._seq,
            push=push,
        )
        sent = 0
        for packet in packets:
            try:
                sent += self._sock.sendto(packet, (self.host, self.port))
            except (BlockingIOError, OSError):
                return sent
        return sent

    def send_solid(self, color: Pixel, count: int) -> int:
        pixels: List[Pixel] = [color] * max(0, int(count))
        return self.send(pixels)
