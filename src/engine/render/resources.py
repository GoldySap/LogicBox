from typing import Any, Dict, Optional


class ResourceRegistry:
    """Universal Asset Manager mapping abstract keys to memory objects."""
    def __init__(self):
        self._resources: Dict[str, Any] = {}

    def register(self, resource_id: str, resource_data: Any):
        self._resources[resource_id] = resource_data

    def get(self, resource_id: str) -> Optional[Any]:
        return self._resources.get(resource_id)

    def unload(self, resource_id: str):
        if resource_id in self._resources:
            del self._resources[resource_id]

# Singleton asset pipeline
resources = ResourceRegistry()