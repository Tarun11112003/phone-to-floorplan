"""Held-out metric evaluation. This module is not imported by reconstruction."""
from __future__ import annotations

import json
import tarfile
from pathlib import Path

import numpy as np


def icl_reference_dimensions(archive: Path) -> np.ndarray:
    vertices, floor_indices = [], set()
    group = ""
    with tarfile.open(archive, "r:gz") as packed:
        with packed.extractfile("living-room.obj") as source:
            for raw in source:
                line = raw.decode("utf-8")
                if line.startswith("v "):
                    vertices.append([float(value) for value in line.split()[1:4]])
                elif line.startswith("g "):
                    group = line[2:].strip()
                elif line.startswith("f ") and group == "cube34_room_floor":
                    floor_indices.update(int(value.split("/")[0]) - 1 for value in line.split()[1:])
    if not floor_indices:
        raise ValueError("ICL room-floor reference group missing")
    floor = np.asarray(vertices)[list(floor_indices)]
    return np.sort(np.ptp(floor[:, [0, 2]], axis=0))


def dimension_metrics(corners: np.ndarray, truth_dimensions: np.ndarray, target_m: float = 0.03) -> dict:
    corners = np.asarray(corners, dtype=float)
    if corners.shape != (4, 2) or not np.isfinite(corners).all():
        raise ValueError("This evaluator only supports a finite four-corner rectangular room")
    edges = np.roll(corners, -1, axis=0) - corners
    lengths = np.linalg.norm(edges, axis=1)
    if np.any(lengths <= 0) or not np.allclose(lengths[:2], lengths[2:], atol=1e-6) or abs(np.dot(edges[0], edges[1])) > 1e-6:
        raise ValueError("Expected an orthogonal rectangle")
    predicted, truth = np.sort(lengths[:2]), np.sort(truth_dimensions)
    if truth.shape != (2,) or np.any(truth <= 0) or not np.isfinite(truth).all():
        raise ValueError("Expected two positive reference dimensions")
    errors = np.abs(predicted - truth)
    return {
        "evaluation_scope": "one synthetic rectangular room; dimension-only comparison",
        "independent_dimensions": 2, "predicted_dimensions_m": predicted.tolist(),
        "reference_dimensions_m": truth.tolist(), "absolute_errors_m": errors.tolist(),
        "max_dimension_error_m": float(errors.max()), "mean_dimension_error_m": float(errors.mean()),
        "floor_area_error_m2": float(abs(np.prod(predicted) - np.prod(truth))),
        "target_dimension_error_m": target_m, "dimension_target_met_on_this_case": bool(errors.max() <= target_m),
        "global_corner_error_m": None, "real_phone_cm_accuracy_validated": False,
        "alignment": "sort two rectangle side lengths; no scaling fitted to reference",
    }


def trajectory_metrics(trajectory_path: Path, reference_path: Path) -> dict:
    estimated = json.loads(trajectory_path.read_text(encoding="utf-8"))
    truth = np.loadtxt(reference_path)
    by_id = {int(row[0]): row[1:4] for row in truth}
    matching = [row for row in estimated if row["frame_id"] in by_id]
    if len(matching) < 3:
        raise ValueError("Too few matching trajectory timestamps")
    a = np.asarray([row["camera_to_first"] for row in matching])[:, :3, 3]
    b = np.asarray([by_id[row["frame_id"]] for row in matching]).copy()
    # ICL native negative fy defines a y-up camera. RGB-D tracker explicitly
    # uses positive fy/y-down, so change handedness before rigid alignment.
    b[:, 1] *= -1
    ac, bc = a.mean(axis=0), b.mean(axis=0)
    u, _, vt = np.linalg.svd((a - ac).T @ (b - bc))
    correction = np.eye(3)
    correction[-1, -1] = np.linalg.det(u @ vt)
    rotation = u @ correction @ vt
    errors = np.linalg.norm((a - ac) @ rotation + bc - b, axis=1)
    return {"matched_frames": len(matching), "unmatched_estimated_frames": len(estimated) - len(matching), "alignment": "fixed native-y reflection, then SE(3) only; scale held at 1", "ate_rmse_m": float(np.sqrt(np.mean(errors**2))), "ate_median_m": float(np.median(errors)), "ate_p95_m": float(np.percentile(errors, 95)), "ate_max_m": float(errors.max())}


def evaluate_icl(plan_path: Path, mesh_archive: Path, output: Path, trajectory: Path | None = None, trajectory_truth: Path | None = None) -> dict:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if len(plan["rooms"]) != 1 or plan["rooms"][0]["metric_status"] == "unscaled":
        raise ValueError("This benchmark requires exactly one metric room")
    result = dimension_metrics(plan["rooms"][0]["corners"], icl_reference_dimensions(mesh_archive))
    if trajectory is not None and trajectory_truth is not None:
        result["trajectory"] = trajectory_metrics(trajectory, trajectory_truth)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
