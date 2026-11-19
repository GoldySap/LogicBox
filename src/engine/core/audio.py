from typing import Dict


class AudioSystem:
    """Optional Pygame-backed audio system with dependency-free fallback."""
    def __init__(self):
        self._sounds: Dict[str, object] = {}
        self._channels: Dict[str, object] = {}
        self._bus_volume = {"master": 1.0, "music": 1.0, "effects": 1.0}
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

    def set_bus_volume(self, bus: str, volume: float):
        if bus not in self._bus_volume:
            raise KeyError(bus)
        if not 0.0 <= volume <= 1.0:
            raise ValueError("Volume must be between 0 and 1")
        self._bus_volume[bus] = volume
        if bus == "master" and self.available:
            self._pygame.mixer.set_volume(volume)

    def play_on_bus(self, resource_id: str, bus: str = "effects",
                     loops: int = 0, pan: float = 0.0,
                     distance: float = 0.0):
        if bus not in self._bus_volume:
            raise KeyError(bus)
        if resource_id not in self._sounds:
            raise KeyError(resource_id)
        if not -1.0 <= pan <= 1.0:
            raise ValueError("pan must be between -1 and 1")
        channel = self._sounds[resource_id].play(loops=loops)
        if channel is not None:
            left = max(0.0, 1.0 - distance - max(0.0, pan))
            right = max(0.0, 1.0 - distance - max(0.0, -pan))
            channel.set_volume(left * self._bus_volume[bus], right * self._bus_volume[bus])
            self._channels[resource_id] = channel
        return channel
