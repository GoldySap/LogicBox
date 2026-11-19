from typing import Iterable, Set


class CapabilityPolicy:
    def __init__(self, capabilities: Iterable[str] = ()):
        self._capabilities: Set[str] = set(capabilities)

    def grant(self, capability: str):
        self.require_name(capability)
        self._capabilities.add(capability)

    def revoke(self, capability: str):
        self.require_name(capability)
        self._capabilities.discard(capability)

    def can(self, capability: str) -> bool:
        return capability in self._capabilities

    def require(self, capability: str):
        if not self.can(capability):
            raise PermissionError(f"Missing capability: {capability}")

    @staticmethod
    def require_name(capability: str):
        if not isinstance(capability, str) or not capability:
            raise ValueError("capability must be a non-empty string")
