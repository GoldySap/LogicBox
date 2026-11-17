from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from engine.core.node import Component
from engine.core.math import Matrix4, AABB


@dataclass
class Collision:
    first: object
    second: object
    normal: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    def resolve(self, restitution: float = 0.0):
        if restitution < 0:
            raise ValueError("Restitution must be non-negative")
        first_body = self.first.get_component(RigidBody) if hasattr(self.first, "get_component") else None
        second_body = self.second.get_component(RigidBody) if hasattr(self.second, "get_component") else None
        if first_body is None or second_body is None:
            return
        relative = (
            second_body.velocity[0] - first_body.velocity[0],
            second_body.velocity[1] - first_body.velocity[1],
            second_body.velocity[2] - first_body.velocity[2],
        )
        speed = sum(relative[index] * self.normal[index] for index in range(3))
        if speed >= 0:
            return
        impulse = -(1.0 + restitution) * speed / 2.0
        for index in range(3):
            first_body.velocity[index] -= impulse * self.normal[index]
            second_body.velocity[index] += impulse * self.normal[index]


class RigidBody(Component):
    """Dependency-free 3D rigid-body state for force and velocity integration."""
    def __init__(self, mass: float = 1.0, gravity: Tuple[float, float, float] = (0.0, -9.81, 0.0),
                 kinematic: bool = False):
        super().__init__()
        if mass <= 0:
            raise ValueError("Mass must be positive")
        self.mass = mass
        self.gravity = gravity
        self.kinematic = kinematic
        self.velocity = [0.0, 0.0, 0.0]
        self.forces = [0.0, 0.0, 0.0]

    def add_force(self, x: float, y: float, z: float = 0.0):
        self.forces[0] += x
        self.forces[1] += y
        self.forces[2] += z

    def on_fixed_process(self, fixed_delta: float):
        if self.kinematic or not self.node:
            return
        from engine.render.components import TransformComponent
        transform = self.node.get_component(TransformComponent)
        if not transform:
            return
        for index in range(3):
            acceleration = self.gravity[index] + self.forces[index] / self.mass
            self.velocity[index] += acceleration * fixed_delta
            transform._position[index] += self.velocity[index] * fixed_delta
            self.forces[index] = 0.0
        transform.mark_dirty()

    def to_dict(self):
        return {
            "mass": self.mass,
            "gravity": self.gravity,
            "kinematic": self.kinematic,
            "velocity": self.velocity,
        }

    def load_state(self, data):
        self.mass = data.get("mass", 1.0)
        self.gravity = tuple(data.get("gravity", (0.0, -9.81, 0.0)))
        self.kinematic = data.get("kinematic", False)
        self.velocity = list(data.get("velocity", (0.0, 0.0, 0.0)))


class Collider(Component):
    def __init__(self, bounds: AABB = None, trigger: bool = False):
        super().__init__()
        self.bounds = bounds or AABB()
        self.trigger = trigger

    def world_aabb(self) -> Optional[AABB]:
        if not self.node:
            return None
        from engine.render.components import TransformComponent
        transform = self.node.get_component(TransformComponent)
        world = transform.get_world_matrix() if transform else Matrix4.identity()
        return self.bounds.transform(world)


def aabb_intersects(first: AABB, second: AABB) -> bool:
    return (
        first.min_bounds[0] <= second.max_bounds[0] and
        first.max_bounds[0] >= second.min_bounds[0] and
        first.min_bounds[1] <= second.max_bounds[1] and
        first.max_bounds[1] >= second.min_bounds[1] and
        first.min_bounds[2] <= second.max_bounds[2] and
        first.max_bounds[2] >= second.min_bounds[2]
    )


class CollisionWorld:
    def __init__(self, cell_size: float = 10.0):
        if cell_size <= 0:
            raise ValueError("Cell size must be positive")
        self.cell_size = cell_size

    def get_collisions(self, root) -> List[Collision]:
        colliders = root.find_by_component(Collider)
        grid = {}
        items = []
        for node in colliders:
            collider = node.get_component(Collider)
            bounds = collider.world_aabb()
            if bounds is None:
                continue
            items.append((node, collider, bounds))
            min_x = int(bounds.min_bounds[0] // self.cell_size)
            max_x = int(bounds.max_bounds[0] // self.cell_size)
            min_y = int(bounds.min_bounds[1] // self.cell_size)
            max_y = int(bounds.max_bounds[1] // self.cell_size)
            min_z = int(bounds.min_bounds[2] // self.cell_size)
            max_z = int(bounds.max_bounds[2] // self.cell_size)
            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    for z in range(min_z, max_z + 1):
                        grid.setdefault((x, y, z), []).append((node, collider, bounds))

        collisions = []
        seen = set()
        for candidates in grid.values():
            for index, (first_node, first, first_aabb) in enumerate(candidates):
                for second_node, second, second_aabb in candidates[index + 1:]:
                    pair = tuple(sorted((id(first_node), id(second_node))))
                    if pair in seen:
                        continue
                    if aabb_intersects(first_aabb, second_aabb):
                        seen.add(pair)
                        center_x = (first_aabb.min_bounds[0] + first_aabb.max_bounds[0]) * 0.5
                        center_y = (first_aabb.min_bounds[1] + first_aabb.max_bounds[1]) * 0.5
                        center_z = (first_aabb.min_bounds[2] + first_aabb.max_bounds[2]) * 0.5
                        other_x = (second_aabb.min_bounds[0] + second_aabb.max_bounds[0]) * 0.5
                        other_y = (second_aabb.min_bounds[1] + second_aabb.max_bounds[1]) * 0.5
                        other_z = (second_aabb.min_bounds[2] + second_aabb.max_bounds[2]) * 0.5
                        dx, dy, dz = other_x - center_x, other_y - center_y, other_z - center_z
                        length = (dx * dx + dy * dy + dz * dz) ** 0.5
                        normal = (dx / length, dy / length, dz / length) if length else (1.0, 0.0, 0.0)
                        collisions.append(Collision(first_node, second_node, normal))
        return collisions
