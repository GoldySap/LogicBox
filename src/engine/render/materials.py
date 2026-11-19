from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass
class Texture:
    resource_id: str
    width: int = 0
    height: int = 0
    mipmaps: bool = True


@dataclass
class Material:
    resource_id: str
    shader: str = "default"
    base_color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    metallic: float = 0.0
    roughness: float = 0.5
    textures: Dict[str, Texture] = field(default_factory=dict)

    def validate(self):
        if not 0.0 <= self.metallic <= 1.0:
            raise ValueError("metallic must be between 0 and 1")
        if not 0.0 <= self.roughness <= 1.0:
            raise ValueError("roughness must be between 0 and 1")
        if len(self.base_color) != 4:
            raise ValueError("base_color must contain RGBA values")


@dataclass
class Light:
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    color: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    intensity: float = 1.0
    radius: float = 10.0
    kind: str = "point"

    def validate(self):
        if self.intensity < 0:
            raise ValueError("intensity cannot be negative")
        if self.kind not in ("point", "directional", "spot"):
            raise ValueError("unsupported light kind")
