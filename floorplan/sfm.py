"""Optional COLMAP Structure-from-Motion experiment for RGB media.

Its geometry is up to an unknown scale and is intentionally kept separate
from the measured-corner plan until a sound alignment is supplied.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
import subprocess
import re
from pathlib import Path

import imageio_ffmpeg

SFM_RANDOM_SEED = 7

_TWO_VIEW_CONFIG_NAMES = {
    0: "UNDEFINED",
    1: "DEGENERATE",
    2: "CALIBRATED",
    3: "UNCALIBRATED",
    4: "PLANAR",
    5: "PANORAMIC",
    6: "PLANAR_OR_PANORAMIC",
    7: "WATERMARK",
    8: "MULTIPLE",
    9: "CALIBRATED_RIG",
}


def _matching_diagnostics(database: Path, image_count: int) -> dict:
    """Summarize verified pair support without changing COLMAP decisions."""
    max_image_id = 2_147_483_647
    with sqlite3.connect(database) as connection:
        image_names = dict(connection.execute("SELECT image_id, name FROM images"))
        geometries = connection.execute(
            "SELECT pair_id, rows, config FROM two_view_geometries WHERE rows > 0"
        ).fetchall()

    pairs = []
    paired_image_ids = set()
    config_counts = {}
    for pair_id, inliers, config in geometries:
        image_a = pair_id // max_image_id
        image_b = pair_id % max_image_id
        if image_a not in image_names or image_b not in image_names:
            continue
        config = int(config)
        config_name = _TWO_VIEW_CONFIG_NAMES.get(config, f"UNKNOWN_{config}")
        config_counts[config_name] = config_counts.get(config_name, 0) + 1
        paired_image_ids.update((image_a, image_b))
        pairs.append({
            "image_a": image_names[image_a],
            "image_b": image_names[image_b],
            "verified_inliers": int(inliers),
            "geometry_configuration": config_name,
        })
    pairs.sort(key=lambda item: (-item["verified_inliers"], item["image_a"], item["image_b"]))
    inliers = [item["verified_inliers"] for item in pairs]
    return {
        "candidate_image_pairs": image_count * (image_count - 1) // 2,
        "geometrically_verified_pair_count": len(pairs),
        "verified_pair_fraction": len(pairs) / max(1, image_count * (image_count - 1) // 2),
        "max_verified_inliers": max(inliers, default=0),
        "median_verified_inliers": float(statistics.median(inliers)) if inliers else 0.0,
        "verified_geometry_configurations": dict(sorted(config_counts.items())),
        "images_without_verified_pairs": sorted(
            name for image_id, name in image_names.items() if image_id not in paired_image_ids
        ),
        "strongest_verified_pairs": pairs[:10],
    }


def _reconstruction_guidance(result: dict, diagnostics: dict, image_count: int) -> str:
    if result["registered_images"] == 0:
        if diagnostics["geometrically_verified_pair_count"] == 0:
            return (
                "No image pair passed geometric verification. Check sharpness, "
                "texture, overlap, and camera metadata; no 3D model was produced."
            )
        return (
            "Some image pairs passed geometric verification, but COLMAP could "
            "not initialize a stable 3D model. Increase viewpoint baseline and "
            "check camera calibration; verified matches alone do not prove usable parallax."
        )
    if result["registered_images"] < image_count:
        return (
            "A partial sparse model was produced. Review unregistered views and "
            "coverage; this model remains unscaled and is not a floor plan."
        )
    return "All selected images registered; the sparse model remains unscaled and is not a floor plan."


def reconstruct_rgb(source: Path, output: Path, fps: float = 2.0, max_frames: int = 40, camera_model: str = "SIMPLE_RADIAL", camera_params: str = "", matching_mode: str = "auto", quality_selection: bool = False, required_images: list[str] | None = None, camera_grouping: str = 'auto') -> dict:
    try:
        import pycolmap
    except ImportError as exc:
        raise RuntimeError('Install the SfM extra: python -m pip install -e ".[sfm]"') from exc
    source = source.resolve()
    output = output.resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if fps <= 0 or max_frames < 2:
        raise ValueError("fps must be positive and max_frames must be at least 2")
    if matching_mode not in {"auto", "sequential", "exhaustive"}:
        raise ValueError("matching_mode must be auto, sequential or exhaustive")
    if camera_grouping not in {'auto','shared','per_image'}:
        raise ValueError('camera_grouping must be auto, shared or per_image')
    output.mkdir(parents=True, exist_ok=True)
    database = output / "features.db"
    if database.exists():
        raise FileExistsError(f"SfM output already has a database: {database}; use a fresh output directory")
    if source.is_dir():
        images = source
        sequential = False
    else:
        images = output / "frames"
        images.mkdir(exist_ok=True)
        candidate_count = max_frames * 3 if quality_selection else max_frames
        if quality_selection:
            _, duration = imageio_ffmpeg.count_frames_and_secs(str(source))
            fps = min(fps, candidate_count/max(duration,1))
        # Select real input frames and retain their presentation times. An fps
        # filter synthesizes a regular output timeline and loses the original
        # timing needed for variable-rate captures and pose association.
        filter_graph=f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{1/fps})',showinfo"
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "info", "-y", "-i", str(source), "-vf", filter_graph,
                   '-vsync','0',"-frames:v", str(candidate_count), str(images / "frame_%05d.png")]
        decoded=subprocess.run(command, check=True, capture_output=True, text=True,timeout=120)
        times=[float(t) for t in re.findall(r'\bpts_time:([-+\d.eE]+)',decoded.stderr)]
        files=sorted(images.glob('frame_*.png'))
        if len(times)<len(files): raise ValueError('FFmpeg did not report source presentation times')
        records=[dict(image=p.name,source_timestamp_s=t,source=str(source)) for p,t in zip(files,times)]
        (output/'video_frame_mapping.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        sequential = True
    if quality_selection:
        import cv2
        import numpy as np
        from PIL import Image, ImageOps
        candidates = sorted(p for p in images.iterdir() if p.suffix.lower() in {'.jpg','.jpeg','.png'})
        if not candidates:
            raise ValueError('At least two usable overlapping images are required')
        selected = output/'selected_images'; selected.mkdir()
        quality = []
        # Temporal bins retain spatial coverage; choose sharpest view per bin.
        for group in np.array_split(np.asarray(candidates,dtype=object),min(max_frames,len(candidates))):
            scored = []
            for path in group:
                with Image.open(path) as source_image:
                    image = ImageOps.exif_transpose(source_image).convert('RGB')
                    gray = cv2.cvtColor(np.asarray(image.resize((320,240))),cv2.COLOR_RGB2GRAY)
                    score = float(cv2.Laplacian(gray,cv2.CV_64F).var())
                    scored.append((score,path,image.copy()))
            if scored:
                score,path,image = max(scored,key=lambda row:row[0])
                quality.extend(dict(image=p.name,sharpness=s,accepted=(p==path and score>=10),
                                    reason='selected' if p==path and score>=10 else
                                           ('blurred' if s<10 else 'temporal_bin_budget'))
                               for s,p,_ in scored)
                if score >= 10: image.save(selected/path.name,exif=image.getexif())
        for name in required_images or []:
            path=images/name
            if not path.is_file():
                raise ValueError(f'Measured control view is missing: {name}')
            with Image.open(path) as image:
                normalized=ImageOps.exif_transpose(image).convert('RGB')
                normalized.save(selected/path.name,exif=normalized.getexif())
        (output/'selection.json').write_text(json.dumps(quality,indent=2),encoding='utf-8')
        images = selected
    image_count = sum(1 for item in images.iterdir() if item.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if matching_mode != "auto":
        sequential = matching_mode == "sequential"
    if image_count < 2:
        raise ValueError("At least two usable overlapping images are required after quality selection")
    extraction = pycolmap.FeatureExtractionOptions(num_threads=1)
    matching = pycolmap.FeatureMatchingOptions(num_threads=1)
    verification = pycolmap.TwoViewGeometryOptions()
    verification.ransac.random_seed = SFM_RANDOM_SEED
    reader = pycolmap.ImageReaderOptions(camera_model=camera_model, camera_params=camera_params)
    if camera_grouping=='per_image' and camera_params:
        raise ValueError('Explicit shared camera parameters conflict with per_image grouping')
    mode = (pycolmap.CameraMode.SINGLE if camera_params or camera_grouping=='shared'
            or (camera_grouping=='auto' and not quality_selection)
            else pycolmap.CameraMode.PER_IMAGE if camera_grouping=='per_image'
            else pycolmap.CameraMode.AUTO)
    image_names = sorted(
        item.name for item in images.iterdir()
        if item.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    pycolmap.extract_features(database, images, image_names=image_names, camera_mode=mode,
                              reader_options=reader, extraction_options=extraction,
                              device=pycolmap.Device.cpu)
    if sequential:
        pycolmap.match_sequential(database, matching_options=matching, verification_options=verification,
                                  device=pycolmap.Device.cpu)
    else:
        pycolmap.match_exhaustive(database, matching_options=matching, verification_options=verification,
                                 device=pycolmap.Device.cpu)
    matching_diagnostics = _matching_diagnostics(database, image_count)
    sparse = output / "sparse"
    sparse.mkdir(exist_ok=True)
    options = pycolmap.IncrementalPipelineOptions(num_threads=1, random_seed=SFM_RANDOM_SEED)
    options.mapper.num_threads = 1
    options.mapper.random_seed = SFM_RANDOM_SEED
    options.triangulation.random_seed = SFM_RANDOM_SEED
    options.min_model_size = min(options.min_model_size,image_count)
    if image_count == 2:
        options.triangulation.ignore_two_view_tracks = False
    if camera_params:
        # Explicit calibration is a measurement, not a free optimization variable.
        options.ba_refine_focal_length = False
        options.ba_refine_extra_params = False
        options.mapper.abs_pose_refine_focal_length = False
        options.mapper.abs_pose_refine_extra_params = False
    models = pycolmap.incremental_mapping(database, images, sparse, options=options)
    if not models:
        result = {"status": "no_model", "input_images": image_count, "registered_images": 0, "registered_fraction": 0.0, "sparse_points": 0, "metric_scale": False, "floor_plan_ready": False, "camera_model": camera_model, "camera_params": camera_params}
    else:
        model_id, best = max(models.items(), key=lambda item: item[1].num_reg_images())
        best.export_PLY(output / "sparse.ply")
        fraction = best.num_reg_images() / image_count
        result = {"status": "reconstructed" if fraction >= 0.9 else "partial", "input_images": image_count, "registered_images": best.num_reg_images(), "registered_fraction": fraction, "sparse_points": best.num_points3D(), "metric_scale": False, "floor_plan_ready": False, "camera_model": camera_model, "camera_params": camera_params, "model_directory": str(sparse / str(model_id)), "point_cloud": str(output / "sparse.ply")}
    result["matching_method"] = "sequential" if sequential else "exhaustive"
    result["feature_extraction_threads"] = 1
    result["mapping_threads"] = 1
    result['matching_threads']=1
    result["feature_extraction_order"] = image_names
    result["random_seed"] = SFM_RANDOM_SEED
    result["seeded_stages"] = ["two_view_ransac", "incremental_mapper", "triangulator"]
    result["matching_diagnostics"] = matching_diagnostics
    result["reconstruction_guidance"] = _reconstruction_guidance(result, matching_diagnostics, image_count)
    result['images_directory'] = str(images)
    result['calibration_fixed'] = bool(camera_params)
    result['camera_grouping']=camera_grouping
    result['camera_mode']=mode.name
    result['minimum_model_size'] = options.min_model_size
    result['two_view_tracks_enabled'] = not options.triangulation.ignore_two_view_tracks
    (output / "sfm_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
