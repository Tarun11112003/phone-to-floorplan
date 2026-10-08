"""Isolated CPU LightGlue+DISK comparison using only input RGB.

Experimental dependencies live under .tools/lightglue_experiment/site and are
deliberately not part of the default installation. After installing the pinned
experiment dependencies, run:

    python scripts/experimental_lightglue_sfm.py --group start0

This script builds a fresh COLMAP database and mapper model per run. It does not
use depth, poses, camera calibration, survey references, or another run's model.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import threading
import time
from pathlib import Path

import numpy as np
import psutil


LIGHTGLUE_COMMIT = "eb42fee2d71449efb0aa5c10549752b5d75384d8"
DISK_SHA256 = "9c2ee4ded238892dfa51569941372601e35e4a74aa6f84ea80053d2ab1c07abe"
MATCHER_SHA256 = "b5b21d47ea24f2c5e501aec9c91b9716e4c8c3429a4dc1e615c133c4c9378335"
SEED = 7


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class _PeakRSS:
    def __init__(self):
        self.process = psutil.Process()
        self.peak = 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self):
        while not self.stop.is_set():
            try:
                self.peak = max(self.peak, self.process.memory_info().rss)
            except psutil.Error:
                pass
            self.stop.wait(.1)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=1)


def run(group: str, root: Path, output: Path, experiment_site: Path) -> dict:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(experiment_site.resolve()))
    import cv2
    import pycolmap
    import torch
    import torchvision
    import kornia
    from lightglue import DISK, LightGlue
    from lightglue.utils import load_image

    image_dir = root / "rgb" / group
    image_paths = sorted(image_dir.glob("*.png"))
    if len(image_paths) != 4:
        raise ValueError(f"Expected exactly four RGB images for {group}; found {len(image_paths)}")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Use a fresh output directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    device = torch.device("cpu")
    with _PeakRSS() as memory:
        started = time.perf_counter()
        extractor = DISK(max_num_keypoints=2048).eval().to(device)
        matcher = LightGlue(features="disk").eval().to(device)
        checkpoint_dir = Path(os.environ.get("TORCH_HOME", Path.home() / ".cache/torch")) / "hub" / "checkpoints"
        weights = {
            "disk_extractor": checkpoint_dir / "depth-save.pth",
            "lightglue_matcher": checkpoint_dir / "disk_lightglue_v0-1_arxiv.pth",
        }
        hashes = {name: _sha256(path) for name, path in weights.items()}
        if hashes["disk_extractor"] != DISK_SHA256 or hashes["lightglue_matcher"] != MATCHER_SHA256:
            raise ValueError(f"Pinned matcher checkpoint SHA-256 mismatch: {hashes}")
        model_load_s = time.perf_counter() - started

        feature_records = {}
        for path in image_paths:
            with torch.inference_mode():
                data = extractor.extract(load_image(str(path)).to(device))
            feature_records[path.name] = data

        db_path = output / "features.db"
        pairs_path = output / "pairs.txt"
        names = [path.name for path in image_paths]
        reader = pycolmap.ImageReaderOptions(camera_model="SIMPLE_RADIAL")
        with pycolmap.Database.open(db_path):
            pass
        pycolmap.import_images(db_path, image_dir, camera_mode=pycolmap.CameraMode.SINGLE,
                               image_names=names, options=reader)
        pair_rows = list(itertools.combinations(names, 2))
        pair_lines = [f"{a} {b}" for a, b in pair_rows]
        pairs_path.write_text("\n".join(pair_lines) + "\n", encoding="utf-8")
        pair_matches = []
        match_times = []
        with pycolmap.Database.open(db_path) as database:
            images = {image.name: image for image in database.read_all_images()}
            for name in names:
                feature = feature_records[name]
                points = feature["keypoints"][0].detach().cpu().numpy().astype(np.float32)
                database.write_keypoints(images[name].image_id, points)
            for name_a, name_b in pair_rows:
                t0 = time.perf_counter()
                with torch.inference_mode():
                    prediction = matcher({"image0": feature_records[name_a],
                                          "image1": feature_records[name_b]})
                matches = prediction["matches"][0].detach().cpu().numpy().astype(np.uint32)
                match_times.append(time.perf_counter() - t0)
                image_a, image_b = images[name_a], images[name_b]
                if image_a.image_id > image_b.image_id:
                    matches = matches[:, ::-1].copy()
                    image_a, image_b = image_b, image_a
                database.write_matches(image_a.image_id, image_b.image_id, matches)
                pair_matches.append(dict(image_a=name_a, image_b=name_b,
                                         raw_matches=int(len(matches))))

        verification = pycolmap.TwoViewGeometryOptions()
        verification.ransac.random_seed = SEED
        pycolmap.verify_matches(db_path, pairs_path, options=verification)
        from floorplan.sfm import _matching_diagnostics
        diagnostics = _matching_diagnostics(db_path, len(names))

        sparse = output / "sparse"
        sparse.mkdir()
        options = pycolmap.IncrementalPipelineOptions(num_threads=1, random_seed=SEED)
        options.mapper.num_threads = 1
        options.mapper.random_seed = SEED
        options.triangulation.random_seed = SEED
        options.min_model_size = min(options.min_model_size, len(names))
        models = pycolmap.incremental_mapping(db_path, image_dir, sparse, options=options)
        if models:
            model_id, best = max(models.items(), key=lambda item: item[1].num_reg_images())
            best.export_PLY(output / "sparse.ply")
            registered = best.num_reg_images()
            sparse_points = best.num_points3D()
            status = "reconstructed" if registered / len(names) >= .9 else "partial"
            model_path = str(sparse / str(model_id))
        else:
            registered = sparse_points = 0
            status = "no_model"
            model_path = None

        runtime_s = time.perf_counter() - started
    result = {
        "status": status, "group": group, "input_images": len(names),
        "registered_images": registered, "registered_fraction": registered / len(names),
        "sparse_points": sparse_points, "model_directory": model_path,
        "matcher": "DISK+LightGlue", "lightglue_commit": LIGHTGLUE_COMMIT,
        "checkpoint_sha256": hashes, "device": "cpu", "torch": torch.__version__,
        "torchvision": torchvision.__version__, "kornia": kornia.__version__,
        "camera_model": "SIMPLE_RADIAL", "camera_params": "unknown/unoptimized",
        "matching_pairs": pair_matches, "mean_pair_matching_s": float(np.mean(match_times)),
        "model_load_s": model_load_s, "runtime_s": runtime_s,
        "peak_process_rss_bytes": memory.peak, "seed": SEED,
        "matching_diagnostics": diagnostics,
        "depth_pose_intrinsics_or_survey_used": False,
        "metric_scale": False, "floor_plan_ready": False,
        "warning": "Sparse registration is a matcher experiment, not a dimensioned plan.",
    }
    (output / "sfm_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=("start0", "start80"), required=True)
    parser.add_argument("--root", type=Path, default=Path("demo/lightglue_trial"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--experiment-site", type=Path,
                        default=Path(".tools/lightglue_experiment/site"))
    args = parser.parse_args()
    output = args.out or args.root / "lightglue" / args.group
    result = run(args.group, args.root, output, args.experiment_site)
    print(json.dumps({k: result[k] for k in
                      ("group", "status", "registered_images", "sparse_points",
                       "runtime_s", "peak_process_rss_bytes", "matching_diagnostics")}, indent=2))
    print(f"report: {output / 'sfm_summary.json'}")


if __name__ == "__main__":
    main()
