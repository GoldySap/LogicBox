from typing import Optional, Any
from engine.render.driver import UniversalDriver
from engine.render.pipeline import CommandBuffer


class TerminalGraphicsDriver(UniversalDriver):
    """Driver converting render commands into ASCII screen buffer grids."""
    def __init__(self, width: int = 40, height: int = 10):
        if width <= 0 or height <= 0:
            raise ValueError("Terminal width and height must be positive")
        self.width = width
        self.height = height
        self.buffer = []

    def begin_frame(self):
        self.buffer = [[" " for _ in range(self.width)] for _ in range(self.height)]

    def execute_command_buffer(self, buffer: CommandBuffer, camera: Optional[Any]):
        for cmd in buffer.commands:
            if cmd.primitive_type == "terminal_text":
                pos = cmd.world_matrix.extract_position()
                ix, iy = int(pos[0]), int(pos[1])
                text = cmd.payload.get("text", "")
                if 0 <= iy < self.height:
                    for i, char in enumerate(text):
                        if 0 <= ix + i < self.width:
                            self.buffer[iy][ix + i] = char

    def end_frame(self):
        print("+" + "-" * self.width + "+")
        for row in self.buffer:
            print("|" + "".join(row) + "|")
        print("+" + "-" * self.width + "+")