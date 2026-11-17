from typing import Any, Optional

from engine.render.driver import UniversalDriver
from engine.render.pipeline import CommandBuffer
from engine.core.input import input


class PygameGraphicsDriver(UniversalDriver):
    """Optional pygame backend for 2D and simple 3D command rendering."""
    def __init__(self, width: int = 800, height: int = 600, title: str = "Universal Engine",
                 flags: int = 0):
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError("Pygame is not installed. Install the 'pygame' extra.") from exc
        self.pygame = pygame
        pygame.init()
        self.screen = pygame.display.set_mode((width, height), flags)
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()

    def begin_frame(self):
        self.screen.fill((0, 0, 0))

    def execute_command_buffer(self, buffer: CommandBuffer, camera: Optional[Any]):
        for command in buffer.commands:
            if command.primitive_type == "text":
                text = str(command.payload.get("text", ""))
                color = tuple(command.payload.get("color", (255, 255, 255)))
                font_size = int(command.payload.get("font_size", 16))
                font = self.pygame.font.SysFont(None, font_size)
                surface = font.render(text, True, color)
                x, y = command.world_matrix.extract_position()[:2]
                self.screen.blit(surface, (int(x), int(y)))
            elif command.primitive_type == "rect":
                color = tuple(command.payload.get("color", (255, 255, 255)))
                width = int(command.payload.get("width", 32))
                height = int(command.payload.get("height", 32))
                x, y = command.world_matrix.extract_position()[:2]
                self.pygame.draw.rect(self.screen, color, (int(x), int(y), width, height))

    def end_frame(self):
        self.pygame.display.flip()
        self.clock.tick()

    def poll_events(self):
        events = []
        for event in self.pygame.event.get():
            if event.type == self.pygame.QUIT:
                events.append(("quit", event))
            elif event.type == self.pygame.KEYDOWN:
                input.set_key(self.pygame.key.name(event.key), True)
                events.append(("key_down", event))
            elif event.type == self.pygame.KEYUP:
                input.set_key(self.pygame.key.name(event.key), False)
                events.append(("key_up", event))
            elif event.type in (
                getattr(self.pygame, "MOUSEBUTTONDOWN", -1),
                getattr(self.pygame, "MOUSEBUTTONUP", -1),
            ):
                button = f"mouse_{getattr(event, 'button', 0)}"
                input.set_mouse_button(button, event.type == self.pygame.MOUSEBUTTONDOWN)
                input.set_mouse_position(*getattr(event, "pos", (0, 0)))
                events.append(("mouse", event))
            elif event.type == getattr(self.pygame, "MOUSEMOTION", -1):
                input.set_mouse_position(*getattr(event, "pos", (0, 0)))
                events.append(("mouse_motion", event))
            else:
                events.append((event.type, event))
        return events

    def shutdown(self):
        self.pygame.quit()

    def poll_application_events(self, application):
        quit_requested = False
        for kind, event in self.poll_events():
            if kind == "quit":
                quit_requested = True
            application.process_input_event(event)
        return quit_requested
