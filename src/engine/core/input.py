from enum import Enum, auto
import threading
from typing import Dict, Iterable, Set


class InputState(Enum):
    RELEASED = auto()
    PRESSED = auto()
    HELD = auto()


class Input:
    """Backend-neutral keyboard, mouse, and action state manager."""
    def __init__(self):
        self._keys: Dict[str, InputState] = {}
        self._actions: Dict[str, Set[str]] = {}
        self._mouse_position = (0.0, 0.0)
        self._mouse_buttons: Dict[str, InputState] = {}
        self._lock = threading.RLock()

    def map_action(self, action: str, *inputs: str):
        self._actions[action] = set(inputs)

    def set_key(self, key: str, pressed: bool):
        with self._lock:
            if pressed:
                self._keys[key] = InputState.PRESSED if self._keys.get(key) in (None, InputState.RELEASED) else InputState.HELD
            else:
                self._keys[key] = InputState.RELEASED

    def set_mouse_button(self, button: str, pressed: bool):
        with self._lock:
            if pressed:
                current = self._mouse_buttons.get(button)
                self._mouse_buttons[button] = InputState.PRESSED if current in (None, InputState.RELEASED) else InputState.HELD
            else:
                self._mouse_buttons[button] = InputState.RELEASED

    def set_mouse_position(self, x: float, y: float):
        with self._lock:
            self._mouse_position = (x, y)

    @property
    def mouse_position(self):
        with self._lock:
            return self._mouse_position

    def is_pressed(self, key: str) -> bool:
        with self._lock:
            return self._keys.get(key) == InputState.PRESSED

    def is_held(self, key: str) -> bool:
        with self._lock:
            return self._keys.get(key) in (InputState.PRESSED, InputState.HELD)

    def is_released(self, key: str) -> bool:
        with self._lock:
            return self._keys.get(key) == InputState.RELEASED

    def action_pressed(self, action: str) -> bool:
        with self._lock:
            return any(self._keys.get(key) == InputState.PRESSED for key in self._actions.get(action, set()))

    def action_held(self, action: str) -> bool:
        with self._lock:
            return any(self._keys.get(key) in (InputState.PRESSED, InputState.HELD) for key in self._actions.get(action, set()))

    def action_released(self, action: str) -> bool:
        with self._lock:
            return any(self._keys.get(key) == InputState.RELEASED for key in self._actions.get(action, set()))

    def end_frame(self):
        with self._lock:
            for key, state in list(self._keys.items()):
                self._keys[key] = InputState.HELD if state == InputState.PRESSED else state
            for button, state in list(self._mouse_buttons.items()):
                self._mouse_buttons[button] = InputState.HELD if state == InputState.PRESSED else state


input = Input()
