import heapq
import itertools
import threading
import time
import logging
from typing import Callable, Optional

logger = logging.getLogger("UniversalEngine")


class Scheduler:
    """Thread-safe one-shot and repeating task scheduler."""
    def __init__(self):
        self._counter = itertools.count()
        self._tasks = []
        self._lock = threading.RLock()
        self.on_error: Optional[Callable[[Exception], None]] = None
        self._cancelled = set()

    def call_later(self, delay: float, callback: Callable, *args, **kwargs) -> int:
        if delay < 0:
            raise ValueError("Delay must be non-negative")
        return self._schedule(delay, callback, args, kwargs, 0.0)

    def call_every(self, interval: float, callback: Callable, *args, **kwargs) -> int:
        if interval <= 0:
            raise ValueError("Interval must be positive")
        return self._schedule(interval, callback, args, kwargs, interval)

    def _schedule(self, delay: float, callback: Callable, args: tuple,
                  kwargs: dict, interval: float) -> int:
        task_id = next(self._counter)
        due_at = time.monotonic() + delay
        with self._lock:
            heapq.heappush(self._tasks, (due_at, task_id, callback, args, kwargs, interval))
        return task_id

    def cancel(self, task_id: int) -> bool:
        with self._lock:
            self._cancelled.add(task_id)
            for index, task in enumerate(self._tasks):
                if task[1] == task_id:
                    del self._tasks[index]
                    heapq.heapify(self._tasks)
                    return True
        return False

    def update(self) -> int:
        now = time.monotonic()
        executed = 0
        while True:
            with self._lock:
                if not self._tasks or self._tasks[0][0] > now:
                    return executed
                due_at, task_id, callback, args, kwargs, interval = heapq.heappop(self._tasks)
            if task_id in self._cancelled:
                continue
            try:
                callback(*args, **kwargs)
            except Exception as exc:
                if self.on_error:
                    self.on_error(exc)
                else:
                    logger.exception("Scheduled callback failed")
            executed += 1
            if interval:
                with self._lock:
                    if task_id in self._cancelled:
                        continue
                    heapq.heappush(
                        self._tasks,
                        (now + interval, task_id, callback, args, kwargs, interval),
                    )

    def clear(self):
        with self._lock:
            self._tasks.clear()
            self._cancelled.clear()


class Clock:
    """Fixed-size simulation clock with clamped frame delta."""
    def __init__(self, max_delta: float = 0.25):
        if max_delta <= 0:
            raise ValueError("Max delta must be positive")
        self.max_delta = max_delta
        self.delta = 0.0
        self.total_time = 0.0
        self._last = time.monotonic()

    def tick(self) -> float:
        now = time.monotonic()
        self.delta = min(max(now - self._last, 0.0), self.max_delta)
        self._last = now
        self.total_time += self.delta
        return self.delta
