from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional
from engine.core.node import Node
from engine.core.signal import events
from engine.core.math import Matrix4


class RenderPassType(Enum):
    SHADOW = auto()
    BACKGROUND = auto()
    OPAQUE = auto()
    TRANSPARENT = auto()
    UI = auto()


@dataclass
class DrawCommand:
    """Stateless render payload dispatched to hardware drivers."""
    node_path: str
    pass_type: RenderPassType
    layer: int
    sorting_depth: float
    material_id: str
    world_matrix: Matrix4
    primitive_type: str
    payload: Dict[str, Any]


class CommandBuffer:
    """Manages rendering operations sorted by pass, layer, material state, and depth."""
    def __init__(self):
        self.commands: List[DrawCommand] = []

    def push(self, cmd: DrawCommand):
        self.commands.append(cmd)

    def sort(self):
        self.commands.sort(key=lambda c: (c.pass_type.value, c.layer, c.material_id, c.sorting_depth))

    def clear(self):
        self.commands.clear()


class UniversalRenderPipeline:
    """Target-agnostic rendering pipeline orchestrator."""
    def __init__(self, driver: Optional[Any] = None):
        self.driver = driver
        self.command_buffer = CommandBuffer()

        events.subscribe("render:set_driver", self.set_driver)
        events.subscribe("render:frame", self.render_scene)

    def set_driver(self, driver: Any):
        self.driver = driver

    def render_scene(self, root_node: Node):
        if not self.driver:
            return

        self.command_buffer.clear()

        # Locate Active Camera
        from engine.render.components import CameraComponent, RenderableComponent
        camera_nodes = root_node.find_by_component(CameraComponent)
        active_camera: Optional[CameraComponent] = None
        for cnode in camera_nodes:
            c = cnode.get_component(CameraComponent)
            if c and c.active:
                active_camera = c
                break

        # Extract & Cull
        renderable_nodes = root_node.find_by_component(RenderableComponent)
        for rnode in renderable_nodes:
            rcomp = rnode.get_component(RenderableComponent)
            if rcomp:
                cmd = rcomp.build_draw_command(active_camera)
                if cmd:
                    self.command_buffer.push(cmd)

        self.command_buffer.sort()

        self.driver.begin_frame()
        try:
            self.driver.execute_command_buffer(self.command_buffer, active_camera)
        finally:
            self.driver.end_frame()