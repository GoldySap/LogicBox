from typing import Any, Optional

from engine.render.driver import UniversalDriver
from engine.render.pipeline import CommandBuffer


class OpenGLGraphicsDriver(UniversalDriver):
    """Optional ModernGL backend with a command-compatible rendering contract."""
    def __init__(self, window: Optional[Any] = None):
        try:
            import moderngl
        except ImportError as exc:
            raise RuntimeError("ModernGL is not installed. Install the 'opengl' extra.") from exc
        self.moderngl = moderngl
        self.window = window
        self.context = moderngl.create_context(require=330) if window is None else window.ctx
        self._clear_color = (0.0, 0.0, 0.0, 1.0)
        self._programs = {}
        self._buffers = {}
        self._vaos = []

    def create_program(self, name: str,
                       vertex_source: Optional[str] = None,
                       fragment_source: Optional[str] = None):
        vertex_source = vertex_source or """
            #version 330
            in vec3 in_position;
            uniform mat4 mvp;
            void main() {
                gl_Position = mvp * vec4(in_position, 1.0);
            }
        """
        fragment_source = fragment_source or """
            #version 330
            out vec4 fragColor;
            void main() {
                fragColor = vec4(1.0, 1.0, 1.0, 1.0);
            }
        """
        program = self.context.program(
            vertex_shader=vertex_source,
            fragment_shader=fragment_source,
        )
        self._programs[name] = program
        return program

    def set_clear_color(self, red: float, green: float, blue: float, alpha: float = 1.0):
        self._clear_color = (red, green, blue, alpha)

    def begin_frame(self):
        self.context.clear(*self._clear_color)

    def execute_command_buffer(self, buffer: CommandBuffer, camera: Optional[Any]):
        for command in buffer.commands:
            if command.primitive_type == "clear":
                color = command.payload.get("color")
                if color:
                    self.context.clear(*color)
            elif command.primitive_type == "mesh":
                vertices = command.payload.get("vertices")
                if not vertices:
                    continue
                buffer_name = command.payload.get("buffer", command.node_path)
                gpu_buffer = self._buffers.get(buffer_name)
                if gpu_buffer is None:
                    import struct
                    packed = struct.pack(
                        f"<{len(vertices) * 3}f",
                        *[value for vertex in vertices for value in vertex],
                    )
                    gpu_buffer = self.context.buffer(packed)
                    self._buffers[buffer_name] = gpu_buffer
                program = self._programs.get(command.payload.get("program", "default"))
                if program is None:
                    program = self.create_program("default")
                vao = self.context.vertex_array(program, [(gpu_buffer, "3f", "in_position")])
                self._vaos.append(vao)
                try:
                    mvp_uniform = program["mvp"]
                except KeyError:
                    mvp_uniform = None
                if mvp_uniform is not None:
                    import struct
                    world = command.world_matrix
                    mvp = (
                        camera.get_view_projection_matrix().multiply(world)
                        if camera is not None
                        else world
                    )
                    mvp_uniform.write(struct.pack("<16f", *mvp.m))
                vao.render(command.payload.get("mode", self.moderngl.TRIANGLES))

    def end_frame(self):
        if self.window is not None:
            self.window.swap_buffers()

    def shutdown(self):
        for vao in getattr(self, "_vaos", []):
            vao.release()
        for gpu_buffer in self._buffers.values():
            gpu_buffer.release()
        for program in self._programs.values():
            program.release()
