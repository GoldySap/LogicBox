from typing import Optional, Any
from engine.render.pipeline import CommandBuffer


class UniversalDriver:
    """Driver contract for concrete graphic implementations."""
    def begin_frame(self):
        pass

    def execute_command_buffer(self, buffer: CommandBuffer, camera: Optional[Any]):
        raise NotImplementedError

    def end_frame(self):
        pass

    def shutdown(self):
        pass