"""Image-ground projection and rigid room alignment."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from shapely.geometry import Polygon


class GeometryError(ValueError):
    pass


@dataclass(frozen=True)
class Camera:
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    height_m: float
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0

    @classmethod
    def from_dict(cls, value: dict) -> "Camera":
        required = ("width", "height", "fx", "fy", "cx", "cy")
        absent = [key for key in required if key not in value]
        if absent:
            raise GeometryError(f"Missing camera values: {', '.join(absent)}")
        camera = cls(
            width=int(value["width"]), height=int(value["height"]),
            fx=float(value["fx"]), fy=float(value["fy"]),
            cx=float(value["cx"]), cy=float(value["cy"]),
            height_m=float(value.get("height_m", 1.0)),
            yaw_deg=float(value.get("yaw_deg", 0.0)),
            pitch_deg=float(value.get("pitch_deg", 0.0)),
        )
        if camera.width <= 0 or camera.height <= 0 or camera.fx <= 0 or camera.fy <= 0 or camera.height_m <= 0:
            raise GeometryError("Camera dimensions, focal lengths, and height must be positive")
        return camera

    def axes(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        yaw = math.radians(self.yaw_deg)
        pitch = math.radians(self.pitch_deg)
        right = np.array([math.cos(yaw), -math.sin(yaw), 0.0])
        forward = np.array([math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), math.sin(pitch)])
        down = np.cross(forward, right)
        return right, down, forward

    def floor_point(self, pixel: list[float] | tuple[float, float]) -> tuple[float, float]:
        u, v = float(pixel[0]), float(pixel[1])
        if not (0 <= u < self.width and 0 <= v < self.height):
            raise GeometryError(f"Floor corner {pixel} lies outside the image")
        right, down, forward = self.axes()
        ray = right * ((u - self.cx) / self.fx) + down * ((v - self.cy) / self.fy) + forward
        if ray[2] >= -1e-6:
            raise GeometryError(f"Floor corner {pixel} does not intersect the floor below the camera")
        point = ray * (-self.height_m / ray[2])
        return float(point[0]), float(point[1])

    def project_floor(self, point: tuple[float, float]) -> tuple[float, float]:
        right, down, forward = self.axes()
        relative = np.array([point[0], point[1], -self.height_m], dtype=float)
        depth = float(relative @ forward)
        if depth <= 0:
            raise GeometryError("Point is behind the camera")
        return self.cx + self.fx * float(relative @ right) / depth, self.cy + self.fy * float(relative @ down) / depth


def validated_polygon(points: list[tuple[float, float]]) -> Polygon:
    polygon = Polygon(points)
    if len(points) < 3 or not polygon.is_valid or polygon.area < 0.01:
        raise GeometryError("Room corners must form a simple polygon of nonzero area")
    return polygon


def rigid_alignment(source: list[list[float]], target: list[list[float]]) -> tuple[np.ndarray, np.ndarray, float]:
    """Return a proper 2D rigid transform and the anchor RMS residual."""
    src = np.asarray(source, dtype=float)
    dst = np.asarray(target, dtype=float)
    if src.shape != dst.shape or src.ndim != 2 or src.shape[1] != 2 or len(src) < 2:
        raise GeometryError("Stitching needs at least two corresponding 2D points")
    src_mean, dst_mean = src.mean(axis=0), dst.mean(axis=0)
    centered = src - src_mean
    if np.linalg.matrix_rank(centered) < 1:
        raise GeometryError("Stitch anchors are coincident")
    u, _, vt = np.linalg.svd(centered.T @ (dst - dst_mean))
    sign = np.linalg.det(u @ vt)
    rotation = u @ np.diag([1.0, sign]) @ vt
    translation = dst_mean - src_mean @ rotation
    residual = float(np.sqrt(np.mean(np.sum((src @ rotation + translation - dst) ** 2, axis=1))))
    return rotation, translation, residual


def transform_points(points: list[tuple[float, float]] | list[list[float]], rotation: np.ndarray, translation: np.ndarray) -> list[tuple[float, float]]:
    transformed = np.asarray(points, dtype=float) @ rotation + translation
    return [(float(x), float(y)) for x, y in transformed]
