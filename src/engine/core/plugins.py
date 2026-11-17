import importlib
import threading
import logging
from typing import Dict, Iterable, Optional

logger = logging.getLogger("UniversalEngine")


class Extension:
    """Base class for application, domain, and backend extensions."""
    def on_load(self, context):
        pass

    def on_unload(self, context):
        pass


class PluginManager:
    """Load local or entry-point-like extension modules safely."""
    def __init__(self, context):
        self.context = context
        self._plugins: Dict[str, Extension] = {}
        self._lock = threading.RLock()

    def register(self, name: str, plugin: Extension):
        if not isinstance(name, str) or not name:
            raise ValueError("Plugin name must be a non-empty string")
        if not hasattr(plugin, "on_load") or not hasattr(plugin, "on_unload"):
            raise TypeError("Plugin must implement on_load(context) and on_unload(context)")
        with self._lock:
            if name in self._plugins:
                raise KeyError(f"Plugin already registered: {name}")
        plugin.on_load(self.context)
        with self._lock:
            self._plugins[name] = plugin
        return plugin

    def load_module(self, name: str, module_name: Optional[str] = None,
                    class_name: str = "Plugin") -> Extension:
        module = importlib.import_module(module_name or name)
        plugin_class = getattr(module, class_name)
        plugin = plugin_class()
        return self.register(name, plugin)

    def unload(self, name: str) -> bool:
        with self._lock:
            plugin = self._plugins.pop(name, None)
        if plugin is None:
            return False
        plugin.on_unload(self.context)
        return True

    def unload_all(self):
        with self._lock:
            names = list(self._plugins)
        for name in reversed(names):
            try:
                self.unload(name)
            except Exception:
                logger.exception("Plugin %s failed during unload", name)

    def get(self, name: str) -> Optional[Extension]:
        with self._lock:
            return self._plugins.get(name)

    @property
    def names(self):
        with self._lock:
            return tuple(self._plugins)
