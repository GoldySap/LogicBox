import threading
import json
from typing import Any, Dict, List, Optional, Set, Type, TypeVar, Generator

T = TypeVar('T', bound='Component')


class Component:
    """Base class for all node components. Implement lifecycle hooks as needed."""
    def __init__(self):
        self.node: Optional['Node'] = None

    def on_attached(self, node: 'Node'):
        """Called when this component is added to a node."""
        self.node = node

    def on_detached(self, node: 'Node'):
        """Called when this component is removed from a node."""
        self.node = None

    def on_enter_tree(self):
        """Called when the parent node enters an active tree hierarchy."""
        pass

    def on_exit_tree(self):
        """Called when the parent node leaves a tree hierarchy."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Override to serialize custom component state."""
        return {}


class Node:
    """
    A universal, thread-safe node container driven entirely by components.
    Supports lifecycle management, path navigation, tag filtering, and serialization.
    """
    def __init__(self, name: str, parent: Optional['Node'] = None):
        self.name: str = name
        self._parent: Optional['Node'] = None
        self._children: List['Node'] = []
        self._components: Dict[Type[Component], Component] = {}
        self.tags: Set[str] = set()
        self.metadata: Dict[str, Any] = {}
        self._is_in_tree: bool = False
        self._lock = threading.RLock()

        if parent:
            parent.add_child(self)

    @property
    def parent(self) -> Optional['Node']:
        with self._lock:
            return self._parent

    @property
    def children(self) -> List['Node']:
        with self._lock:
            return list(self._children)

    @property
    def root(self) -> 'Node':
        current = self
        while current.parent:
            current = current.parent
        return current

    @property
    def path(self) -> str:
        ancestors = []
        curr: Optional[Node] = self
        while curr:
            ancestors.insert(0, curr.name)
            curr = curr.parent
        return "/" + "/".join(ancestors) if ancestors else "/"

    def add_child(self, child: 'Node') -> 'Node':
        with self._lock:
            if child._parent:
                child._parent.remove_child(child)
            
            child._parent = self
            self._children.append(child)

            # If parent is already in a tree, propagate tree entry down
            if self._is_in_tree:
                child._enter_tree()
            return child

    def remove_child(self, child: 'Node') -> Optional['Node']:
        with self._lock:
            if child in self._children:
                if child._is_in_tree:
                    child._exit_tree()
                self._children.remove(child)
                child._parent = None
                return child
            return None

    def _enter_tree(self):
        with self._lock:
            self._is_in_tree = True
            self.on_enter_tree()
            for comp in self._components.values():
                comp.on_enter_tree()
            for child in self._children:
                child._enter_tree()

    def _exit_tree(self):
        with self._lock:
            for child in list(self._children):
                child._exit_tree()
            for comp in self._components.values():
                comp.on_exit_tree()
            self.on_exit_tree()
            self._is_in_tree = False

    def on_enter_tree(self):
        """Override to run logic when node attaches to an active tree."""
        pass

    def on_exit_tree(self):
        """Override to run cleanup logic when node leaves a tree."""
        pass

    def add_component(self, component: Component) -> Component:
        with self._lock:
            comp_type = type(component)
            if comp_type in self._components:
                self.remove_component(comp_type)
            
            self._components[comp_type] = component
            component.on_attached(self)
            if self._is_in_tree:
                component.on_enter_tree()
            return component

    def remove_component(self, comp_type: Type[T]) -> Optional[T]:
        with self._lock:
            component = self._components.pop(comp_type, None)
            if component:
                if self._is_in_tree:
                    component.on_exit_tree()
                component.on_detached(self)
            return component

    def has_component(self, comp_type: Type[Component]) -> bool:
        with self._lock:
            return any(issubclass(registered_type, comp_type) for registered_type in self._components)

    def get_component(self, comp_type: Type[T]) -> Optional[T]:
        with self._lock:
            # Check exact match first
            if comp_type in self._components:
                return self._components[comp_type]
            # Fallback to subclass match
            for registered_type, instance in self._components.items():
                if issubclass(registered_type, comp_type):
                    return instance
            return None

    def find_by_tag(self, tag: str) -> List['Node']:
        results = []
        with self._lock:
            if tag in self.tags:
                results.append(self)
            for child in self._children:
                results.extend(child.find_by_tag(tag))
        return results

    def find_by_component(self, comp_type: Type[Component]) -> List['Node']:
        results = []
        with self._lock:
            if self.has_component(comp_type):
                results.append(self)
            for child in self._children:
                results.extend(child.find_by_component(comp_type))
        return results

    def get_node(self, path: str) -> Optional['Node']:
        if not path:
            return self
        parts = [p for p in path.split("/") if p]
        if not parts:
            return self

        curr: Optional[Node] = self
        if path.startswith("/"):
            curr = self.root
            if parts and parts[0] == curr.name:
                parts = parts[1:]

        for part in parts:
            if not curr:
                return None
            if part == "..":
                curr = curr.parent
            elif part == ".":
                continue
            else:
                found = None
                with curr._lock:
                    for child in curr._children:
                        if child.name == part:
                            found = child
                            break
                curr = found
        return curr

    def emit_bubble(self, event_name: str, *args, **kwargs):
        """Passes an event up the tree from child to parent."""
        if self._parent:
            self._parent.emit_bubble(event_name, *args, **kwargs)

    # --- Serialization (JSON Export / Import) ---
    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            components_data = {
                comp_type.__name__: comp.to_dict() 
                for comp_type, comp in self._components.items()
            }
            return {
                "name": self.name,
                "tags": list(self.tags),
                "metadata": self.metadata,
                "components": components_data,
                "children": [child.to_dict() for child in self._children]
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], component_registry: Optional[Dict[str, Type[Component]]] = None, parent: Optional['Node'] = None) -> 'Node':
        registry = component_registry or {}
        node = cls(name=data["name"], parent=parent)
        node.tags = set(data.get("tags", []))
        node.metadata = data.get("metadata", {})

        # Re-attach components if registered
        for comp_name, comp_state in data.get("components", {}).items():
            if comp_name in registry:
                comp_class = registry[comp_name]
                comp_instance = comp_class()
                # If you want to populate state from comp_state, you can handle it in the component
                node.add_component(comp_instance)

        for child_data in data.get("children", []):
            cls.from_dict(child_data, component_registry=registry, parent=node)
        return node

    def __repr__(self) -> str:
        return f"<Node '{self.name}' (tags={list(self.tags)}, components={list(self._components.keys())})>"