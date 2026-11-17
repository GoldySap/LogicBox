import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Diagnostic:
    level: str
    message: str
    source: str
    timestamp: float
    data: Dict


class Diagnostics:
    """In-memory diagnostic recorder with standard logging integration."""
    def __init__(self, logger: Optional[logging.Logger] = None, limit: int = 10000):
        if limit <= 0:
            raise ValueError("Diagnostic limit must be positive")
        self.logger = logger or logging.getLogger("UniversalEngine")
        self.limit = limit
        self._records: List[Diagnostic] = []
        self._lock = threading.RLock()

    def record(self, level: str, message: str, source: str = "engine", **data):
        level = level.upper()
        record = Diagnostic(level, message, source, time.time(), dict(data))
        with self._lock:
            self._records.append(record)
            if len(self._records) > self.limit:
                del self._records[:len(self._records) - self.limit]
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method("[%s] %s", source, message)
        return record

    def info(self, message: str, source: str = "engine", **data):
        return self.record("INFO", message, source, **data)

    def warning(self, message: str, source: str = "engine", **data):
        return self.record("WARNING", message, source, **data)

    def error(self, message: str, source: str = "engine", **data):
        return self.record("ERROR", message, source, **data)

    def snapshot(self, level: Optional[str] = None) -> tuple:
        with self._lock:
            records = list(self._records)
        if level:
            level = level.upper()
            records = [record for record in records if record.level == level]
        return tuple(records)

    def clear(self):
        with self._lock:
            self._records.clear()
