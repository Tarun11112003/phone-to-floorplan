"""Collect the recorded local benchmark artifacts into a small reviewable JSON."""
import importlib.metadata
import json
from pathlib import Path


def read(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sfm(path: str):
    value = read(path)
    keys = ["input_images", "registered_images", "registered_fraction", "sparse_points", "metric_scale", "floor_plan_ready", "matching_method"]
    return {key: value[key] for key in keys if key in value}


if __name__ == "__main__":
    oracle = read("demo/icl_benchmark/benchmark.json")
    rgbd = read("demo/icl_rgbd_refined/rgbd_summary.json")
    result = {
        "recorded_date": "2026-10-05",
        "scope": "development results on ICL-NUIM synthetic living room; no field accuracy claim",
        "rgbd": {key: rgbd[key] for key in ["input_frames", "tracked_frames", "tracked_fraction", "point_count", "floor_plan_ready", "ground_truth_used_for_reconstruction"]},
        "rgbd_evaluation": read("demo/icl_rgbd_refined/evaluation.json"),
        "oracle_component": {key: oracle[key] for key in ["input", "point_count", "noise_sigma_m", "max_edge_error_m", "real_phone_cm_accuracy_validated"]},
        "photos": sfm("demo/icl_photo_sfm/sfm_summary.json"),
        "video_sequential": sfm("demo/icl_rgb_sfm/sfm_summary.json"),
        "video_exhaustive": sfm("demo/icl_video_exhaustive/sfm_summary.json"),
        "versions": {name: importlib.metadata.version(name) for name in ["numpy", "opencv-python-headless", "pycolmap", "Pillow", "Shapely", "ezdxf", "imageio-ffmpeg"]},
    }
    target = Path("benchmarks/results/benchmark_summary.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(target)
