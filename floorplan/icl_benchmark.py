"""Reproducible, idealized metric wall-scan benchmark using ICL-NUIM.

The named wall mesh is used to simulate a LiDAR point cloud; the named floor
mesh is opened only by the evaluator. This is an oracle-semantic benchmark,
not a phone capture or an end-to-end layout detector.
"""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import ezdxf
import numpy as np


def _parse_obj(path: Path) -> tuple[np.ndarray, dict[str, list[list[int]]]]:
    vertices: list[list[float]] = []
    groups: dict[str, list[list[int]]] = {}
    group = ""
    with path.open(encoding="utf-8", errors="replace") as source:
        for line in source:
            if line.startswith("v "):
                vertices.append([float(value) for value in line.split()[1:4]])
            elif line.startswith("g "):
                group = line[2:].strip()
            elif line.startswith("f "):
                face = [int(value.split("/")[0]) - 1 for value in line.split()[1:]]
                if len(face) >= 3:
                    groups.setdefault(group, []).extend([[face[0], face[i], face[i + 1]] for i in range(1, len(face) - 1)])
    return np.asarray(vertices, dtype=float), groups


def _sample_faces(vertices: np.ndarray, faces: list[list[int]], count: int, rng: np.random.Generator) -> np.ndarray:
    triangles = vertices[np.asarray(faces, dtype=int)]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    areas = np.linalg.norm(cross, axis=1) / 2
    indices = rng.choice(len(triangles), count, p=areas / areas.sum())
    chosen = triangles[indices]
    r1 = np.sqrt(rng.random(count))[:, None]
    r2 = rng.random(count)[:, None]
    return (1 - r1) * chosen[:, 0] + r1 * (1 - r2) * chosen[:, 1] + r1 * r2 * chosen[:, 2]


def _outer_wall_coordinate(values: np.ndarray, side: str) -> float:
    # Dense orthogonal walls form extreme-coordinate modes. The 5th/95th
    # percentiles reject isolated simulated outliers; local medians reject
    # depth noise. This assumes a complete, roughly axis-aligned room scan.
    q = float(np.percentile(values, 5 if side == "low" else 95))
    nearby = values[np.abs(values - q) < 0.06]
    if len(nearby) < 100:
        raise ValueError("Insufficient support for an outer wall")
    return float(np.median(nearby))


def estimate_rectangle(points: np.ndarray) -> list[list[float]]:
    """Estimate x/z room bounds from semantically filtered wall points (y up)."""
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 1000 or not np.isfinite(points).all():
        raise ValueError("Expected at least 1000 finite XYZ wall points")
    low_y, high_y = np.percentile(points[:, 1], [1, 99])
    mid = points[(points[:, 1] > low_y + 0.25) & (points[:, 1] < high_y - 0.25)]
    if len(mid) < 1000:
        raise ValueError("Too few vertical wall observations")
    x0, x1 = (_outer_wall_coordinate(mid[:, 0], side) for side in ("low", "high"))
    z0, z1 = (_outer_wall_coordinate(mid[:, 2], side) for side in ("low", "high"))
    if x1 - x0 < 0.5 or z1 - z0 < 0.5:
        raise ValueError("Degenerate room dimensions")
    return [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]


def _write_plan(corners: list[list[float]], output: Path) -> None:
    x0, z0 = corners[0]
    x1, z1 = corners[2]
    width, depth = x1 - x0, z1 - z0
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="750" height="750" viewBox="0 0 750 750">
<rect width="100%" height="100%" fill="white"/>
<rect x="90" y="90" width="{width*105:.2f}" height="{depth*105:.2f}" fill="#edf5fa" stroke="#18364c" stroke-width="4"/>
<text x="{90+width*52.5:.1f}" y="75" text-anchor="middle" font-family="Arial" font-size="18">{width:.3f} m</text>
<text x="20" y="{90+depth*52.5:.1f}" font-family="Arial" font-size="18">{depth:.3f} m</text>
<text x="90" y="{110+depth*105:.1f}" font-family="Arial" font-size="16">ICL-NUIM simulated wall scan</text>
</svg>'''
    (output / "plan.svg").write_text(svg, encoding="utf-8")
    document = ezdxf.new("R2010")
    document.header["$INSUNITS"] = 6
    document.modelspace().add_lwpolyline(corners, close=True, dxfattribs={"layer": "ROOM_WALL_FACES"})
    document.saveas(output / "plan.dxf")


def run_icl_benchmark(archive: Path, output: Path, *, seed: int = 42, points_count: int = 30000, noise_sigma_m: float = 0.008) -> dict:
    """Sample walls, estimate layout, then compare against withheld floor mesh."""
    if points_count < 5000 or noise_sigma_m < 0:
        raise ValueError("At least 5000 points and nonnegative noise are required")
    output.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as packed:
        with packed.extractfile("living-room.obj") as source:
            obj_path = output / "living-room.obj"
            obj_path.write_bytes(source.read())
    vertices, groups = _parse_obj(obj_path)
    obj_path.unlink()
    wall_faces = groups["cube34_room_wall1"] + groups["cube34_room_walls"]
    floor_faces = groups["cube34_room_floor"]
    rng = np.random.default_rng(seed)
    observations = _sample_faces(vertices, wall_faces, points_count, rng)
    observations += rng.normal(0, noise_sigma_m, observations.shape)
    # Isolated return errors; these are not clustered furniture or missing walls.
    outliers = rng.choice(points_count, int(points_count * 0.02), replace=False)
    observations[outliers] += rng.uniform(-0.4, 0.4, (len(outliers), 3))
    np.save(output / "wall_scan.npy", observations.astype(np.float32))
    predicted = estimate_rectangle(observations)
    floor = vertices[np.unique(np.asarray(floor_faces).ravel())]
    true_x0, true_x1 = float(floor[:, 0].min()), float(floor[:, 0].max())
    true_z0, true_z1 = float(floor[:, 2].min()), float(floor[:, 2].max())
    truth = [[true_x0, true_z0], [true_x1, true_z0], [true_x1, true_z1], [true_x0, true_z1]]
    predicted_width = predicted[1][0] - predicted[0][0]
    predicted_depth = predicted[2][1] - predicted[1][1]
    true_width, true_depth = true_x1 - true_x0, true_z1 - true_z0
    metrics = {
        "source": "ICL-NUIM living room surface mesh, CC BY 3.0",
        "input": "simulated complete, semantically filtered wall point cloud",
        "ground_truth": "separate room-floor mesh group; not supplied to estimator",
        "metric_status": "simulated_metric_scan",
        "seed": seed, "point_count": points_count, "noise_sigma_m": noise_sigma_m,
        "predicted_corners_xz_m": predicted, "ground_truth_corners_xz_m": truth,
        "predicted_width_m": predicted_width, "ground_truth_width_m": true_width,
        "predicted_depth_m": predicted_depth, "ground_truth_depth_m": true_depth,
        "width_error_m": abs(predicted_width - true_width),
        "depth_error_m": abs(predicted_depth - true_depth),
        "max_edge_error_m": max(abs(predicted_width - true_width), abs(predicted_depth - true_depth)),
        "floor_area_error_m2": abs(predicted_width * predicted_depth - true_width * true_depth),
        "real_phone_cm_accuracy_validated": False,
    }
    (output / "benchmark.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    _write_plan(predicted, output)
    return metrics
