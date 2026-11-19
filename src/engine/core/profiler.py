import statistics
import threading
import time
from collections import defaultdict
from typing import Dict, Iterable


class FrameProfiler:
    """Low-overhead frame and named-operation profiler."""
    def __init__(self, history_size: int = 120):
        if history_size <= 0:
            raise ValueError("history_size must be positive")
        self.history_size = history_size
        self._samples: Dict[str, list] = defaultdict(list)
        self._active = {}
        self._lock = threading.RLock()

    def begin(self, name: str):
        with self._lock:
            self._active[name] = time.perf_counter()

    def end(self, name: str):
        with self._lock:
            start = self._active.pop(name, None)
            if start is None:
                raise KeyError(f"No active profile sample: {name}")
            samples = self._samples[name]
            samples.append(time.perf_counter() - start)
            if len(samples) > self.history_size:
                del samples[:-self.history_size]

    def measure(self, name: str, callback, *args, **kwargs):
        self.begin(name)
        try:
            return callback(*args, **kwargs)
        finally:
            self.end(name)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                name: {
                    "count": len(samples),
                    "last": samples[-1] if samples else 0.0,
                    "mean": statistics.fmean(samples) if samples else 0.0,
                    "max": max(samples) if samples else 0.0,
                }
                for name, samples in self._samples.items()
            }

    def clear(self):
        with self._lock:
            self._samples.clear()
            self._active.clear()
