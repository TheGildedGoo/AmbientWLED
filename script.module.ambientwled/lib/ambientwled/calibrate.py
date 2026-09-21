"""Sync-calibration math: perimeter phase → LED index and on-screen bar.

The white bar on the Kodi screen and the white LED hotspot share one
perimeter phase in ``[0, 1)``. Phase 0 is the strip's start corner. Phase
increases in the strip direction (clockwise from bottom-left by default),
which is the same order as ``edge_sequence``.

The screen uses the phase for *now*. The LED frame is the same hotspot pushed
through ``SyncDelay``, so a wrong ``sync_delay_ms`` makes the strip lead or
lag the bar. No xbmc and no sockets live here.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Sequence, Tuple

from ambientwled.colors.mapper import edge_sequence
from ambientwled.sync_delay import SyncDelay

# One lap. Inside the 2–3 second window Dylan asked for.
REVOLUTION_S = 2.5
# Thickness of the on-screen bar as a fraction of the short screen edge.
BAR_THICKNESS_FRAC = 0.03
# How long the bar is along the edge it is currently on.
BAR_LENGTH_FRAC = 0.08
DELAY_MIN = 0
DELAY_MAX = 200
DELAY_STEP = 10

# Home-window property. The service stands down while this is "1".
CALIBRATE_PROPERTY = "AmbientWLED.Calibrating"

# Kodi action ids. Remote only: Left/Right adjust, OK/Back/Done stop.
ACTION_MOVE_LEFT = 1
ACTION_MOVE_RIGHT = 2
ACTION_SELECT_ITEM = 7
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_STOP = 13
ACTION_NAV_BACK = 92

RGB = Tuple[int, int, int]
Rect = Tuple[int, int, int, int]


def clamp_delay_ms(value: int) -> int:
    """Snap to the settings slider: 0–200, step 10."""
    try:
        delay = int(value)
    except (TypeError, ValueError):
        delay = 0
    delay = max(DELAY_MIN, min(DELAY_MAX, delay))
    return delay - (delay % DELAY_STEP)


def step_delay_ms(value: int, steps: int) -> int:
    """Move by ``steps`` slider clicks (each click is 10 ms)."""
    return clamp_delay_ms(clamp_delay_ms(value) + int(steps) * DELAY_STEP)


def classify_remote_action(action_id: int) -> str:
    """Map a remote action to ``decrease``, ``increase``, ``close``, or ``ignore``."""
    try:
        aid = int(action_id)
    except (TypeError, ValueError):
        return "ignore"
    if aid == ACTION_MOVE_LEFT:
        return "decrease"
    if aid == ACTION_MOVE_RIGHT:
        return "increase"
    if aid in (ACTION_SELECT_ITEM, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_STOP, ACTION_NAV_BACK):
        return "close"
    return "ignore"


def phase_at(now: float, started: float, period_s: float = REVOLUTION_S) -> float:
    """Perimeter progress in ``[0, 1)``."""
    period = float(period_s) if period_s else REVOLUTION_S
    if period <= 0.0:
        period = REVOLUTION_S
    return ((float(now) - float(started)) / period) % 1.0


def _counts(leds_left: int, leds_top: int, leds_right: int, leds_bottom: int) -> Dict[str, int]:
    return {
        "left": max(0, int(leds_left)),
        "top": max(0, int(leds_top)),
        "right": max(0, int(leds_right)),
        "bottom": max(0, int(leds_bottom)),
    }


def _total(counts: Dict[str, int]) -> int:
    return counts["left"] + counts["top"] + counts["right"] + counts["bottom"]


def perimeter_led_index(
    progress: float,
    *,
    leds_left: int,
    leds_top: int,
    leds_right: int,
    leds_bottom: int,
    start_corner: str = "bottom_left",
    direction: str = "cw",
) -> int:
    """Map perimeter progress in ``[0, 1)`` to a strip LED index.

    Progress 0 is the first LED (the start corner). Progress increases along
    ``edge_sequence`` — clockwise from that corner unless ``direction`` is
    counter-clockwise. ``start_corner`` and ``direction`` select that order;
    the index itself is the offset along it.
    """
    total = _total(_counts(leds_left, leds_top, leds_right, leds_bottom))
    if total <= 0:
        return 0
    pos = float(progress) % 1.0
    # Epsilon keeps ``n / total * total`` from truncating to n-1.
    return int(pos * total + 1e-9) % total


def _along_screen(travel: str, index_on_edge: int, count: int) -> float:
    """Center of this LED on the edge. 0 is top or left; 1 is bottom or right."""
    if count <= 0:
        return 0.0
    center = (int(index_on_edge) + 0.5) / float(count)
    if travel in ("up", "rtl"):
        return 1.0 - center
    return center


def perimeter_location(
    progress: float,
    *,
    leds_left: int,
    leds_top: int,
    leds_right: int,
    leds_bottom: int,
    start_corner: str = "bottom_left",
    direction: str = "cw",
) -> Dict[str, object]:
    """Edge placement for ``progress``.

    ``along`` is 0 at the top of a vertical edge or the left of a horizontal
    edge, and 1 at the opposite end. ``led_index`` is the strip index.
    """
    counts = _counts(leds_left, leds_top, leds_right, leds_bottom)
    total = _total(counts)
    led = perimeter_led_index(
        progress,
        leds_left=counts["left"],
        leds_top=counts["top"],
        leds_right=counts["right"],
        leds_bottom=counts["bottom"],
        start_corner=start_corner,
        direction=direction,
    )
    if total <= 0:
        return {
            "led_index": 0,
            "edge": "left",
            "index_on_edge": 0,
            "edge_count": 0,
            "along": 1.0,
            "travel": "up",
        }
    cursor = 0
    for edge, travel in edge_sequence(start_corner, direction):
        count = counts[edge]
        if count <= 0:
            continue
        if led < cursor + count:
            index_on_edge = led - cursor
            return {
                "led_index": led,
                "edge": edge,
                "index_on_edge": index_on_edge,
                "edge_count": count,
                "along": _along_screen(travel, index_on_edge, count),
                "travel": travel,
            }
        cursor += count
    return {
        "led_index": led,
        "edge": "left",
        "index_on_edge": 0,
        "edge_count": counts["left"],
        "along": 1.0,
        "travel": "up",
    }


def bar_rect(
    location: Dict[str, object],
    width: int,
    height: int,
    *,
    thickness_frac: float = BAR_THICKNESS_FRAC,
    length_frac: float = BAR_LENGTH_FRAC,
) -> Rect:
    """Pixel rect ``(x, y, w, h)`` of the white bar. Origin is top-left.

    Thickness is about 3% of the short edge (within 2–4%). The bar stays on
    the hotspot's edge.
    """
    width = max(1, int(width))
    height = max(1, int(height))
    short = min(width, height)
    thick = max(1, int(round(short * float(thickness_frac))))
    edge = str(location.get("edge") or "left")
    along = float(location.get("along") or 0.0)
    if edge in ("left", "right"):
        length = max(thick, int(round(height * float(length_frac))))
        length = min(length, height)
        y = int(round(along * height - length / 2.0))
        y = max(0, min(height - length, y))
        x = 0 if edge == "left" else max(0, width - thick)
        return (x, y, min(thick, width), length)
    length = max(thick, int(round(width * float(length_frac))))
    length = min(length, width)
    x = int(round(along * width - length / 2.0))
    x = max(0, min(width - length, x))
    y = 0 if edge == "top" else max(0, height - thick)
    return (x, y, length, min(thick, height))


def hotspot_frame(
    progress: float,
    *,
    leds_left: int,
    leds_top: int,
    leds_right: int,
    leds_bottom: int,
    start_corner: str = "bottom_left",
    direction: str = "cw",
    brightness: int = 255,
) -> List[RGB]:
    """Black frame with a white blob centered on the perimeter LED.

    The center pixel is full white. A couple of neighbours fall off so the
    spot is visible on a 264-LED strip without lighting an edge.
    """
    counts = _counts(leds_left, leds_top, leds_right, leds_bottom)
    total = _total(counts)
    if total <= 0:
        return []
    center = perimeter_led_index(
        progress,
        leds_left=counts["left"],
        leds_top=counts["top"],
        leds_right=counts["right"],
        leds_bottom=counts["bottom"],
        start_corner=start_corner,
        direction=direction,
    )
    half = max(0, total // 100)
    level = max(0, min(255, int(brightness)))
    pixels: List[RGB] = [(0, 0, 0)] * total
    for offset in range(-half, half + 1):
        dist = abs(offset)
        gain = 1.0 if half == 0 else 1.0 - (dist / float(half + 1))
        value = int(level * gain)
        pixels[(center + offset) % total] = (value, value, value)
    return pixels


class CalibrateClock:
    """Phase clock shared by the on-screen bar and the DDP worker.

    ``tick`` is the worker side: it queues the hotspot for *now* and returns a
    frame only after ``sync_delay_ms``, using the same ``SyncDelay`` as live
    video. The UI calls ``phase`` and does not touch the queue.
    """

    def __init__(
        self,
        geometry: Dict[str, object],
        delay_ms: int = 40,
        period_s: float = REVOLUTION_S,
        started: Optional[float] = None,
    ) -> None:
        self.geometry = dict(geometry)
        self.delay_ms = clamp_delay_ms(delay_ms)
        self.period_s = float(period_s) if period_s else REVOLUTION_S
        self.started = None if started is None else float(started)
        self.delay = SyncDelay(max_pending=24)
        self._lock = threading.Lock()

    def set_delay_ms(self, value: int) -> int:
        """Apply a new delay and drop frames still waiting on the old one."""
        new = clamp_delay_ms(value)
        with self._lock:
            if new != self.delay_ms:
                self.delay_ms = new
                self.delay.clear()
        return self.delay_ms

    def phase(self, now: float) -> float:
        if self.started is None:
            self.started = float(now)
        return phase_at(now, self.started, self.period_s)

    def location(self, now: float) -> Dict[str, object]:
        return perimeter_location(self.phase(now), **self._geo())  # type: ignore[arg-type]

    def tick(self, now: float) -> Optional[Sequence[RGB]]:
        """Queue the current hotspot and return one whose delay has elapsed."""
        frame = hotspot_frame(self.phase(now), **self._geo())  # type: ignore[arg-type]
        if not frame:
            return None
        with self._lock:
            self.delay.push(frame, float(now), self.delay_ms / 1000.0)
            return self.delay.pop_ready(float(now))

    def _geo(self) -> Dict[str, object]:
        return {
            "leds_left": self.geometry.get("leds_left", 0),
            "leds_top": self.geometry.get("leds_top", 0),
            "leds_right": self.geometry.get("leds_right", 0),
            "leds_bottom": self.geometry.get("leds_bottom", 0),
            "start_corner": self.geometry.get("start_corner", "bottom_left"),
            "direction": self.geometry.get("direction", "cw"),
        }
