import math
from typing import List, Optional, Tuple


class Matrix4:
    """Column-major 4x4 matrix with TRS, projection, and view operations."""

    def __init__(self, data: Optional[List[float]] = None):
        if data is not None and len(data) != 16:
            raise ValueError("A 4x4 matrix requires exactly 16 values")
        self.m = list(data) if data is not None else [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ]

    @classmethod
    def identity(cls) -> "Matrix4":
        return cls()

    @classmethod
    def trs(cls, pos: Tuple[float, float, float],
            rot: Tuple[float, float, float],
            scale: Tuple[float, float, float]) -> "Matrix4":
        x, y, z = pos
        rx, ry, rz = (math.radians(value) for value in rot)
        sx, sy, sz = scale

        cx, sx_s = math.cos(rx), math.sin(rx)
        cy, sy_s = math.cos(ry), math.sin(ry)
        cz, sz_s = math.cos(rz), math.sin(rz)

        r00 = cy * cz
        r01 = -cy * sz_s
        r02 = sy_s
        r10 = cz * sx_s * sy_s + cx * sz_s
        r11 = cx * cz - sx_s * sy_s * sz_s
        r12 = -cy * sx_s
        r20 = -cx * cy * sz_s + sx_s * sz_s
        r21 = cz * sx_s + cx * sy_s * sz_s
        r22 = cx * cy

        return cls([
            r00 * sx, r10 * sx, r20 * sx, 0.0,
            r01 * sy, r11 * sy, r21 * sy, 0.0,
            r02 * sz, r12 * sz, r22 * sz, 0.0,
            x, y, z, 1.0,
        ])

    def multiply(self, other: "Matrix4") -> "Matrix4":
        result = [0.0] * 16
        for column in range(4):
            for row in range(4):
                result[column * 4 + row] = sum(
                    self.m[index * 4 + row] * other.m[column * 4 + index]
                    for index in range(4)
                )
        return Matrix4(result)

    def __mul__(self, other: "Matrix4") -> "Matrix4":
        return self.multiply(other)

    def extract_position(self) -> Tuple[float, float, float]:
        return (self.m[12], self.m[13], self.m[14])

    def multiply_point(self, point: Tuple[float, float, float]) -> Tuple[float, float, float]:
        x, y, z = point
        w = self.m[3] * x + self.m[7] * y + self.m[11] * z + self.m[15]
        if abs(w) < 1e-12:
            raise ZeroDivisionError("Point is on the matrix projection's homogeneous plane")
        return (
            (self.m[0] * x + self.m[4] * y + self.m[8] * z + self.m[12]) / w,
            (self.m[1] * x + self.m[5] * y + self.m[9] * z + self.m[13]) / w,
            (self.m[2] * x + self.m[6] * y + self.m[10] * z + self.m[14]) / w,
        )

    def inverse(self) -> "Matrix4":
        augmented = [
            list(self.m[row * 4:(row + 1) * 4])
            + [1.0 if row == column else 0.0 for column in range(4)]
            for row in range(4)
        ]
        for column in range(4):
            pivot = max(range(column, 4), key=lambda row: abs(augmented[row][column]))
            if abs(augmented[pivot][column]) < 1e-12:
                raise ValueError("Matrix is singular and cannot be inverted")
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
            divisor = augmented[column][column]
            augmented[column] = [value / divisor for value in augmented[column]]
            for row in range(4):
                if row == column:
                    continue
                factor = augmented[row][column]
                augmented[row] = [
                    augmented[row][index] - factor * augmented[column][index]
                    for index in range(8)
                ]
        return Matrix4([
            augmented[row][column]
            for row in range(4)
            for column in range(4, 8)
        ])

    @classmethod
    def look_at(cls, eye: Tuple[float, float, float],
                target: Tuple[float, float, float],
                up: Tuple[float, float, float] = (0.0, 1.0, 0.0)) -> "Matrix4":
        ex, ey, ez = eye
        fx, fy, fz = (target[index] - eye[index] for index in range(3))
        length = math.sqrt(fx * fx + fy * fy + fz * fz)
        if length < 1e-12:
            raise ValueError("Camera position and target must be different")
        fx, fy, fz = fx / length, fy / length, fz / length

        ux, uy, uz = up
        sx = fy * uz - fz * uy
        sy = fz * ux - fx * uz
        sz = fx * uy - fy * ux
        length = math.sqrt(sx * sx + sy * sy + sz * sz)
        if length < 1e-12:
            raise ValueError("Camera up vector cannot be parallel to the viewing direction")
        sx, sy, sz = sx / length, sy / length, sz / length

        ux = sy * fz - sz * fy
        uy = sz * fx - sx * fz
        uz = sx * fy - sy * fx
        return cls([
            sx, sy, sz, 0.0,
            ux, uy, uz, 0.0,
            -fx, -fy, -fz, 0.0,
            -(sx * ex + sy * ey + sz * ez),
            -(ux * ex + uy * ey + uz * ez),
            fx * ex + fy * ey + fz * ez,
            1.0,
        ])

    @classmethod
    def orthographic(cls, left: float, right: float,
                     bottom: float, top: float,
                     near: float, far: float) -> "Matrix4":
        width = right - left
        height = top - bottom
        depth = far - near
        if width <= 0 or height <= 0 or depth <= 0:
            raise ValueError("Orthographic bounds must be ordered and have non-zero depth")
        return cls([
            2.0 / width, 0.0, 0.0, 0.0,
            0.0, 2.0 / height, 0.0, 0.0,
            0.0, 0.0, -2.0 / depth, 0.0,
            -(right + left) / width,
            -(top + bottom) / height,
            -(far + near) / depth,
            1.0,
        ])

    @classmethod
    def perspective(cls, fov_degrees: float, aspect_ratio: float,
                    near: float, far: float) -> "Matrix4":
        if not 0 < fov_degrees < 180:
            raise ValueError("Perspective field of view must be between 0 and 180 degrees")
        if aspect_ratio <= 0:
            raise ValueError("Aspect ratio must be positive")
        if near <= 0 or far <= near:
            raise ValueError("Perspective requires 0 < near < far")
        f = 1.0 / math.tan(math.radians(fov_degrees) / 2.0)
        return cls([
            f / aspect_ratio, 0.0, 0.0, 0.0,
            0.0, f, 0.0, 0.0,
            0.0, 0.0, (far + near) / (near - far), -1.0,
            0.0, 0.0, (2.0 * far * near) / (near - far), 0.0,
        ])


class AABB:
    """Axis-aligned bounding box used for culling and broad-phase collision."""

    def __init__(self,
                 min_bounds: Tuple[float, float, float] = (-0.5, -0.5, -0.5),
                 max_bounds: Tuple[float, float, float] = (0.5, 0.5, 0.5)):
        if any(min_bounds[index] > max_bounds[index] for index in range(3)):
            raise ValueError("AABB minimum bounds must not exceed maximum bounds")
        self.min_bounds = tuple(min_bounds)
        self.max_bounds = tuple(max_bounds)

    def transform(self, matrix: Matrix4) -> "AABB":
        corners = [
            (
                matrix.m[0] * x + matrix.m[4] * y + matrix.m[8] * z + matrix.m[12],
                matrix.m[1] * x + matrix.m[5] * y + matrix.m[9] * z + matrix.m[13],
                matrix.m[2] * x + matrix.m[6] * y + matrix.m[10] * z + matrix.m[14],
            )
            for x in (self.min_bounds[0], self.max_bounds[0])
            for y in (self.min_bounds[1], self.max_bounds[1])
            for z in (self.min_bounds[2], self.max_bounds[2])
        ]
        return AABB(
            tuple(min(corner[index] for corner in corners) for index in range(3)),
            tuple(max(corner[index] for corner in corners) for index in range(3)),
        )
