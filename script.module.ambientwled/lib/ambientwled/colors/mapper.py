"""Per-edge geometry mapper.

LED order follows start_corner + direction around the TV. Default for this
install is left 47, top 85, right 47, bottom 85, bottom-left, clockwise.

Edge colours are the mean of a band ``edge_depth_pct`` thick on the active
picture rectangle. Letterbox bars (2.39 in a 16:9 frame) are cropped out
before sampling so the bottom edge reads the picture, not the black bar.

This is not a 32% / 18% / 32% / 18% split of a single LED count.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

RGB = Tuple[int, int, int]

# Clockwise, starting at bottom-left: up the left side, across the top,
# down the right side, back along the bottom toward the left.
CW_EDGES = (
    ("left", "up"),
    ("top", "ltr"),
    ("right", "down"),
    ("bottom", "rtl"),
)
CW_STARTS = ("bottom_left", "top_left", "top_right", "bottom_right")

# Counter-clockwise from bottom-left: along the bottom toward the right.
CCW_EDGES = (
    ("bottom", "ltr"),
    ("right", "up"),
    ("top", "rtl"),
    ("left", "down"),
)
CCW_STARTS = ("bottom_left", "bottom_right", "top_right", "top_left")


def edge_sequence(start_corner: str = "bottom_left", direction: str = "cw"):
    """Return the ordered (edge, travel) pairs for one loop."""
    start = (start_corner or "bottom_left").strip().lower().replace("-", "_").replace(" ", "_")
    direction = (direction or "cw").strip().lower()
    if direction in ("ccw", "counterclockwise", "counter_clockwise"):
        edges, starts = CCW_EDGES, CCW_STARTS
    else:
        edges, starts = CW_EDGES, CW_STARTS
    if start not in starts:
        start = starts[0]
    index = starts.index(start)
    return edges[index:] + edges[:index]


def _luma(b: int, g: int, r: int) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def detect_content_rect(
    frame,
    width: int,
    height: int,
    black_threshold: float = 16.0,
    min_content_frac: float = 0.30,
) -> Tuple[int, int, int, int]:
    """Return exclusive (x0, y0, x1, y1) of the non-bar picture.

    A dark scene that would collapse the window falls back to the full frame.
    """
    width = int(width)
    height = int(height)
    if width < 2 or height < 2:
        return 0, 0, max(0, width), max(0, height)
    mv = memoryview(frame)
    thresh = float(black_threshold)

    def row_mean(y: int) -> float:
        base = y * width * 4
        total = 0.0
        for x in range(width):
            i = base + x * 4
            total += _luma(mv[i], mv[i + 1], mv[i + 2])
        return total / width

    def col_mean(x: int) -> float:
        total = 0.0
        for y in range(height):
            i = (y * width + x) * 4
            total += _luma(mv[i], mv[i + 1], mv[i + 2])
        return total / height

    top = 0
    while top < height - 1 and row_mean(top) < thresh:
        top += 1
    bottom = height - 1
    while bottom > top and row_mean(bottom) < thresh:
        bottom -= 1
    left = 0
    while left < width - 1 and col_mean(left) < thresh:
        left += 1
    right = width - 1
    while right > left and col_mean(right) < thresh:
        right -= 1

    content_w = right - left + 1
    content_h = bottom - top + 1
    if content_w < width * min_content_frac or content_h < height * min_content_frac:
        return 0, 0, width, height
    if (width - content_w) < width * 0.02 and (height - content_h) < height * 0.02:
        return 0, 0, width, height
    return left, top, right + 1, bottom + 1


def _avg_rect(mv, width: int, x0: int, x1: int, y0: int, y1: int) -> RGB:
    if x1 <= x0:
        x1 = x0 + 1
    if y1 <= y0:
        y1 = y0 + 1
    total_r = total_g = total_b = 0
    count = 0
    for y in range(y0, y1):
        row = y * width * 4
        for x in range(x0, x1):
            i = row + x * 4
            total_b += mv[i]
            total_g += mv[i + 1]
            total_r += mv[i + 2]
            count += 1
    if count == 0:
        return (0, 0, 0)
    return (total_r // count, total_g // count, total_b // count)


def _span(origin: int, length: int, index: int, count: int, reverse: bool) -> Tuple[int, int]:
    count = max(1, count)
    if reverse:
        a = origin + int((count - index - 1) * length / count)
        b = origin + int((count - index) * length / count)
    else:
        a = origin + int(index * length / count)
        b = origin + int((index + 1) * length / count)
    if b <= a:
        b = a + 1
    return a, b


def map_frame(
    frame: Sequence[int],
    width: int,
    height: int,
    *,
    leds_left: int = 47,
    leds_top: int = 85,
    leds_right: int = 47,
    leds_bottom: int = 85,
    start_corner: str = "bottom_left",
    direction: str = "cw",
    edge_depth_pct: int = 10,
    black_threshold: int = 8,
) -> List[RGB]:
    """Sample one RGB colour per LED. Frame is BGRA."""
    counts = {
        "left": max(0, int(leds_left)),
        "top": max(0, int(leds_top)),
        "right": max(0, int(leds_right)),
        "bottom": max(0, int(leds_bottom)),
    }
    total = counts["left"] + counts["top"] + counts["right"] + counts["bottom"]
    if total <= 0:
        return []
    width = int(width)
    height = int(height)
    needed = width * height * 4
    if width < 2 or height < 2 or frame is None or len(frame) < needed:
        return [(0, 0, 0)] * total

    bar_thresh = max(16.0, float(black_threshold))
    x0, y0, x1, y1 = detect_content_rect(frame, width, height, black_threshold=bar_thresh)
    cw = max(1, x1 - x0)
    ch = max(1, y1 - y0)
    depth_x = max(1, int(round(cw * max(1, int(edge_depth_pct)) / 100.0)))
    depth_y = max(1, int(round(ch * max(1, int(edge_depth_pct)) / 100.0)))
    depth_x = min(depth_x, max(1, cw // 2))
    depth_y = min(depth_y, max(1, ch // 2))

    mv = memoryview(frame)
    colours: List[RGB] = []
    for edge, travel in edge_sequence(start_corner, direction):
        count = counts[edge]
        for i in range(count):
            if edge == "left":
                xa, xb = x0, min(x1, x0 + depth_x)
                ya, yb = _span(y0, ch, i, count, reverse=(travel == "up"))
            elif edge == "right":
                xa, xb = max(x0, x1 - depth_x), x1
                ya, yb = _span(y0, ch, i, count, reverse=(travel == "up"))
            elif edge == "top":
                ya, yb = y0, min(y1, y0 + depth_y)
                xa, xb = _span(x0, cw, i, count, reverse=(travel == "rtl"))
            else:
                ya, yb = max(y0, y1 - depth_y), y1
                xa, xb = _span(x0, cw, i, count, reverse=(travel == "rtl"))
            xa = max(0, min(width - 1, xa))
            ya = max(0, min(height - 1, ya))
            xb = max(xa + 1, min(width, xb))
            yb = max(ya + 1, min(height, yb))
            colours.append(_avg_rect(mv, width, xa, xb, ya, yb))
    return colours
