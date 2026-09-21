"""RenderCapture sizing and frame-budget helpers. No xbmc import.

The service calls ``xbmc.RenderCapture`` on a worker. These functions only
decide the buffer size (~96 px on the long edge) and when to drop to 15 fps.
"""

from __future__ import annotations


def capture_size(aspect: float, long_edge: int = 96) -> tuple:
    """Return even (width, height) with the long edge near ``long_edge``."""
    try:
        aspect = float(aspect)
    except (TypeError, ValueError):
        aspect = 0.0
    if aspect <= 0.05:
        aspect = 16.0 / 9.0
    long_edge = max(16, int(long_edge))
    if aspect >= 1.0:
        width = long_edge
        height = max(2, int(round(long_edge / aspect)))
    else:
        height = long_edge
        width = max(2, int(round(long_edge * aspect)))
    if width % 2:
        width += 1
    if height % 2:
        height += 1
    return width, height


def recommend_fps(avg_process_ms: float, current_fps: int, budget_ms: float = 8.0, floor: int = 15) -> int:
    """Drop to ``floor`` when map+colour average exceeds the budget."""
    current = int(current_fps)
    if avg_process_ms > budget_ms and current > floor:
        return floor
    return current
