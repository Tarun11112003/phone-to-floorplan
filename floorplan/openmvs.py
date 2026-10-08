"""Optional external OpenMVS CPU backend; no reference geometry enters inference."""
from __future__ import annotations

import json
import subprocess
import hashlib
import time
from pathlib import Path

import numpy as np


def reconstruct_openmvs(model_path, images_path, output, references, *, ordered_capture=False, binary_dir=None,runtime_budget_s=600):
    import pycolmap
    import open3d as o3d
    from .dense import measured_scale, camera_path_quality
    from .layout import weighted_voxels, extract_layout, export_layout
    from .rgbd import _fit_planes

    output = Path(output).resolve()
    deadline=time.perf_counter()+runtime_budget_s
    if runtime_budget_s<=0: raise ValueError('Runtime budget must be positive')
    output.mkdir(parents=True, exist_ok=True)
    model = pycolmap.Reconstruction(str(model_path))
    registered=model.num_reg_images()
    if registered<3:
        # Three-view OpenMVS fusion cannot run on a two-photo room.
        from .dense import reconstruct_dense
        return reconstruct_dense(Path(model_path),Path(images_path),output,references,ordered_capture=ordered_capture)
    binary_dir = Path(binary_dir or Path(__file__).resolve().parents[1]/'.tools/openmvs/vc17/x64/Release').resolve()
    for name in ('InterfaceCOLMAP', 'DensifyPointCloud'):
        if not (binary_dir/f'{name}.exe').is_file():
            raise ValueError('OpenMVS CPU binaries missing; run scripts/install_openmvs.py')
    scale, evidence = measured_scale(model, references)
    quality = camera_path_quality(model, scale, ordered_capture)
    if not quality['passed']:
        result = dict(status='incomplete_geometry', reason='Discontinuous camera trajectory; inspect matching or capture gaps',
                      floor_plan_ready=False, accuracy_validated=False, camera_path_quality=quality,
                      metric_scale=scale, scale_evidence=evidence, backend='openmvs_cpu')
        (output/'dense_summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        return result
    scene = output/'openmvs'
    scene.mkdir()
    undistorted = scene/'colmap'
    pycolmap.undistort_images(str(undistorted), str(model_path), str(images_path), num_threads=4)
    commands = [
        [str(binary_dir/'InterfaceCOLMAP.exe'), '-i', str(undistorted), '-o', 'scene.mvs', '--image-folder', str(undistorted/'images'), '--max-threads', '4'],
        [str(binary_dir/'DensifyPointCloud.exe'), '-i', 'scene.mvs', '-o', 'scene_dense.mvs', '--max-threads', '4',
         '--resolution-level', '0', '--max-resolution', '640', '--min-resolution', '160',
         '--number-views', str(min(5,registered-1)), '--number-views-fuse', str(min(3,registered)), '--tower-mode', '0', '--crop-to-roi', '0', '--estimate-roi', '0'],
        [str(binary_dir/'DensifyPointCloud.exe'), '-i', 'scene_dense.mvs', '-o', 'visibility.mvs',
         '--filter-point-cloud', '-1', '--max-threads', '4'],
    ]
    (scene/'commands.json').write_text(json.dumps(commands, indent=2), encoding='utf-8')
    stages = []
    for index, command in enumerate(commands):
        started = time.perf_counter()
        with (scene/f'stage_{index}.log').open('w', encoding='utf-8') as log:
            remaining=deadline-time.perf_counter()
            if remaining<=0: raise TimeoutError('OpenMVS processing budget exceeded')
            subprocess.run(command, cwd=scene, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=remaining)
        stages.append(dict(executable=Path(command[0]).name,
                           executable_sha256=hashlib.sha256(Path(command[0]).read_bytes()).hexdigest(),
                           runtime_s=time.perf_counter()-started))
        (scene/'stages.json').write_text(json.dumps(stages, indent=2), encoding='utf-8')
    cloud = o3d.io.read_point_cloud(str(scene/'visibility_filtered.ply'))
    raw = np.asarray(cloud.points)*scale
    if len(raw) < 1000 or not np.isfinite(raw).all():
        raise ValueError('OpenMVS produced insufficient finite dense geometry')
    colors = np.asarray(cloud.colors)*255 if cloud.has_colors() else np.full_like(raw, 128)
    points, rgb, _ = weighted_voxels(raw, colors)
    np.savez_compressed(output/'cloud.npz', points=points, rgb=rgb)
    images = sorted(model.images.values(), key=lambda image: image.name)
    centers = np.array([image.projection_center()*scale for image in images])
    np.save(output/'camera_centers.npy', centers)
    result = dict(backend='openmvs_cpu', metric_scale=scale, scale_evidence=evidence,
                  point_count=len(points), floor_plan_ready=False, accuracy_validated=False, camera_path_quality=quality,
                  external_stages=stages)
    try:
        down = images[0].cam_from_world().rotation.matrix().T[:, 1]
        rooms, metadata = extract_layout(points, _fit_planes(points), centers, down,
                                        path_breaks=() if ordered_capture else range(1, len(centers)))
        metadata.update(ordered_capture=ordered_capture, scale_evidence=evidence)
        (output/'layout_evidence.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        export_layout(rooms, metadata, output, 'reference_scaled')
        result.update(status='partial' if metadata['unclosed_geometry'] else 'proposal_requires_review',
                      floor_plan_ready=not metadata['unclosed_geometry'], plan_produced=True,
                      camera_center_coverage_fraction=metadata['camera_center_coverage_fraction'])
    except ValueError as exc:
        result.update(status='incomplete_geometry', reason=str(exc))
    (output/'dense_summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
