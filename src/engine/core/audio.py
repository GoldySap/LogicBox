from typing import Dict


class AudioSystem:
    """Optional Pygame-backed audio system with dependency-free fallback."""
    def __init__(self):
        self._sounds: Dict[str, object] = {}
        try:
            import pygame
            pygame.mixer.init()
            self._pygame = pygame
            self.available = True
        except ImportError:
            self._pygame = None
            self.available = False
        except Exception as exc:
            self._pygame = None
            self.available = False
            raise RuntimeError("Audio backend failed to initialize") from exc

    def load(self, resource_id: str, path: str):
        if not self.available:
            raise RuntimeError("Audio backend unavailable")
        sound = self._pygame.mixer.Sound(path)
        self._sounds[resource_id] = sound
        return sound

    def play(self, resource_id: str, loops: int = 0):
        if resource_id not in self._sounds:
            raise KeyError(resource_id)
        return self._sounds[resource_id].play(loops=loops)

    def stop_all(self):
        if self.available:
            self._pygame.mixer.stop()

    def set_volume(self, volume: float):
        if not 0.0 <= volume <= 1.0:
            raise ValueError("Volume must be between 0 and 1")
        if self.available:
            self._pygame.mixer.set_volume(volume)
