import traceback
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, Optional


@dataclass
class SceneSnapshot:
    node_count: int
    component_count: int
    tags: Dict[str, int]


class Inspector:
    def snapshot(self, root) -> SceneSnapshot:
        nodes = []

        def walk(node):
            nodes.append(node)
            for child in node.children:
                walk(child)

        walk(root)
        tag_counts = {}
        component_count = 0
        for node in nodes:
            for tag in node.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            component_count += len(node._components)
        return SceneSnapshot(len(nodes), component_count, tag_counts)

    def describe(self, node) -> dict:
        return {
            "name": node.name,
            "path": node.path,
            "tags": sorted(node.tags),
            "metadata": node.metadata,
            "components": sorted(
                component.__class__.__name__
                for component in node._components.values()
            ),
        }


class CrashReporter:
    def capture(self, exception: BaseException, context: Optional[dict] = None) -> dict:
        return {
            "type": exception.__class__.__name__,
            "message": str(exception),
            "traceback": traceback.format_exception(
                exception.__class__,
                exception,
                exception.__traceback__,
            ),
            "context": dict(context or {}),
        }
