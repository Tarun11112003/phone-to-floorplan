"""Optional COLMAP Structure-from-Motion experiment for RGB media.

Its geometry is up to an unknown scale and is intentionally kept separate
from the measured-corner plan until a sound alignment is supplied.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import imageio_ffmpeg


def reconstruct_rgb(source: Path, output: Path, fps: float = 2.0, max_frames: int = 40, camera_model: str = "SIMPLE_RADIAL", camera_params: str = "", matching_mode: str = "auto", quality_selection: bool = False, required_images: list[str] | None = None) -> dict:
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
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(source), "-vf", f"fps={fps}", "-frames:v", str(candidate_count), str(images / "frame_%05d.png")]
        subprocess.run(command, check=True, capture_output=True, text=True)
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
                quality.append({'image':path.name,'sharpness':score,'accepted':score>=10})
                if score >= 10: image.save(selected/path.name)
        for name in required_images or []:
            path=images/name
            if not path.is_file():
                raise ValueError(f'Measured control view is missing: {name}')
            with Image.open(path) as image:
                ImageOps.exif_transpose(image).convert('RGB').save(selected/path.name)
        (output/'selection.json').write_text(json.dumps(quality,indent=2),encoding='utf-8')
        images = selected
    image_count = sum(1 for item in images.iterdir() if item.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if matching_mode != "auto":
        sequential = matching_mode == "sequential"
    if image_count < 2:
        raise ValueError("At least two usable overlapping images are required after quality selection")
    extraction = pycolmap.FeatureExtractionOptions(num_threads=4)
    matching = pycolmap.FeatureMatchingOptions(num_threads=4)
    reader = pycolmap.ImageReaderOptions(camera_model=camera_model, camera_params=camera_params)
    mode = pycolmap.CameraMode.SINGLE if camera_params or not quality_selection else pycolmap.CameraMode.AUTO
    pycolmap.extract_features(database, images, camera_mode=mode, reader_options=reader, extraction_options=extraction, device=pycolmap.Device.cpu)
    if sequential:
        pycolmap.match_sequential(database, matching_options=matching, device=pycolmap.Device.cpu)
    else:
        pycolmap.match_exhaustive(database, matching_options=matching, device=pycolmap.Device.cpu)
    sparse = output / "sparse"
    sparse.mkdir(exist_ok=True)
    options = pycolmap.IncrementalPipelineOptions(num_threads=4, random_seed=7)
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
    result['images_directory'] = str(images)
    result['calibration_fixed'] = bool(camera_params)
    result['minimum_model_size'] = options.min_model_size
    result['two_view_tracks_enabled'] = not options.triangulation.ignore_two_view_tracks
    (output / "sfm_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
