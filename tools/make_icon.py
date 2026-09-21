#!/usr/bin/env python3
"""Draw the AmbientWLED icon (TV with a coloured edge glow)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "script.module.ambientwled" / "lib"))

from ambientwled.imageio import encode_png  # noqa: E402


def render(size=256) -> bytes:
    left, top, right, bottom = int(size * 0.20), int(size * 0.16), int(size * 0.80), int(size * 0.78)
    buf = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            r, g, b = 14, 16, 24
            inside = left <= x < right and top <= y < bottom
            if inside:
                r, g, b = 8, 10, 16
                d_left = x - left
                d_right = right - 1 - x
                d_top = y - top
                d_bottom = bottom - 1 - y
                band = min(d_left, d_right, d_top, d_bottom)
                if band < 12:
                    if d_left <= d_right and d_left <= d_top and d_left <= d_bottom:
                        r, g, b = 190, 42, 58
                    elif d_right <= d_top and d_right <= d_bottom:
                        r, g, b = 46, 92, 210
                    elif d_top <= d_bottom:
                        r, g, b = 36, 186, 110
                    else:
                        r, g, b = 214, 150, 42
            else:
                dx = 0 if left <= x < right else (left - x if x < left else x - right + 1)
                dy = 0 if top <= y < bottom else (top - y if y < top else y - bottom + 1)
                dist = (dx * dx + dy * dy) ** 0.5
                if dist < 26:
                    strength = (1.0 - dist / 26.0) * 0.9
                    if x < left:
                        cr, cg, cb = 255, 56, 72
                    elif x >= right:
                        cr, cg, cb = 64, 104, 255
                    elif y < top:
                        cr, cg, cb = 52, 220, 120
                    else:
                        cr, cg, cb = 255, 176, 48
                    r = int(r + (cr - r) * strength)
                    g = int(g + (cg - g) * strength)
                    b = int(b + (cb - b) * strength)
            i = (y * size + x) * 4
            buf[i] = r
            buf[i + 1] = g
            buf[i + 2] = b
            buf[i + 3] = 255
    return encode_png(bytes(buf), size, size, color_type=6)


def main():
    png = render(256)
    targets = [
        ROOT / "script.service.ambientwled" / "resources" / "icon.png",
        ROOT / "script.module.ambientwled" / "resources" / "icon.png",
        ROOT / "plugin.program.ambientwled" / "resources" / "icon.png",
        ROOT / "repository.ambientwled" / "icon.png",
    ]
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)
        print("wrote", path.relative_to(ROOT), len(png))


if __name__ == "__main__":
    main()
