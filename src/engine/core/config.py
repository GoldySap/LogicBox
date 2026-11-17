import copy
import json
import threading
from pathlib import Path
from typing import Any, Mapping


class Config:
    """Nested, JSON-compatible configuration with environment-safe defaults."""
    def __init__(self, values: Mapping[str, Any] = None):
        self._values = copy.deepcopy(dict(values or {}))
        self._lock = threading.RLock()

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Configuration root must be a JSON object")
        return cls(data)

    def save(self, path):
        with self._lock:
            destination = Path(path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + ".tmp")
            temporary.write_text(
                json.dumps(self._values, indent=2, sort_keys=True, allow_nan=False),
                encoding="utf-8",
            )
            temporary.replace(destination)

    def get(self, key: str, default=None):
        with self._lock:
            value = self._values
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value:
                    return default
                value = value[part]
            return copy.deepcopy(value)

    def set(self, key: str, value):
        with self._lock:
            target = self._values
            parts = key.split(".")
            if not parts or any(not part for part in parts):
                raise ValueError("Configuration key must contain non-empty components")
            for part in parts[:-1]:
                child = target.get(part)
                if not isinstance(child, dict):
                    child = {}
                    target[part] = child
                target = child
            target[parts[-1]] = copy.deepcopy(value)

    def to_dict(self):
        with self._lock:
            return copy.deepcopy(self._values)
