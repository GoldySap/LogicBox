import copy
import threading
from typing import Callable, Dict, Iterable, Optional


class ReplicationManager:
    """Snapshot and delta replication foundation."""
    def __init__(self):
        self._states: Dict[str, dict] = {}
        self._versions: Dict[str, int] = {}
        self._lock = threading.RLock()

    def set_state(self, network_id: str, state: dict):
        with self._lock:
            self._states[network_id] = copy.deepcopy(state)
            self._versions[network_id] = self._versions.get(network_id, 0) + 1
        return self._versions[network_id]

    def get_delta(self, network_id: str, previous: dict) -> dict:
        with self._lock:
            current = copy.deepcopy(self._states.get(network_id, {}))
        return {
            key: value
            for key, value in current.items()
            if key not in previous or previous[key] != value
        }

    def apply_delta(self, network_id: str, delta: dict):
        with self._lock:
            state = self._states.setdefault(network_id, {})
            state.update(copy.deepcopy(delta))
            self._versions[network_id] = self._versions.get(network_id, 0) + 1
        return copy.deepcopy(state)

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._states)


class NetworkSession:
    def __init__(self, authority: str = "server"):
        if authority not in ("server", "host", "peer"):
            raise ValueError("unsupported authority")
        self.authority = authority
        self.connected = set()
        self.replication = ReplicationManager()

    def connect(self, peer_id: str):
        self.connected.add(peer_id)

    def disconnect(self, peer_id: str):
        self.connected.discard(peer_id)
