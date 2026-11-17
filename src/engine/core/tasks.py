import asyncio
import concurrent.futures
import threading
from typing import Callable, Optional


class TaskRunner:
    """Thread-safe bridge for CPU, I/O, and asyncio work."""
    def __init__(self, max_workers: Optional[int] = None):
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="engine-task",
        )
        self._lock = threading.RLock()
        self._tasks = set()
        self._closed = False

    def submit(self, function: Callable, *args, **kwargs):
        with self._lock:
            if self._closed:
                raise RuntimeError("TaskRunner is shut down")
            future = self._executor.submit(function, *args, **kwargs)
            self._tasks.add(future)
        future.add_done_callback(self._done)
        return future

    def submit_async(self, coroutine):
        def run():
            return asyncio.run(coroutine)
        return self.submit(run)

    def _done(self, future):
        with self._lock:
            self._tasks.discard(future)

    def cancel_all(self):
        with self._lock:
            for future in tuple(self._tasks):
                future.cancel()

    def shutdown(self, wait: bool = True):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=True)
