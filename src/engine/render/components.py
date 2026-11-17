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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": self._position,
            "rotation": self._rotation,
            "scale": self._scale,
        }

    def load_state(self, data: Dict[str, Any]):
        self.position = tuple(data.get("position", (0.0, 0.0, 0.0)))
        self.rotation = tuple(data.get("rotation", (0.0, 0.0, 0.0)))
        self.scale = tuple(data.get("scale", (1.0, 1.0, 1.0)))


class ProjectionType(Enum):
    ORTHOGRAPHIC = auto()
    PERSPECTIVE = auto()
    CELL_GRID = auto()


class CameraComponent(Component):
    """Camera supporting viewports and spatial bounding box culling."""
    def __init__(self, projection_type: ProjectionType = ProjectionType.ORTHOGRAPHIC,
                 ortho_bounds: Tuple[float, float, float, float] = (-10.0, 10.0, -10.0, 10.0),
                 near: float = 0.1, far: float = 1000.0, active: bool = True,
                 fov_degrees: float = 60.0, viewport_size: Tuple[int, int] = (800, 600)):
        super().__init__()
        self.projection_type = projection_type
        self.ortho_bounds = ortho_bounds
        self.near = near
        self.far = far
        self.active = active
        self.fov_degrees = fov_degrees
        self.viewport_size = viewport_size
        self.target = (0.0, 0.0, 0.0)
        self.up = (0.0, 1.0, 0.0)

    def get_view_matrix(self) -> Matrix4:
        if not self.node:
            return Matrix4.identity()
        transform = self.node.get_component(TransformComponent)
        eye = transform.get_world_matrix().extract_position() if transform else (0.0, 0.0, 0.0)
        return Matrix4.look_at(eye, self.target, self.up)

    def get_projection_matrix(self) -> Matrix4:
        if self.projection_type == ProjectionType.PERSPECTIVE:
            width, height = self.viewport_size
            return Matrix4.perspective(
                self.fov_degrees,
                width / height if height else 1.0,
                self.near,
                self.far,
            )
        left, right, bottom, top = self.ortho_bounds
        return Matrix4.orthographic(left, right, bottom, top, self.near, self.far)

    def get_view_projection_matrix(self) -> Matrix4:
        return self.get_projection_matrix().multiply(self.get_view_matrix())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "projection_type": self.projection_type.name,
            "ortho_bounds": self.ortho_bounds,
            "near": self.near,
            "far": self.far,
            "active": self.active,
            "fov_degrees": self.fov_degrees,
            "viewport_size": self.viewport_size,
            "target": self.target,
            "up": self.up,
        }

    def load_state(self, data: Dict[str, Any]):
        self.projection_type = ProjectionType[data.get("projection_type", "ORTHOGRAPHIC")]
        self.ortho_bounds = tuple(data.get("ortho_bounds", (-10.0, 10.0, -10.0, 10.0)))
        self.near = data.get("near", 0.1)
        self.far = data.get("far", 1000.0)
        self.active = data.get("active", True)
        self.fov_degrees = data.get("fov_degrees", 60.0)
        self.viewport_size = tuple(data.get("viewport_size", (800, 600)))
        self.target = tuple(data.get("target", (0.0, 0.0, 0.0)))
        self.up = tuple(data.get("up", (0.0, 1.0, 0.0)))

    def is_aabb_visible(self, aabb: AABB) -> bool:
        if self.projection_type == ProjectionType.PERSPECTIVE:
            view_projection = self.get_view_projection_matrix()
            for x in (aabb.min_bounds[0], aabb.max_bounds[0]):
                for y in (aabb.min_bounds[1], aabb.max_bounds[1]):
                    for z in (aabb.min_bounds[2], aabb.max_bounds[2]):
                        point = view_projection.multiply_point((x, y, z))
                        if -1.0 <= point[0] <= 1.0 and -1.0 <= point[1] <= 1.0 and -1.0 <= point[2] <= 1.0:
                            return True
            return False
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