import math
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple
from engine.core.node import Component
from engine.core.math import Matrix4, AABB
from engine.render.pipeline import DrawCommand, RenderPassType


class TransformComponent(Component):
    """Hierarchical transform component utilizing dirty-flag caching matrix calculations."""
    def __init__(self, position: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                 rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                 scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)):
        super().__init__()
        self._position = list(position)
        self._rotation = list(rotation)
        self._scale = list(scale)
        self._local_matrix = Matrix4.identity()
        self._world_matrix = Matrix4.identity()
        self._dirty = True

    def mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            if self.node:
                for child in self.node.children:
                    t = child.get_component(TransformComponent)
                    if t:
                        t.mark_dirty()

    @property
    def position(self) -> List[float]: return self._position
    @position.setter
    def position(self, val: Tuple[float, float, float]): self._position = list(val); self.mark_dirty()

    @property
    def rotation(self) -> List[float]: return self._rotation
    @rotation.setter
    def rotation(self, val: Tuple[float, float, float]): self._rotation = list(val); self.mark_dirty()

    @property
    def scale(self) -> List[float]: return self._scale
    @scale.setter
    def scale(self, val: Tuple[float, float, float]): self._scale = list(val); self.mark_dirty()

    def get_world_matrix(self) -> Matrix4:
        if self._dirty:
            local = Matrix4.trs(tuple(self._position), tuple(self._rotation), tuple(self._scale))
            parent_node = self.node.parent if self.node else None
            parent_t = parent_node.get_component(TransformComponent) if parent_node else None
            self._world_matrix = parent_t.get_world_matrix().multiply(local) if parent_t else local
            self._dirty = False
        return self._world_matrix


class ProjectionType(Enum):
    ORTHOGRAPHIC = auto()
    PERSPECTIVE = auto()
    CELL_GRID = auto()


class CameraComponent(Component):
    """Camera supporting viewports and spatial bounding box culling."""
    def __init__(self, projection_type: ProjectionType = ProjectionType.ORTHOGRAPHIC,
                 ortho_bounds: Tuple[float, float, float, float] = (-10.0, 10.0, -10.0, 10.0),
                 near: float = 0.1, far: float = 1000.0, active: bool = True):
        super().__init__()
        self.projection_type = projection_type
        self.ortho_bounds = ortho_bounds
        self.near = near
        self.far = far
        self.active = active

    def is_aabb_visible(self, aabb: AABB) -> bool:
        l, r, b, t = self.ortho_bounds
        if aabb.max_bounds[0] < l or aabb.min_bounds[0] > r:
            return False
        if aabb.max_bounds[1] < b or aabb.min_bounds[1] > t:
            return False
        return True


class RenderableComponent(Component):
    """Base visual component emitting stateless draw calls."""
    def __init__(self, pass_type: RenderPassType = RenderPassType.OPAQUE, layer: int = 0, visible: bool = True):
        super().__init__()
        self.pass_type = pass_type
        self.layer = layer
        self.visible = visible
        self.material_id: str = "default_mat"
        self.local_aabb = AABB()

    def build_draw_command(self, camera: Optional[CameraComponent]) -> Optional[DrawCommand]:
        if not self.visible or not self.node:
            return None

        transform = self.node.get_component(TransformComponent)
        world_mat = transform.get_world_matrix() if transform else Matrix4.identity()

        if camera:
            world_aabb = self.local_aabb.transform(world_mat)
            if not camera.is_aabb_visible(world_aabb):
                return None

        world_pos = world_mat.extract_position()
        depth = 0.0
        if camera and camera.node:
            cam_t = camera.node.get_component(TransformComponent)
            if cam_t:
                cpos = cam_t.get_world_matrix().extract_position()
                depth = math.sqrt(sum((a - b) ** 2 for a, b in zip(world_pos, cpos)))

        return DrawCommand(
            node_path=self.node.path,
            pass_type=self.pass_type,
            layer=self.layer,
            sorting_depth=depth,
            material_id=self.material_id,
            world_matrix=world_mat,
            primitive_type=self.get_primitive_type(),
            payload=self.get_payload()
        )

    def get_primitive_type(self) -> str: raise NotImplementedError
    def get_payload(self) -> Dict[str, Any]: return {}