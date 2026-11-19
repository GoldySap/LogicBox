import copy
from typing import Dict, List


class RollbackBuffer:
    def __init__(self, capacity: int = 120):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._states: List[dict] = []

    def record(self, state: dict):
        self._states.append(copy.deepcopy(state))
        if len(self._states) > self.capacity:
            del self._states[:-self.capacity]

    def restore(self, frames_back: int = 1) -> dict:
        if frames_back <= 0:
            raise ValueError("frames_back must be positive")
        if len(self._states) < frames_back:
            raise IndexError("rollback history is insufficient")
        return copy.deepcopy(self._states[-frames_back])

    def clear(self):
        self._states.clear()
