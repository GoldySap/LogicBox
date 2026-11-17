from dataclasses import dataclass
from typing import Any, Dict, Tuple

from engine.render.components import RenderableComponent


@dataclass
class UIStyle:
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)
    background: Tuple[int, int, int, int] = (30, 30, 30, 255)
    font_size: int = 16
    padding: int = 4


class UIComponent(RenderableComponent):
    """Backend-neutral user interface primitive."""
    def __init__(self, text: str = "", style: UIStyle = None, width: int = 100,
                 height: int = 30):
        super().__init__()
        self.text = text
        self.style = style or UIStyle()
        self.width = width
        self.height = height
        self.hovered = False
        self.pressed = False

    def get_primitive_type(self) -> str:
        return "rect" if self.text == "" else "text"

    def get_payload(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "width": self.width,
            "height": self.height,
            "color": self.style.color[:3],
            "background": self.style.background[:3],
            "font_size": self.style.font_size,
            "hovered": self.hovered,
            "pressed": self.pressed,
        }


class Label(UIComponent):
    pass


class Button(UIComponent):
    def on_input(self, event: Any):
        if isinstance(event, dict):
            self.hovered = event.get("hovered", self.hovered)
            if event.get("pressed"):
                self.pressed = True
            elif event.get("released"):
                self.pressed = False
