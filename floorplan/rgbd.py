"""CPU RGB-D mapping and supported floor-plan proposals.

Inputs are calibrated RGB/depth pairs and optionally disclosed sensor poses.
Reference meshes, room corners and reference trajectories are never read.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from .pipeline import _dxf, _quantities, _svg


def _backproject(pixels: np.ndarray, depths: np.ndarray, k: np.ndarray) -> np.ndarray:
    rays = np.column_stack(((pixels[:, 0] - k[0, 2]) / k[0, 0], (pixels[:, 1] - k[1, 2]) / k[1, 1], np.ones(len(pixels))))
    return rays * depths[:, None]


def _features(image: np.ndarray, depth: np.ndarray, sift, cv2) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    keys, descriptors = sift.detectAndCompute(image, None)
    if descriptors is None:
        raise ValueError("No visual features in frame")
    pixels = np.asarray([key.pt for key in keys])
    rounded = np.rint(pixels).astype(int)
    xs = np.clip(rounded[:, 0], 1, depth.shape[1] - 2)
    ys = np.clip(rounded[:, 1], 1, depth.shape[0] - 2)
    samples = np.stack([depth[ys + dy, xs + dx] for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    # Depth discontinuities make a 2D feature's 3D location ambiguous.
    good = (samples.min(axis=0) > 0.2) & (samples.max(axis=0) - samples.min(axis=0) < 0.1)
    return pixels[good], descriptors[good], np.median(samples[:, good], axis=0)


def _relative_pose(previous, current, k, cv2, source_k=None,*,ordered_motion=True) -> tuple[np.ndarray, dict]:
    pxy, pdesc, pdepth = previous
    cxy, cdesc, cdepth = current
    if len(pdesc) < 20 or len(cdesc) < 20:
        raise ValueError("Too few depth-supported visual features")
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(pdesc, cdesc, k=2)
    matches = [a for pair in pairs if len(pair) == 2 for a, b in [pair] if a.distance < 0.7 * b.distance]
    if len(matches) < 20:
        raise ValueError(f"Only {len(matches)} reliable descriptor matches")
    source_ids = np.asarray([match.queryIdx for match in matches])
    target_ids = np.asarray([match.trainIdx for match in matches])
    xyz = _backproject(pxy[source_ids], pdepth[source_ids], k if source_k is None else source_k)
    uv = cxy[target_ids]
    ok, rvec, tvec, inliers = cv2.solvePnPRansac(xyz, uv, k, None, iterationsCount=200, reprojectionError=2.0, confidence=0.999, flags=cv2.SOLVEPNP_EPNP)
    if not ok or inliers is None or len(inliers) < 20 or len(inliers) / len(matches) < 0.25:
        raise ValueError("PnP did not find a sufficiently supported camera pose")
    ids = inliers.ravel()
    rvec, tvec = cv2.solvePnPRefineLM(xyz[ids], uv[ids], k, None, rvec, tvec)
    rotation, _ = cv2.Rodrigues(rvec)
    # Both frames carry metric depth. Refine the robust visual pose with 3D
    # correspondences so tracking uses target depth as well as source depth.
    target_xyz = _backproject(cxy[target_ids], cdepth[target_ids], k)
    metric_ids = ids
    for _ in range(3):
        distances = np.linalg.norm(xyz @ rotation.T + tvec.ravel() - target_xyz, axis=1)
        metric_ids = np.flatnonzero(distances < 0.04)
        if len(metric_ids) < 20:
            break
        a, b = xyz[metric_ids], target_xyz[metric_ids]
        ac, bc = a.mean(axis=0), b.mean(axis=0)
        u, _, vt = np.linalg.svd((a - ac).T @ (b - bc))
        correction = np.eye(3)
        correction[-1, -1] = np.linalg.det(vt.T @ u.T)
        rotation = vt.T @ correction @ u.T
        tvec = (bc - rotation @ ac).reshape(3, 1)
    rvec, _ = cv2.Rodrigues(rotation)
    if len(metric_ids)<20:
        raise ValueError('Insufficient mutually consistent metric-depth correspondences')
    if ordered_motion and (np.linalg.norm(tvec) > 1.0 or np.linalg.norm(rvec) > np.deg2rad(45)):
        raise ValueError("Implausibly large inter-frame camera motion")
    transform = np.eye(4)
    transform[:3, :3], transform[:3, 3] = rotation, tvec.ravel()
    projected, _ = cv2.projectPoints(xyz[ids], rvec, tvec, k, None)
    residual = np.linalg.norm(projected.reshape(-1, 2) - uv[ids], axis=1)
    if not np.isfinite(residual).all() or np.median(residual)>2.:
        raise ValueError('Metric refinement invalidated the verified reprojection support')
    return transform, {"matches": len(matches), "inliers": len(ids), "metric_inliers": len(metric_ids), "median_reprojection_px": float(np.median(residual))}


def pose_against_registered(current,k,features,calibrations,poses,cv2):
    """Unordered stills may overlap any registered view, not the filename neighbor.

    No small inter-frame motion prior applies to independent photos. Descriptor,
    reprojection and mutually consistent metric-depth checks remain unchanged.
    """
    candidates=[]
    for index in range(max(0,len(features)-24),len(features)):
        if features[index] is None: continue
        try:
            relative,quality=_relative_pose(features[index],current,k,cv2,calibrations[index],ordered_motion=False)
        except ValueError: continue
        candidates.append((quality['metric_inliers'],-quality['median_reprojection_px'],index,relative,quality))
    if not candidates: raise ValueError('No verified overlap with any registered photo view')
    _,_,index,relative,quality=max(candidates,key=lambda item:item[:3])
    return poses[index]@np.linalg.inv(relative),{**quality,'reference_registered_index':index,
                                              'motion_prior':'unordered stills; no small-motion assumption'}


def _fit_planes(points: np.ndarray, seed: int = 7, threshold: float = 0.025) -> list[dict]:
    rng = np.random.default_rng(seed)
    remaining = points[rng.choice(len(points), min(18000, len(points)), replace=False)]
    planes = []
    for _ in range(14):
        if len(remaining) < 500:
            break
        triples = remaining[rng.integers(0, len(remaining), (1024, 3))]
        normals = np.cross(triples[:, 1] - triples[:, 0], triples[:, 2] - triples[:, 0])
        lengths = np.linalg.norm(normals, axis=1)
        good = lengths > 1e-5
        if not np.any(good):
            break
        normals = normals[good] / lengths[good, None]
        offsets = -np.sum(normals * triples[good, 0], axis=1)
        scores = np.concatenate([np.sum(np.abs(remaining @ normals[start:start + 128].T + offsets[start:start + 128]) < threshold, axis=0) for start in range(0, len(normals), 128)])
        best = int(scores.argmax())
        mask = np.abs(remaining @ normals[best] + offsets[best]) < threshold
        if mask.sum() < 250:
            break
        support = remaining[mask]
        center = support.mean(axis=0)
        _, _, vt = np.linalg.svd(support - center, full_matrices=False)
        normal = vt[-1]
        offset = -float(normal @ center)
        planes.append({"normal": normal.tolist(), "offset": offset, "support": int(mask.sum()), "centroid": center.tolist(), "rms_m": float(np.sqrt(np.mean((support @ normal + offset)**2)))})
        remaining = remaining[~mask]
    return planes


def rectangle_from_planes(planes: list[dict]) -> tuple[list[list[float]], dict]:
    """Require opposing observed planes; never close unobserved boundaries."""
    vertical = [p for p in planes if abs(p["normal"][1]) < 0.3]
    if len(vertical) < 4:
        raise ValueError("Fewer than four vertical planes; room boundary coverage is incomplete")
    strongest = max(vertical, key=lambda p: p["support"])
    axis_x = np.asarray(strongest["normal"], dtype=float)
    axis_x[1] = 0
    axis_x /= np.linalg.norm(axis_x)
    axis_z = np.cross(axis_x, [0, 1, 0])
    bounds = []
    selected = []
    for axis in (axis_x, axis_z):
        candidates = []
        for plane in vertical:
            dot = float(np.dot(plane["normal"], axis))
            if abs(dot) > np.cos(np.deg2rad(8)):
                candidates.append((-plane["offset"] / dot, plane))
        negative = [p for p in candidates if p[0] < -0.3]
        positive = [p for p in candidates if p[0] > 0.3]
        if not negative or not positive:
            raise ValueError("No opposing supported walls around the starting camera on both room axes")
        lo = max(negative, key=lambda p: p[1]["support"])
        hi = max(positive, key=lambda p: p[1]["support"])
        bounds.append((lo[0], hi[0]))
        selected.extend([lo[1], hi[1]])
    (x0, x1), (z0, z1) = bounds
    corners = [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]
    return corners, {"axis_x_in_first_camera": axis_x.tolist(), "axis_z_in_first_camera": axis_z.tolist(), "selected_planes": selected, "assumptions": ["single rectangular Manhattan room", "first camera approximately level", "four opposing wall planes visible", "no global loop closure"]}


def retained_path_breaks(retained_indices, original_breaks=()):
    """Retain boundaries after depth/tracking rejection; never invent traversal."""
    boundaries=set(original_breaks)
    return [i for i,(a,b) in enumerate(zip(retained_indices,retained_indices[1:]),start=1)
            if b>a+1 or any(a<boundary<=b for boundary in boundaries)]


def reconstruct_rgbd(manifest_path: Path, output: Path, max_frames: int | None = None) -> dict:
    if max_frames is not None and max_frames < 2:
        raise ValueError("max_frames must be at least two")
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError('Install RGB-D extra: pip install -e ".[rgbd]"') from exc
    cv2.setNumThreads(4)
    cv2.setRNGSeed(7)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    camera = manifest["intrinsics"]
    k = np.array([[camera["fx"], 0, camera["cx"]], [0, camera["fy"], camera["cy"]], [0, 0, 1]], dtype=float)
    frames = manifest["frames"][:max_frames]
    if len(frames) < 2 or not np.isfinite(manifest["depth_scale"]) or manifest["depth_scale"] <= 0:
        raise ValueError("At least two calibrated RGB-D frames and positive depth scale are required")
    if not np.isfinite(k).all() or min(k[0,0], k[1,1]) <= 0 or min(camera['width'], camera['height']) < 3:
        raise ValueError('Invalid finite positive camera calibration')
    if len({str(f['id']) for f in frames}) != len(frames):
        raise ValueError('Frame IDs must be unique')
    times = [f['timestamp_s'] for f in frames if 'timestamp_s' in f]
    if times and (len(times) != len(frames) or not np.isfinite(times).all() or np.any(np.diff(times) <= 0)):
        raise ValueError('Timestamps must be finite and strictly increasing')
    supplied = manifest.get('pose_source') in {'sensor', 'rgb_reconstruction'}
    if any('camera_to_world' in f for f in frames) and not supplied:
        raise ValueError('Supplied poses require explicit sensor or rgb_reconstruction provenance')
    output.mkdir(parents=True, exist_ok=True)
    if (output / "rgbd_summary.json").exists() or (output / "plan.json").exists():
        raise FileExistsError("Use a fresh RGB-D output directory to avoid mixing experiment artifacts")
    # Indoor walls can carry useful low-contrast texture. Geometry verification
    # remains unchanged: descriptor ratio, PnP and metric depth agreement.
    sift = cv2.SIFT_create(nfeatures=2000, contrastThreshold=0.01)
    pose = np.eye(4)
    previous = None
    poses, logs, clouds, colors, feature_history, weights = [], [], [], [], [], []
    previous_k = k
    camera_calibrations=[]
    retained_indices=[]
    failure = None
    skipped = []
    recovery_limit = int(manifest.get('tracking_recovery_frames', 5))
    if not 0 <= recovery_limit <= 30:
        raise ValueError('tracking_recovery_frames must be between 0 and 30')
    consecutive_failures = 0
    for index, frame in enumerate(frames):
        frame_camera = frame.get('intrinsics', camera)
        k = np.array([[frame_camera['fx'], 0, frame_camera['cx']], [0, frame_camera['fy'], frame_camera['cy']], [0,0,1]], float)
        if not np.isfinite(k).all() or min(k[0,0],k[1,1]) <= 0:
            raise ValueError('Invalid per-frame calibration')
        rgb = cv2.imread(str(manifest_path.parent / frame["rgb"]))
        depth_path = manifest_path.parent / frame['depth']
        raw_depth = np.load(depth_path, allow_pickle=False) if depth_path.suffix == '.npy' else cv2.imread(str(depth_path), cv2.IMREAD_UNCHANGED)
        if rgb is None or raw_depth is None:
            raise ValueError(f"Missing RGB-D pair {frame['id']}")
        if rgb.shape[:2] != (frame_camera["height"], frame_camera["width"]) or raw_depth.shape != rgb.shape[:2]:
            raise ValueError("RGB, depth and intrinsics must have the same image dimensions")
        depth = raw_depth.astype(float) / manifest["depth_scale"]
        depth[(depth > manifest.get("depth_max_m", 8.0)) | (depth < 0.2) | ~np.isfinite(depth)] = 0
        confidence = np.ones(depth.shape)
        if frame.get('confidence'):
            confidence = cv2.imread(str(manifest_path.parent / frame['confidence']), cv2.IMREAD_UNCHANGED)
            if confidence is None or confidence.shape != depth.shape:
                raise ValueError('Confidence must match depth dimensions')
            depth[confidence < manifest.get('minimum_confidence', 1)] = 0
        if np.count_nonzero(depth) < 100 or np.count_nonzero(depth[::8,::8]) < 30:
            skipped.append({'frame_id':frame['id'],'reason':'Insufficient valid confident depth'})
            continue
        try:
            if supplied:
                pose = np.asarray(frame['camera_to_world'], float)
                if pose.shape != (4,4) or not np.isfinite(pose).all() or not np.allclose(pose[3], [0,0,0,1]) or not np.allclose(pose[:3,:3].T @ pose[:3,:3], np.eye(3), atol=1e-4) or np.linalg.det(pose[:3,:3]) < 0.99:
                    raise ValueError('Invalid rigid sensor camera-to-world pose')
                # Sensor poses are a prior; retain visual evidence for verified
                # historical loop constraints with each frame's own intrinsics.
                try:
                    current = _features(cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY), depth, sift, cv2)
                except ValueError:
                    current = None
            else:
                current = _features(cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY), depth, sift, cv2)
            if previous is not None and not supplied:
                if manifest.get('ordered_capture',True):
                    relative, quality = _relative_pose(previous, current, k, cv2, previous_k)
                    pose = pose @ np.linalg.inv(relative)
                else:
                    pose,quality=pose_against_registered(current,k,feature_history,camera_calibrations,
                        [np.asarray(p['camera_to_first']) for p in poses],cv2)
                logs.append({"frame_id": frame["id"], **quality})
        except ValueError as exc:
            failure = {"frame_id": frame["id"], "reason": str(exc)}
            if not supplied and consecutive_failures < recovery_limit:
                # Retry against the last verified camera, never integrate an
                # untracked frame or extrapolate a pose through the gap.
                skipped.append({**failure, 'reason': 'Tracking retry: '+str(exc)})
                consecutive_failures += 1
                continue
            break
        if consecutive_failures:
            if not logs or logs[-1]['frame_id']!=frame['id']:
                logs.append(dict(frame_id=frame['id'],event='initialized after rejected initial views'))
            logs[-1]['recovered_after_skipped_frames'] = consecutive_failures
        consecutive_failures = 0
        failure = None
        poses.append({"frame_id": frame["id"], "camera_to_first": pose.tolist()})
        retained_indices.append(index)
        yy, xx = np.mgrid[0:depth.shape[0]:8, 0:depth.shape[1]:8]
        z = depth[yy, xx].ravel()
        valid = z > 0
        xyz = _backproject(np.column_stack((xx.ravel()[valid], yy.ravel()[valid])), z[valid], k)
        clouds.append(xyz)
        colors.append(rgb[yy, xx].reshape(-1, 3)[valid, ::-1])
        weights.append((confidence[yy, xx].ravel()[valid].astype(float)+1) / np.maximum(z[valid], 0.5)**2)
        feature_history.append(current)
        camera_calibrations.append(k.copy())
        previous = current
        previous_k = k
        if index % 25 == 0:
            print(f"RGB-D: tracked {index + 1}/{len(frames)} frames", flush=True)
    if not clouds:
        result = {"status": "no_tracking", "input_frames": len(frames), "tracked_frames": 0, "tracked_fraction": 0.0, "tracking_failure": failure, "floor_plan_ready": False, "ground_truth_used_for_reconstruction": False}
        (output / "rgbd_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result
    pose_matrices = [np.asarray(p['camera_to_first']) for p in poses]
    raw_pose_matrices=[p.copy() for p in pose_matrices]
    (output/'raw_trajectory.json').write_text(json.dumps(poses,indent=2),encoding='utf-8')
    mapping = {'enabled': False, 'pose_source': manifest.get('pose_source', 'estimated')}
    path_breaks=retained_path_breaks(retained_indices,manifest.get('path_breaks',()))
    if manifest.get('optimize_poses', False) and len(poses) > 2:
        from .mapping import optimize_poses
        pose_matrices, mapping = optimize_poses(clouds, pose_matrices,
            feature_history, k, keyframe_stride=manifest.get('keyframe_stride', 5),
            calibrations=camera_calibrations,path_breaks=path_breaks)
        mapping['enabled'] = True
        for entry, matrix in zip(poses, pose_matrices):
            entry['camera_to_first'] = matrix.tolist()
    mapping['max_camera_translation_correction_m']=float(max(np.linalg.norm(a[:3,3]-b[:3,3]) for a,b in zip(raw_pose_matrices,pose_matrices)))
    mapping['requested']=bool(manifest.get('optimize_poses',False))
    mapping['path_breaks']=path_breaks
    cloud = np.concatenate([c @ p[:3,:3].T + p[:3,3] for c,p in zip(clouds, pose_matrices)])
    color = np.concatenate(colors)
    from .layout import weighted_voxels, extract_layout, export_layout, render_layout_diagnostic
    cloud, color, support_weights = weighted_voxels(cloud, color, np.concatenate(weights))
    # Retain the coordinates actually used for fitting. Rounding only the saved
    # cloud to float32 changes refitted finite lines and sometimes polygonization.
    np.savez_compressed(output / "cloud.npz", points=cloud, rgb=color.astype(np.uint8), weights=support_weights)
    (output / "trajectory.json").write_text(json.dumps(poses, indent=2), encoding="utf-8")
    planes = _fit_planes(cloud)
    result = {"source": str(manifest_path), "method": "SIFT + depth-supported PnP RANSAC + 3D metric refinement + plane fitting", "input_frames": len(frames), "tracked_frames": len(poses), "tracked_fraction": len(poses) / len(frames), "point_count": len(cloud), "tracking_failure": failure, "skipped_frames":skipped, "planes": planes, "tracking_quality": logs, "ground_truth_used_for_reconstruction": False, "metric_scale_source": "input depth units", "floor_plan_ready": False}
    result['supplied_frames']=len(manifest['frames'])
    result['cloud_artifact_precision']='float64; identical coordinates used for fitting and layout'
    result['truncated_capture']=len(frames)<len(manifest['frames'])
    complete_capture = failure is None and len(poses)/len(frames)>=0.9 and not result['truncated_capture']
    try:
        result['mapping'] = mapping
        result['accuracy_validated'] = False
        if manifest.get('layout', 'rectangle') == 'polygons':
            # SfM/sensor world axes need not be the first camera's axes. Use a
            # disclosed camera-down weak prior in that actual world frame when
            # gravity was not supplied; never assume arbitrary world Y is down.
            down=manifest.get('down_direction')
            if down is None: down=pose_matrices[0][:3,1]
            rooms, metadata = extract_layout(cloud, planes, np.asarray(pose_matrices)[:,:3,3], down,
                                             path_breaks=path_breaks)
            metadata['depth_provenance']=manifest.get('depth_provenance','sensor or declared metric depth')
            from .openings import augment_room_openings
            augment_room_openings(rooms,metadata,[
                dict(points=c@p[:3,:3].T+p[:3,3],camera=p[:3,3]) for c,p in zip(clouds,pose_matrices)])
            (output / 'layout_evidence.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
            render_layout_diagnostic(metadata,output/'layout_diagnostic.svg')
            if not rooms:
                raise ValueError('Observed wall segments do not close a room; inspect layout_evidence.json')
            complete_capture=complete_capture and not metadata['unclosed_geometry']
            export_layout(rooms, metadata, output, manifest.get('metric_status', 'sensor_scaled'), complete_capture)
            result.update({'status': 'proposal_requires_review' if complete_capture else 'partial', 'floor_plan_ready': complete_capture,
                           'plan_produced': True, 'plan_metadata': metadata})
            (output / 'rgbd_summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            return result
        corners, metadata = rectangle_from_planes(planes)
        room = {"id": "room_0", "label": "RGB-D room proposal", "corners": corners, "local_corners": corners, "placement": "origin", "metric_status": "sensor_scaled", "ceiling_height_m": None, "openings": []}
        quantities = _quantities(room)
        plan = {"schema_version": 1, "units": "metres", "rooms": [room], "quantities": [quantities], "provenance": metadata, "status": "review_required"}
        (output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        _svg([room], output / "plan.svg")
        _dxf([room], output / "plan.dxf")
        with (output / "quantities.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(quantities))
            writer.writeheader()
            writer.writerow(quantities)
        result.update({"status": "partial" if failure else "proposal_requires_review", "floor_plan_ready": failure is None, "plan_produced": True, "plan_metadata": metadata})
    except ValueError as exc:
        result.update({"status": "incomplete_geometry", "geometry_failure": str(exc)})
    (output / "rgbd_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
