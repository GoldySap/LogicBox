import concurrent.futures
import threading
import json
import time
from pathlib import Path
from typing import Callable, Dict, Optional


class AssetManager:
    """Async asset loading, cache, reference, and unload management."""
    def __init__(self, max_workers: int = 4):
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="logicbox-assets",
        )
        self._lock = threading.RLock()
        self._assets: Dict[str, object] = {}
        self._loading: Dict[str, concurrent.futures.Future] = {}

    def load_async(self, asset_id: str, loader: Callable[[], object]):
        if not isinstance(asset_id, str) or not asset_id:
            raise ValueError("asset_id must be a non-empty string")
        with self._lock:
            if asset_id in self._assets:
                completed = concurrent.futures.Future()
                completed.set_result(self._assets[asset_id])
                return completed
            if asset_id in self._loading:
                return self._loading[asset_id]
            future = self._executor.submit(loader)
            self._loading[asset_id] = future
        future.add_done_callback(
            lambda completed: self._cache_asset(asset_id, completed)
        )
        return future

    def load_file_async(self, asset_id: str, path, mode: str = "rb"):
        def loader():
            return Path(path).read_bytes() if "b" in mode else Path(path).read_text(encoding="utf-8")
        return self.load_async(asset_id, loader)

    def _cache_asset(self, asset_id: str, future):
        with self._lock:
            self._loading.pop(asset_id, None)
            if future.cancelled():
                return
            exception = future.exception()
            if exception is None:
                self._assets[asset_id] = future.result()

    def get(self, asset_id: str) -> Optional[object]:
        with self._lock:
            return self._assets.get(asset_id)

    def unload(self, asset_id: str) -> bool:
        with self._lock:
            if asset_id in self._loading:
                self._loading.pop(asset_id).cancel()
            return self._assets.pop(asset_id, None) is not None

    def clear(self):
        with self._lock:
            for future in self._loading.values():
                future.cancel()
            self._loading.clear()
            self._assets.clear()

    def close(self, wait: bool = True):
        self.clear()
        self._executor.shutdown(wait=wait, cancel_futures=True)


class AssetManifest:
    def __init__(self, entries=None):
        self.entries = dict(entries or {})

    def add(self, asset_id: str, path: str, kind: str,
            checksum: Optional[str] = None, dependencies=()):
        if not asset_id or not path or not kind:
            raise ValueError("asset_id, path, and kind are required")
        self.entries[asset_id] = {
            "path": path,
            "kind": kind,
            "checksum": checksum,
            "dependencies": list(dependencies),
        }

    def save(self, path):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({"assets": self.entries}, indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("assets"), dict):
            raise ValueError("asset manifest root must contain an assets object")
        return cls(data["assets"])


class HotReloadWatcher:
    def __init__(self, paths):
        self.paths = [Path(path) for path in paths]
        self._timestamps = {}
        self._lock = threading.RLock()
        self._refresh()

    def _refresh(self):
        with self._lock:
            for path in self.paths:
                if path.is_file():
                    self._timestamps[str(path)] = path.stat().st_mtime_ns

    def changes(self):
        changed = []
        with self._lock:
            for path in self.paths:
                if not path.is_file():
                    continue
                stamp = path.stat().st_mtime_ns
                key = str(path)
                if key not in self._timestamps:
                    changed.append(path)
                    self._timestamps[key] = stamp
                elif self._timestamps[key] != stamp:
                    changed.append(path)
                    self._timestamps[key] = stamp
        return tuple(changed)
