import threading
from typing import Any, Callable, Dict, Optional


class ResourceRegistry:
    """Universal Asset Manager mapping abstract keys to memory objects."""
    def __init__(self):
        self._resources: Dict[str, Any] = {}
        self._loaders: Dict[str, Callable[[str], Any]] = {}
        self._lock = threading.RLock()

    def register(self, resource_id: str, resource_data: Any):
        with self._lock:
            self._resources[resource_id] = resource_data

    def get(self, resource_id: str) -> Optional[Any]:
        with self._lock:
            if resource_id in self._resources:
                return self._resources[resource_id]
            loader = self._loaders.get(resource_id)
        if loader:
            resource = loader(resource_id)
            self.register(resource_id, resource)
            return resource
        return None

    def register_loader(self, resource_id: str, loader: Callable[[str], Any]):
        with self._lock:
            self._loaders[resource_id] = loader

    def register_prefix_loader(self, prefix: str, loader: Callable[[str], Any]):
        with self._lock:
            self._loaders[f"prefix:{prefix}"] = loader

    def load(self, resource_id: str) -> Any:
        existing = self.get(resource_id)
        if existing is not None:
            return existing
        for key, loader in list(self._loaders.items()):
            if key.startswith("prefix:") and resource_id.startswith(key[7:]):
                resource = loader(resource_id)
                self.register(resource_id, resource)
                return resource
        raise KeyError(f"Unknown resource: {resource_id}")

    def unload(self, resource_id: str):
        with self._lock:
            self._resources.pop(resource_id, None)

    def unregister_loader(self, resource_id: str):
        with self._lock:
            return self._loaders.pop(resource_id, None) is not None

    def clear(self):
        with self._lock:
            self._resources.clear()

# Singleton asset pipeline
resources = ResourceRegistry()