"""Week 1 demo: HSV rainbow / edge chase over DDP — no capture, no xbmc."""

from __future__ import annotations

import math
import time
from typing import Callable, List, Optional, Tuple

from ambientwled.ddp import DdpSender, Pixel

RGB = Tuple[int, int, int]


def hsv_to_rgb(h: float, s: float = 1.0, v: float = 1.0) -> RGB:
    """h in [0,1), s,v in [0,1]. Returns 0–255 RGB."""
    if s <= 0.0:
        x = int(v * 255)
        return (x, x, x)
    i = int(h * 6.0)
    f = h * 6.0 - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i %= 6
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return (int(r * 255), int(g * 255), int(b * 255))


def rainbow_frame(led_count: int, phase: float, brightness: float = 0.4) -> List[RGB]:
    """Full-strip rainbow; ``phase`` shifts hue along the strip."""
    brightness = max(0.0, min(1.0, brightness))
    out: List[RGB] = []
    for i in range(led_count):
        h = (i / max(1, led_count) + phase) % 1.0
        r, g, b = hsv_to_rgb(h, 1.0, brightness)
        out.append((r, g, b))
    return out


def edge_demo_frame(led_count: int, phase: float, brightness: float = 0.5) -> List[RGB]:
    """Four soft color blobs chasing around the strip (stand-in for L/R/T/B)."""
    brightness = max(0.0, min(1.0, brightness))
    # Approximate TV perimeter into 4 edges
    n = max(4, led_count)
    edges = [
        (0.00, (255, 40, 40)),   # left-ish red
        (0.25, (40, 255, 40)),   # top green
        (0.50, (40, 40, 255)),   # right blue
        (0.75, (255, 200, 40)),  # bottom amber
    ]
    pixels: List[RGB] = [(0, 0, 0)] * n
    for base, color in edges:
        center = ((base + phase) % 1.0) * n
        half = max(2, n // 16)
        for i in range(n):
            dist = min(abs(i - center), n - abs(i - center))
            if dist <= half:
                w = (1.0 - dist / half) * brightness
                r0, g0, b0 = pixels[i]
                pixels[i] = (
                    min(255, int(r0 + color[0] * w)),
                    min(255, int(g0 + color[1] * w)),
                    min(255, int(b0 + color[2] * w)),
                )
    return pixels


def run_cycle(
    sender: DdpSender,
    led_count: int,
    *,
    mode: str = "rainbow",
    fps: float = 20.0,
    brightness: float = 0.35,
    duration_s: Optional[float] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> None:
    """Drive DDP frames until duration elapses or ``should_stop`` returns True."""
    led_count = max(1, int(led_count))
    dt = 1.0 / max(1.0, fps)
    t0 = time.monotonic()
    phase = 0.0
    while True:
        if should_stop and should_stop():
            break
        if duration_s is not None and (time.monotonic() - t0) >= duration_s:
            break
        if mode == "edge":
            frame = edge_demo_frame(led_count, phase, brightness)
        else:
            frame = rainbow_frame(led_count, phase, brightness)
        # RGBW: let DdpSender expand W = min(R,G,B) when rgbw=True
        sender.send(frame)  # type: ignore[arg-type]
        phase = (phase + 0.01) % 1.0
        time.sleep(dt)
