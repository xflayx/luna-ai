from __future__ import annotations

import queue
import threading
from typing import Generic, TypeVar


T = TypeVar("T")


class EventQueue(Generic[T]):
    def __init__(self, max_size: int = 100):
        self._queue: "queue.Queue[T]" = queue.Queue(maxsize=max(1, int(max_size)))
        self._dropped = 0
        self._processing = False
        self._lock = threading.Lock()

    def put(self, item: T) -> bool:
        try:
            self._queue.put_nowait(item)
            return True
        except queue.Full:
            with self._lock:
                self._dropped += 1
            return False

    def get(self, timeout_sec: float | None = None) -> T | None:
        try:
            if timeout_sec is None:
                return self._queue.get()
            return self._queue.get(timeout=max(0.0, float(timeout_sec)))
        except queue.Empty:
            return None

    def task_done(self) -> None:
        self._queue.task_done()

    def clear(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

    def reset_metrics(self, *, reset_dropped: bool = True) -> None:
        with self._lock:
            if reset_dropped:
                self._dropped = 0
        self._processing = False

    @property
    def qsize(self) -> int:
        return self._queue.qsize()

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped

    @property
    def is_processing(self) -> bool:
        return self._processing

    @is_processing.setter
    def is_processing(self, value: bool) -> None:
        self._processing = bool(value)
