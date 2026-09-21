"""Near-black probe for RenderCapture during OnPlay.

Samples the center 50% so letterbox bars are not treated as a failed grab.
A frame is empty when mean Y < 4 and max Y < 12, or the buffer is missing.
The probe fails when at least 75% of the window (default 12 frames) is empty.
"""

from __future__ import annotations

from typing import Optional, Sequence


def center_luma(frame: Optional[Sequence[int]], width: int, height: int, fraction: float = 0.5):
    """Return (mean_y, max_y, empty)."""
    width = int(width)
    height = int(height)
    if not frame or width < 1 or height < 1 or len(frame) < width * height * 4:
        return 0.0, 0.0, True
    box_w = max(1, int(width * fraction))
    box_h = max(1, int(height * fraction))
    x0 = (width - box_w) // 2
    y0 = (height - box_h) // 2
    mv = memoryview(frame)
    total = 0.0
    max_y = 0.0
    count = 0
    for y in range(y0, y0 + box_h):
        row = y * width * 4
        for x in range(x0, x0 + box_w):
            i = row + x * 4
            yv = 0.2126 * mv[i + 2] + 0.7152 * mv[i + 1] + 0.0722 * mv[i]
            total += yv
            if yv > max_y:
                max_y = yv
            count += 1
    mean_y = total / count if count else 0.0
    empty = mean_y < 4.0 and max_y < 12.0
    return mean_y, max_y, empty


class BlackDetector:
    def __init__(self, frames: int = 12, fail_ratio: float = 0.75) -> None:
        self.frames = max(1, int(frames))
        self.fail_ratio = float(fail_ratio)
        self.empty_count = 0
        self.count = 0
        self.mean_sum = 0.0
        self.max_seen = 0.0

    def add(self, frame, width: int, height: int) -> None:
        mean_y, max_y, empty = center_luma(frame, width, height)
        self.count += 1
        self.mean_sum += mean_y
        if max_y > self.max_seen:
            self.max_seen = max_y
        if empty:
            self.empty_count += 1

    @property
    def ready(self) -> bool:
        return self.count >= self.frames

    @property
    def mean_y(self) -> float:
        if not self.count:
            return 0.0
        return self.mean_sum / self.count

    def failed(self) -> bool:
        if self.count == 0:
            return True
        return (self.empty_count / self.count) >= self.fail_ratio
