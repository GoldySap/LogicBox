from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from engine.core.math import Matrix4


@dataclass
class Mesh:
    resource_id: str
    vertices: List[Tuple[float, float, float]]
    normals: List[Tuple[float, float, float]] = field(default_factory=list)
    uv: List[Tuple[float, float]] = field(default_factory=list)
    indices: List[int] = field(default_factory=list)

    def validate(self):
        if not self.vertices:
            raise ValueError("mesh must contain vertices")
        if any(index < 0 or index >= len(self.vertices) for index in self.indices):
            raise ValueError("mesh index is outside the vertex array")


@dataclass
class MeshInstance:
    mesh_id: str
    material_id: str
    world_matrix: Matrix4 = field(default_factory=Matrix4.identity)
    visible: bool = True
