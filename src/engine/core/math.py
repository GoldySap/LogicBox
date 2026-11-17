import math
from typing import List, Optional, Tuple
# from dataclasses import dataclass, field
# from enum import Enum, auto
# from typing import Any, Dict, List, Optional, Set, Tuple, Type
# from LogicBox.src.engine.core.node import Component, Node
# from signal import events

class Matrix4:
    """Full 4x4 Transformation Matrix supporting Translation, Rotation (Euler Pitch/Yaw/Roll), and Scaling."""
    def __init__(self, data: Optional[List[float]] = None):
        if data and len(data) == 16:
            self.m = list(data)
        else:
            self.m = [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0
            ]

    @classmethod
    def identity(cls) -> 'Matrix4':
        return cls()

    @classmethod
    def trs(cls, pos: Tuple[float, float, float], rot: Tuple[float, float, float], scale: Tuple[float, float, float]) -> 'Matrix4':
        x, y, z = pos
        rx, ry, rz = math.radians(rot[0]), math.radians(rot[1]), math.radians(rot[2])
        sx, sy, sz = scale

        cx, sx_s = math.cos(rx), math.sin(rx)
        cy, sy_s = math.cos(ry), math.sin(ry)
        cz, sz_s = math.cos(rz), math.sin(rz)

        r00 = cy * cz
        r01 = -cy * sz_s
        r02 = sy_s
        r10 = cz * sx_s * sy_s + cx * sz_s
        r11 = cx * cz - sx_s * sy_s * sz_s
        r12 = -cy * sx_s
        r20 = -cx * cy * sz_s + sx_s * sz_s
        r21 = cz * sx_s + cx * sy_s * sz_s
        r22 = cx * cy

        return cls([
            r00 * sx, r01 * sy, r02 * sz, 0.0,
            r10 * sx, r11 * sy, r12 * sz, 0.0,
            r20 * sx, r21 * sy, r22 * sz, 0.0,
            x,        y,        z,        1.0
        ])

    def multiply(self, other: 'Matrix4') -> 'Matrix4':
        res = [0.0] * 16
        for r in range(4):
            for c in range(4):
                res[r * 4 + c] = sum(
                    self.m[r * 4 + i] * other.m[i * 4 + c] for i in range(4)
                )
        return Matrix4(res)

    def extract_position(self) -> Tuple[float, float, float]:
        return (self.m[12], self.m[13], self.m[14])


class AABB:
    """Axis-Aligned Bounding Box for universal spatial culling."""
    def __init__(self, min_bounds: Tuple[float, float, float] = (-0.5, -0.5, -0.5),
                 max_bounds: Tuple[float, float, float] = (0.5, 0.5, 0.5)):
        self.min_bounds = min_bounds
        self.max_bounds = max_bounds

    def transform(self, matrix: Matrix4) -> 'AABB':
        pos = matrix.extract_position()
        return AABB(
            min_bounds=(self.min_bounds[0] + pos[0], self.min_bounds[1] + pos[1], self.min_bounds[2] + pos[2]),
            max_bounds=(self.max_bounds[0] + pos[0], self.max_bounds[1] + pos[1], self.max_bounds[2] + pos[2])
        )

# class TransformComponent(Component):
#     """Hierarchy matrix calculator with automatic dirty-flag propagation."""
#     def __init__(self, position: Tuple[float, float, float] = (0.0, 0.0, 0.0),
#                  rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0),
#                  scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)):
#         super().__init__()
#         self._position = list(position)
#         self._rotation = list(rotation)
#         self._scale = list(scale)
#         self._local_matrix = Matrix4.identity()
#         self._world_matrix = Matrix4.identity()
#         self._dirty = True

#     def mark_dirty(self):
#         if not self._dirty:
#             self._dirty = True
#             if self.node:
#                 for child in self.node.children:
#                     t = child.get_component(TransformComponent)
#                     if t:
#                         t.mark_dirty()

#     @property
#     def position(self) -> List[float]: return self._position
#     @position.setter
#     def position(self, val: Tuple[float, float, float]): self._position = list(val); self.mark_dirty()

#     @property
#     def rotation(self) -> List[float]: return self._rotation
#     @rotation.setter
#     def rotation(self, val: Tuple[float, float, float]): self._rotation = list(val); self.mark_dirty()

#     @property
#     def scale(self) -> List[float]: return self._scale
#     @scale.setter
#     def scale(self, val: Tuple[float, float, float]): self._scale = list(val); self.mark_dirty()

#     def get_world_matrix(self) -> Matrix4:
#         if self._dirty:
#             local = Matrix4.trs(tuple(self._position), tuple(self._rotation), tuple(self._scale))
#             parent_node = self.node.parent if self.node else None
#             parent_t = parent_node.get_component(TransformComponent) if parent_node else None
#             self._world_matrix = parent_t.get_world_matrix().multiply(local) if parent_t else local
#             self._dirty = False
#         return self._world_matrix


# # ============================================================================
# # 2. UNIVERSAL RESOURCE & ASSET MANAGER
# # ============================================================================

# class ResourceRegistry:
#     """Universal Asset Manager mapping abstract keys to loaded memory objects/handles."""
#     def __init__(self):
#         self._resources: Dict[str, Any] = {}

#     def register(self, resource_id: str, resource_data: Any):
#         self._resources[resource_id] = resource_data

#     def get(self, resource_id: str) -> Optional[Any]:
#         return self._resources.get(resource_id)

#     def unload(self, resource_id: str):
#         if resource_id in self._resources:
#             del self._resources[resource_id]

# # Global Asset Engine Singleton
# resources = ResourceRegistry()


# # ============================================================================
# # 3. CAMERA, VIEWPORT & SPATIAL CULLING
# # ============================================================================

# class ProjectionType(Enum):
#     ORTHOGRAPHIC = auto()
#     PERSPECTIVE = auto()
#     CELL_GRID = auto()


# class CameraComponent(Component):
#     """Camera supporting multi-projection space, frustum/box culling, and viewport bounds."""
#     def __init__(self, projection_type: ProjectionType = ProjectionType.ORTHOGRAPHIC,
#                  ortho_bounds: Tuple[float, float, float, float] = (-10.0, 10.0, -10.0, 10.0),
#                  near: float = 0.1, far: float = 1000.0, active: bool = True):
#         super().__init__()
#         self.projection_type = projection_type
#         self.ortho_bounds = ortho_bounds  # (left, right, bottom, top)
#         self.near = near
#         self.far = far
#         self.active = active

#     def is_aabb_visible(self, aabb: AABB) -> bool:
#         """Simple, target-agnostic bounding-box frustum check."""
#         l, r, b, t = self.ortho_bounds
#         # Check X/Y spatial overlap against viewport orthographic bounds
#         if aabb.max_bounds[0] < l or aabb.min_bounds[0] > r:
#             return False
#         if aabb.max_bounds[1] < b or aabb.min_bounds[1] > t:
#             return False
#         return True


# # ============================================================================
# # 4. MULTI-PASS COMMAND BUFFER (Material Batching & Sorting)
# # ============================================================================

# class RenderPassType(Enum):
#     SHADOW = auto()
#     BACKGROUND = auto()
#     OPAQUE = auto()
#     TRANSPARENT = auto()
#     UI = auto()


# @dataclass
# class DrawCommand:
#     """Stateless render payload emitted to driver engines."""
#     node_path: str
#     pass_type: RenderPassType
#     layer: int
#     sorting_depth: float
#     material_id: str
#     world_matrix: Matrix4
#     primitive_type: str
#     payload: Dict[str, Any]


# class CommandBuffer:
#     """Manages command queue and executes state-optimized multi-pass sorting."""
#     def __init__(self):
#         self.commands: List[DrawCommand] = []

#     def push(self, cmd: DrawCommand):
#         self.commands.append(cmd)

#     def sort(self):
#         # Optimized Order: Pass -> Layer -> Material (State Minimization) -> Depth
#         self.commands.sort(key=lambda c: (c.pass_type.value, c.layer, c.material_id, c.sorting_depth))

#     def clear(self):
#         self.commands.clear()


# # ============================================================================
# # 5. UNIVERSAL RENDER COMPONENT BASE & PIPELINE CORE
# # ============================================================================

# class RenderableComponent(Component):
#     """Base visual component with bounding-box support for frustum culling."""
#     def __init__(self, pass_type: RenderPassType = RenderPassType.OPAQUE, layer: int = 0, visible: bool = True):
#         super().__init__()
#         self.pass_type = pass_type
#         self.layer = layer
#         self.visible = visible
#         self.material_id: str = "default_mat"
#         self.local_aabb = AABB()

#     def build_draw_command(self, camera: Optional[CameraComponent]) -> Optional[DrawCommand]:
#         if not self.visible or not self.node:
#             return None

#         transform = self.node.get_component(TransformComponent)
#         world_mat = transform.get_world_matrix() if transform else Matrix4.identity()

#         # Spatial Culling Check
#         if camera:
#             world_aabb = self.local_aabb.transform(world_mat)
#             if not camera.is_aabb_visible(world_aabb):
#                 return None

#         world_pos = world_mat.extract_position()
#         depth = 0.0
#         if camera and camera.node:
#             cam_t = camera.node.get_component(TransformComponent)
#             if cam_t:
#                 cpos = cam_t.get_world_matrix().extract_position()
#                 depth = math.sqrt(sum((a - b) ** 2 for a, b in zip(world_pos, cpos)))

#         return DrawCommand(
#             node_path=self.node.path,
#             pass_type=self.pass_type,
#             layer=self.layer,
#             sorting_depth=depth,
#             material_id=self.material_id,
#             world_matrix=world_mat,
#             primitive_type=self.get_primitive_type(),
#             payload=self.get_payload()
#         )

#     def get_primitive_type(self) -> str: raise NotImplementedError
#     def get_payload(self) -> Dict[str, Any]: return {}


# class UniversalDriver:
#     """Driver contract for concrete graphic implementations."""
#     def begin_frame(self): pass
#     def execute_command_buffer(self, buffer: CommandBuffer, camera: Optional[CameraComponent]): raise NotImplementedError
#     def end_frame(self): pass


# class UniversalRenderPipeline:
#     """Target-agnostic rendering pipeline orchestrator."""
#     def __init__(self, driver: Optional[UniversalDriver] = None):
#         self.driver: Optional[UniversalDriver] = driver
#         self.command_buffer = CommandBuffer()

#         events.subscribe("render:set_driver", self.set_driver)
#         events.subscribe("render:frame", self.render_scene)

#     def set_driver(self, driver: UniversalDriver):
#         self.driver = driver

#     def render_scene(self, root_node: Node):
#         if not self.driver:
#             return

#         self.command_buffer.clear()

#         # 1. Locate Active Camera
#         camera_nodes = root_node.find_by_component(CameraComponent)
#         active_camera: Optional[CameraComponent] = None
#         for cnode in camera_nodes:
#             c = cnode.get_component(CameraComponent)
#             if c and c.active:
#                 active_camera = c
#                 break

#         # 2. Extract Commands & Perform Culling
#         renderable_nodes = root_node.find_by_component(RenderableComponent)
#         for rnode in renderable_nodes:
#             rcomp = rnode.get_component(RenderableComponent)
#             if rcomp:
#                 cmd = rcomp.build_draw_command(active_camera)
#                 if cmd:
#                     self.command_buffer.push(cmd)

#         # 3. State-Optimized Sorting
#         self.command_buffer.sort()

#         # 4. Flush to Hardware Driver
#         self.driver.begin_frame()
#         self.driver.execute_command_buffer(self.command_buffer, active_camera)
#         self.driver.end_frame()