"""Tiny PNG codec (8-bit gray / RGB / RGBA, non-interlaced) plus BGRA helpers.

Stdlib only so CoreELEC does not need Pillow. Hyperion snapshots are PNG.
"""

from __future__ import annotations

import struct
import zlib
from typing import Optional, Tuple

_SIG = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def encode_png(pixels: bytes, width: int, height: int, color_type: int = 6) -> bytes:
    """Encode raw pixels. color_type 2 = RGB, 6 = RGBA, 0 = gray."""
    if color_type == 6:
        bpp = 4
    elif color_type == 2:
        bpp = 3
    elif color_type == 0:
        bpp = 1
    else:
        raise ValueError("unsupported color type")
    width = int(width)
    height = int(height)
    stride = width * bpp
    if len(pixels) < stride * height:
        raise ValueError("pixel buffer too small")
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(pixels[start : start + stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return b"".join(
        (
            _SIG,
            _chunk(b"IHDR", ihdr),
            _chunk(b"IDAT", zlib.compress(bytes(raw), 9)),
            _chunk(b"IEND", b""),
        )
    )


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode_png(data: bytes) -> Tuple[bytes, int, int, int]:
    """Return (raw_pixels, width, height, color_type).

    color_type 2 is RGB, 6 is RGBA, 0 is gray. Raises ValueError on unsupported
    or truncated input.
    """
    if not data or not data.startswith(_SIG):
        raise ValueError("not a png")
    pos = 8
    width = height = color_type = None
    idat = bytearray()
    bit_depth = 8
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        tag = data[pos + 4 : pos + 8]
        pos += 8
        chunk = data[pos : pos + length]
        pos += length + 4  # crc
        if len(chunk) < length:
            raise ValueError("truncated png")
        if tag == b"IHDR":
            (
                width,
                height,
                bit_depth,
                color_type,
                _compression,
                _filter_method,
                interlace,
            ) = struct.unpack(">IIBBBBB", chunk[:13])
            if bit_depth != 8 or interlace != 0:
                raise ValueError("unsupported png")
            if color_type not in (0, 2, 6):
                raise ValueError("unsupported png color")
        elif tag == b"IDAT":
            idat.extend(chunk)
        elif tag == b"IEND":
            break
    if not width or not height or color_type is None or not idat:
        raise ValueError("incomplete png")
    bpp = {0: 1, 2: 3, 6: 4}[color_type]
    stride = width * bpp
    raw = zlib.decompress(bytes(idat))
    expected = (stride + 1) * height
    if len(raw) < expected:
        raise ValueError("png data short")
    out = bytearray(stride * height)
    prev = bytearray(stride)
    src = 0
    for y in range(height):
        filt = raw[src]
        src += 1
        row = bytearray(raw[src : src + stride])
        src += stride
        if filt == 0:
            pass
        elif filt == 1:
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + left) & 0xFF
        elif filt == 2:
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 0xFF
        elif filt == 3:
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((left + prev[i]) // 2)) & 0xFF
        elif filt == 4:
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                up_left = prev[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + _paeth(left, prev[i], up_left)) & 0xFF
        else:
            raise ValueError("bad png filter")
        start = y * stride
        out[start : start + stride] = row
        prev = row
    return bytes(out), int(width), int(height), int(color_type)


def rgb_to_bgra(rgb: bytes, width: int, height: int) -> bytes:
    out = bytearray(width * height * 4)
    o = 0
    for i in range(0, width * height * 3, 3):
        r, g, b = rgb[i], rgb[i + 1], rgb[i + 2]
        out[o] = b
        out[o + 1] = g
        out[o + 2] = r
        out[o + 3] = 255
        o += 4
    return bytes(out)


def rgba_to_bgra(rgba: bytes, width: int, height: int) -> bytes:
    out = bytearray(width * height * 4)
    for i in range(0, width * height * 4, 4):
        r, g, b, a = rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]
        out[i] = b
        out[i + 1] = g
        out[i + 2] = r
        out[i + 3] = a
    return bytes(out)


def png_to_bgra(data: bytes) -> Optional[Tuple[bytes, int, int]]:
    """Decode a PNG into Kodi-style BGRA. Returns None on failure."""
    try:
        pixels, width, height, color_type = decode_png(data)
    except (ValueError, zlib.error, struct.error):
        return None
    if color_type == 6:
        return rgba_to_bgra(pixels, width, height), width, height
    if color_type == 2:
        return rgb_to_bgra(pixels, width, height), width, height
    if color_type == 0:
        rgb = bytearray(width * height * 3)
        for i, g in enumerate(pixels[: width * height]):
            rgb[i * 3 : i * 3 + 3] = bytes((g, g, g))
        return rgb_to_bgra(bytes(rgb), width, height), width, height
    return None
