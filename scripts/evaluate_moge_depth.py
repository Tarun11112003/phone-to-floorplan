"""RGB-only MoGe-2 depth probe against withheld ARKitScenes LiDAR depth.

Run from the repository root with the optional MoGe experiment environment:
    python scripts/evaluate_moge_depth.py --scene 41418140 --views 8

Reference depth is opened only after each RGB prediction has been produced.
This probe is experimental and does not feed its output into floor-plan runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from huggingface_hub import hf_hub_download
from moge.model.v2 import MoGeModel


CHECKPOINT = "Ruicheng/moge-2-vits-normal"
REVISION = "26b477f41595707c5db6770294c0d1721e8ed4ed"
CODE_REVISION = "74fbce054ebed49800de42d0ad0e83495065719a"
CHECKPOINT_SHA256 = "79a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc"


def score_depth(predicted: np.ndarray, reference: np.ndarray,
                valid: np.ndarray) -> dict[str, float | int]:
    """Score raw metres, with no scale/shift fit against reference."""
    mask = valid & np.isfinite(predicted) & (predicted > 0)
    errors = np.abs(predicted[mask] - reference[mask])
    if not errors.size:
        return {"valid_pixels": 0, "mae_m": float("nan"),
                "median_abs_error_m": float("nan"), "signed_bias_m": float("nan")}
    signed = predicted[mask] - reference[mask]
    return {
        "valid_pixels": int(errors.size),
        "mae_m": float(errors.mean()),
        "median_abs_error_m": float(np.median(errors)),
        "signed_bias_m": float(signed.mean()),
    }


def evaluate(scene_dir: Path, views: int, output: Path) -> dict:
    rgb_dir = scene_dir / "lowres_wide"
    depth_dir = scene_dir / "lowres_depth"
    confidence_dir = scene_dir / "confidence"
    common = sorted(p.name for p in rgb_dir.glob("*.png")
                    if (depth_dir / p.name).is_file()
                    and (confidence_dir / p.name).is_file())
    if views < 1 or views > len(common):
        raise ValueError(f"views must be in 1..{len(common)}")
    selected = [common[i] for i in np.unique(
        np.linspace(0, len(common) - 1, views).round().astype(int))]

    started = time.perf_counter()
    checkpoint_path = Path(hf_hub_download(CHECKPOINT, "model.pt", revision=REVISION))
    checkpoint_hash = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    if checkpoint_hash != CHECKPOINT_SHA256:
        raise ValueError(f"MoGe checkpoint hash mismatch: {checkpoint_hash}")
    model = MoGeModel.from_pretrained(checkpoint_path).to("cpu").eval()
    model_load_s = time.perf_counter() - started
    rows = []
    for name in selected:
        rgb = np.asarray(Image.open(rgb_dir / name).convert("RGB")).copy()
        image = torch.from_numpy(rgb).permute(2, 0, 1).float() / 255
        start = time.perf_counter()
        with torch.inference_mode():
            prediction = model.infer(image, use_fp16=False)
        infer_s = time.perf_counter() - start

        # Reference streams are read only after RGB inference is complete.
        reference_mm = cv2.imread(str(depth_dir / name), cv2.IMREAD_UNCHANGED)
        confidence = cv2.imread(str(confidence_dir / name), cv2.IMREAD_UNCHANGED)
        if reference_mm is None or confidence is None:
            raise ValueError(f"Missing synchronized reference for {name}")
        pred = prediction["depth"].detach().cpu().numpy()
        if pred.shape != reference_mm.shape:
            raise ValueError(f"Resolution mismatch for {name}: {pred.shape} vs {reference_mm.shape}")
        reference_m = reference_mm.astype(np.float32) / 1000.0
        valid = (reference_mm > 0) & (confidence >= 1)
        rows.append({"frame": name, "inference_s": infer_s,
                     **score_depth(pred, reference_m, valid)})

    metrics = {}
    for key in ("mae_m", "median_abs_error_m", "signed_bias_m"):
        values = [row[key] for row in rows if np.isfinite(row[key])]
        metrics[key] = float(np.mean(values)) if values else None
    result = {
        "experiment": "moge-2-vits-normal-rgb-only-vs-arkitscenes-depth",
        "scene": scene_dir.name, "views": len(rows),
        "checkpoint": CHECKPOINT, "checkpoint_revision": REVISION,
        "checkpoint_sha256": checkpoint_hash,
        "code_revision": CODE_REVISION, "device": "cpu",
        "reference_scale": "uint16 millimetres to metres",
        "confidence_threshold": 1, "posthoc_scale_fit": False,
        "model_load_s": model_load_s,
        "mean_inference_s": float(np.mean([r["inference_s"] for r in rows])),
        "per_frame": rows, "macro_mean": metrics,
        "interpretation": "Depth-only probe; does not validate room dimensions or floor plans.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="41418140")
    parser.add_argument("--views", type=int, default=8)
    parser.add_argument("--data-root", type=Path, default=Path("datasets/arkitscenes"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    scene_dir = args.data_root / args.scene
    out = args.output or Path("demo/moge_metric_eval") / f"{args.scene}_{args.views}.json"
    result = evaluate(scene_dir, args.views, out)
    print(json.dumps({k: result[k] for k in
                      ("scene", "views", "model_load_s", "mean_inference_s", "macro_mean")},
                     indent=2))
    print(f"report: {out}")


if __name__ == "__main__":
    main()
