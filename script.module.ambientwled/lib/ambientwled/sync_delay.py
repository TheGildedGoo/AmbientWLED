"""Timestamped send delay.

Frames are held until ``captured_at + sync_delay_ms``. When several frames
have matured, only the newest is returned (depth 1 after the delay). Capture
and the render thread are not delayed here — only the DDP send.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Optional, Sequence, Tuple

Pixel = Tuple[int, ...]


class SyncDelay:
    def __init__(self, max_pending: int = 8) -> None:
        self.max_pending = max(1, int(max_pending))
        self._items: Deque[Tuple[float, Sequence[Pixel]]] = deque()

    def push(self, pixels: Sequence[Pixel], now: float, delay_s: float) -> None:
        ready_at = float(now) + max(0.0, float(delay_s))
        self._items.append((ready_at, pixels))
        while len(self._items) > self.max_pending:
            self._items.popleft()

    def pop_ready(self, now: float) -> Optional[Sequence[Pixel]]:
        """Return the newest frame whose delay has elapsed, or None."""
        ready: Optional[Sequence[Pixel]] = None
        while self._items and self._items[0][0] <= now:
            ready = self._items.popleft()[1]
        return ready

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)
