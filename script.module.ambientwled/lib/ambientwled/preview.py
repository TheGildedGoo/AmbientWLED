"""Short DDP previews for Test connection and the setup wizard.

These run on the caller thread (a settings action or wizard step), never on
the Kodi render thread. Live override is released when the preview ends.
"""

from __future__ import annotations

import time
from typing import List, Optional, Sequence, Tuple

from ambientwled.colors.mapper import edge_sequence
from ambientwled.ddp import DdpSender
from ambientwled.fake_cycle import rainbow_frame
from ambientwled.wled_json import WledClient, WledError

RGB = Tuple[int, int, int]

EDGE_COLOURS = {
    "left": (255, 48, 48),
    "top": (48, 220, 96),
    "right": (48, 96, 255),
    "bottom": (255, 176, 48),
}


def geometry_chase_frame(
    leds_left: int,
    leds_top: int,
    leds_right: int,
    leds_bottom: int,
    phase: float,
    start_corner: str = "bottom_left",
    direction: str = "cw",
    brightness: float = 0.55,
) -> List[RGB]:
    """One frame: each edge keeps its colour, a bright spot walks LED order."""
    counts = {
        "left": max(0, int(leds_left)),
        "top": max(0, int(leds_top)),
        "right": max(0, int(leds_right)),
        "bottom": max(0, int(leds_bottom)),
    }
    brightness = max(0.05, min(1.0, float(brightness)))
    pixels: List[RGB] = []
    for name, _travel in edge_sequence(start_corner, direction):
        colour = EDGE_COLOURS[name]
        dim = tuple(int(c * brightness * 0.35) for c in colour)
        pixels.extend([dim] * counts[name])  # type: ignore[list-item]
    total = len(pixels)
    if total == 0:
        return []
    center = int((phase % 1.0) * total) % total
    span = max(2, total // 18)
    out: List[RGB] = []
    for i, base in enumerate(pixels):
        dist = min(abs(i - center), total - abs(i - center))
        if dist <= span:
            gain = (1.0 - dist / span) * brightness
            out.append(
                (
                    min(255, int(base[0] + 255 * gain)),
                    min(255, int(base[1] + 255 * gain)),
                    min(255, int(base[2] + 255 * gain)),
                )
            )
        else:
            out.append(base)
    return out


def solid_frame(count: int, colour: RGB = (180, 140, 80)) -> List[RGB]:
    return [colour] * max(0, int(count))


def run_frames(
    host: str,
    frames: Sequence[Sequence[RGB]],
    *,
    port: int = 80,
    ddp_port: int = 4048,
    rgbw: bool = True,
    fps: float = 20.0,
    release_live: bool = True,
) -> Optional[str]:
    """Send ``frames`` over DDP. Returns an error string, or None on success.

    HTTP failure does not block UDP: the chase still goes out, and live
    release is best-effort.
    """
    host = (host or "").strip()
    if not host or not frames:
        return "no host"
    client = WledClient(host, port=port, timeout=2.0)
    sender = DdpSender(host, port=ddp_port, rgbw=rgbw)
    error = None
    try:
        try:
            client.set_live(True)
        except WledError as exc:
            error = str(exc)
        dt = 1.0 / max(1.0, fps)
        for frame in frames:
            sender.send(frame)
            time.sleep(dt)
    finally:
        if release_live:
            try:
                client.set_live(False)
            except WledError:
                pass
        sender.close()
    return error


def chase_frames(count_args: dict, seconds: float = 2.0, fps: float = 20.0) -> List[List[RGB]]:
    frames = []
    steps = max(1, int(seconds * fps))
    for i in range(steps):
        frames.append(geometry_chase_frame(phase=i / steps, **count_args))
    return frames


def rainbow_frames(led_count: int, seconds: float = 2.0, fps: float = 20.0, brightness: float = 0.45):
    frames = []
    steps = max(1, int(seconds * fps))
    for i in range(steps):
        frames.append(rainbow_frame(led_count, i / steps, brightness))
    return frames
