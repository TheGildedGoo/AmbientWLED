"""Single-slot queue. A newer item replaces the one still waiting."""

from __future__ import annotations

import threading
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


class LatestSlot(Generic[T]):
    """Depth-1 handoff. ``put`` drops the previous unread item."""

    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._item: Optional[T] = None
        self._closed = False

    def put(self, item: T) -> None:
        with self._cv:
            if self._closed:
                return
            self._item = item
            self._cv.notify_all()

    def get(self, timeout: float = 0.1) -> Optional[T]:
        with self._cv:
            if self._item is None and not self._closed:
                self._cv.wait(timeout)
            item = self._item
            self._item = None
            return item

    def close(self) -> None:
        with self._cv:
            self._closed = True
            self._cv.notify_all()
