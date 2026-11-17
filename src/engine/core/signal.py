import fnmatch
import inspect
import logging
import threading
import weakref
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("EnterpriseSignalSystem")


class SignalConnection:
    """Manages metadata for a single listener connection, supporting weak/strong refs, priorities, and filters."""
    def __init__(self, signal:Signal, callback:Callable, priority:int = 0, once:bool = False, weak:Optional[bool] = None, filter_fn:Optional[Callable[..., bool]] = None):
        self.signal = signal
        self.priority = priority
        self.once = once
        self.filter_fn = filter_fn
        self._strong_ref:Optional[Callable] = None

        # Auto-detect lambdas/anonymous functions (which die instantly under weakref)
        is_lambda = getattr(callback, "__name__", "") == "<lambda>"
        if weak is None:
            weak = False if is_lambda else True

        if weak and inspect.ismethod(callback):
            self._ref = weakref.WeakMethod(callback, self._on_dead_reference)
        elif weak and not is_lambda:
            try:
                self._ref = weakref.ref(callback, self._on_dead_reference)
            except TypeError:
                self._ref = lambda: callback
                self._strong_ref = callback
        else:
            self._ref = lambda: callback
            self._strong_ref = callback

    def _on_dead_reference(self, ref):
        with self.signal._lock:
            if self in self.signal._connections:
                self.signal._connections.remove(self)

    @property
    def callback(self) -> Optional[Callable]:
        return self._ref()

    def disconnect(self):
        """Explicitly disconnect this listener."""
        self.signal.disconnect_connection(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class Signal:
    """Thread-safe signal channel managing a sorted list of connections."""
    def __init__(self, name:str = "Signal", error_handler:Optional[Callable] = None):
        self.name = name
        self._connections:List[SignalConnection] = []
        self._lock = threading.RLock()
        self.error_handler = error_handler or self._default_error_handler

    def _default_error_handler(self, exception: Exception, signal_name: str, callback: Callable):
        logger.error(f"[Signal Error] Exception in listener {callback} on signal '{signal_name}': {exception}", exc_info=True)

    def connect(self, callback:Callable, priority:int = 0, once:bool = False, weak:Optional[bool] = None, filter_fn:Optional[Callable[..., bool]] = None) -> SignalConnection:
        with self._lock:
            # Update existing connection if exact callback matches
            for conn in self._connections:
                if conn.callback == callback:
                    conn.priority = priority
                    conn.once = once
                    conn.filter_fn = filter_fn
                    self._connections.sort(key=lambda c: c.priority, reverse=True)
                    return conn

            conn = SignalConnection(self, callback, priority=priority, once=once, weak=weak, filter_fn=filter_fn)
            self._connections.append(conn)
            self._connections.sort(key=lambda c: c.priority, reverse=True)
            return conn

    def disconnect(self, callback: Callable):
        with self._lock:
            self._connections = [c for c in self._connections if c.callback != callback]

    def disconnect_connection(self, conn: SignalConnection):
        with self._lock:
            if conn in self._connections:
                self._connections.remove(conn)

    def emit(self, *args, **kwargs):
        with self._lock:
            connections = list(self._connections)

        to_remove = []
        for conn in connections:
            cb = conn.callback
            if cb is None:
                to_remove.append(conn)
                continue

            # Evaluate optional filter guard
            try:
                if conn.filter_fn and not conn.filter_fn(*args, **kwargs):
                    continue
            except Exception as e:
                self.error_handler(e, self.name, conn.filter_fn)
                continue

            try:
                if inspect.iscoroutinefunction(cb):
                    logger.warning(f"[Signal Warning] Async listener {cb} called synchronously on signal '{self.name}'. Use emit_async().")
                    cb_object = cb(*args, **kwargs)
                    if hasattr(cb_object, "close"):
                        cb_object.close()
                else:
                    cb(*args, **kwargs)
            except Exception as e:
                self.error_handler(e, self.name, cb)

            if conn.once:
                to_remove.append(conn)

        if to_remove:
            with self._lock:
                for conn in to_remove:
                    if conn in self._connections:
                        self._connections.remove(conn)

    async def emit_async(self, *args, **kwargs):
        with self._lock:
            connections = list(self._connections)

        to_remove = []
        for conn in connections:
            cb = conn.callback
            if cb is None:
                to_remove.append(conn)
                continue

            # Evaluate optional filter guard
            try:
                if conn.filter_fn and not conn.filter_fn(*args, **kwargs):
                    continue
            except Exception as e:
                self.error_handler(e, self.name, conn.filter_fn)
                continue

            try:
                if inspect.iscoroutinefunction(cb):
                    await cb(*args, **kwargs)
                else:
                    cb(*args, **kwargs)
            except Exception as e:
                self.error_handler(e, self.name, cb)

            if conn.once:
                to_remove.append(conn)

        if to_remove:
            with self._lock:
                for conn in to_remove:
                    if conn in self._connections:
                        self._connections.remove(conn)

    def clear(self):
        with self._lock:
            self._connections.clear()


class EventBus:
    """Enterprise Event Bus supporting exact channels, wildcard glob subscriptions (e.g. 'player:*'), middleware hooks, and thread-safe sync/async publishing."""
    def __init__(self, error_handler:Optional[Callable] = None):
        self._channels:Dict[str, Signal] = {}
        self._wildcard_signals:Dict[str, Signal] = {}
        self._lock = threading.RLock()
        self._error_handler = error_handler
        self._pre_publish_hooks:List[Callable[[str, Tuple, Dict], None]] = []
        self._post_publish_hooks:List[Callable[[str, Tuple, Dict], None]] = []

    def add_pre_publish_hook(self, hook:Callable[[str, Tuple, Dict], None]):
        """Register middleware executed before any channel publish."""
        with self._lock:
            self._pre_publish_hooks.append(hook)

    def add_post_publish_hook(self, hook:Callable[[str, Tuple, Dict], None]):
        """Register middleware executed after any channel publish."""
        with self._lock:
            self._post_publish_hooks.append(hook)

    def get_channel(self, name:str) -> Signal:
        with self._lock:
            is_wildcard = '*' in name or '?' in name or '[' in name
            target_dict = self._wildcard_signals if is_wildcard else self._channels
            
            if name not in target_dict:
                target_dict[name] = Signal(name=name, error_handler=self._error_handler)
            return target_dict[name]

    def subscribe(self, channel: str, callback:Callable, priority:int = 0,once: bool = False, weak:Optional[bool] = None, filter_fn:Optional[Callable[..., bool]] = None) -> SignalConnection:
        """Subscribe to an exact channel name or a wildcard pattern (e.g., 'player:*')."""
        sig = self.get_channel(channel)
        return sig.connect(callback, priority=priority, once=once, weak=weak, filter_fn=filter_fn)

    def unsubscribe(self, channel: str, callback: Callable):
        with self._lock:
            is_wildcard = '*' in channel or '?' in channel or '[' in channel
            target_dict = self._wildcard_signals if is_wildcard else self._channels
            if channel in target_dict:
                target_dict[channel].disconnect(callback)

    def publish(self, channel: str, *args, **kwargs):
        """Synchronously publish to an exact channel and any matching wildcard patterns."""
        with self._lock:
            for hook in self._pre_publish_hooks:
                try:
                    hook(channel, args, kwargs)
                except Exception as e:
                    self._report_hook_error("pre-publish", channel, e)

            # 1. Emit to exact channel match
            exact_sig = self._channels.get(channel)
            
            # 2. Collect all matching wildcard channels
            matching_wildcards = [
                sig for pattern, sig in self._wildcard_signals.items()
                if fnmatch.fnmatch(channel, pattern)
            ]

        if exact_sig:
            exact_sig.emit(*args, **kwargs)

        for sig in matching_wildcards:
            sig.emit(*args, **kwargs)

        with self._lock:
            for hook in self._post_publish_hooks:
                try:
                    hook(channel, args, kwargs)
                except Exception as e:
                    self._report_hook_error("post-publish", channel, e)

    def _report_hook_error(self, phase: str, channel: str, exception: Exception):
        if self._error_handler:
            self._error_handler(exception, f"{phase}:{channel}", lambda: None)
        else:
            logger.error("[Signal Error] %s hook failed on channel '%s': %s", phase, channel, exception, exc_info=True)

    async def publish_async(self, channel: str, *args, **kwargs):
        """Asynchronously publish to an exact channel and any matching wildcard patterns."""
        with self._lock:
            for hook in self._pre_publish_hooks:
                try:
                    hook(channel, args, kwargs)
                except Exception as e:
                    self._report_hook_error("pre-publish", channel, e)

            exact_sig = self._channels.get(channel)
            matching_wildcards = [
                sig for pattern, sig in self._wildcard_signals.items()
                if fnmatch.fnmatch(channel, pattern)
            ]

        if exact_sig:
            await exact_sig.emit_async(*args, **kwargs)

        for sig in matching_wildcards:
            await sig.emit_async(*args, **kwargs)

        with self._lock:
            for hook in self._post_publish_hooks:
                try:
                    hook(channel, args, kwargs)
                except Exception as e:
                    self._report_hook_error("post-publish", channel, e)

    def clear_channel(self, channel: str):
        with self._lock:
            if channel in self._channels:
                self._channels[channel].clear()
            if channel in self._wildcard_signals:
                self._wildcard_signals[channel].clear()

    def clear_all(self):
        with self._lock:
            for sig in self._channels.values():
                sig.clear()
            for sig in self._wildcard_signals.values():
                sig.clear()
            self._channels.clear()
            self._wildcard_signals.clear()

# Global production singleton
events = EventBus()