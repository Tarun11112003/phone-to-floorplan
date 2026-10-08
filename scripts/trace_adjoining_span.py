"""Audit a diagnostic span against measured returns; never create geometry.

The query is an inspection coordinate, not a wall, opening, or surveyed truth.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from scipy.spatial.transform import Rotation

import floorplan.layout as layout
from floorplan.provenance import sha256
from floorplan.rgbd import _backproject

X_BOUNDS = (-2.73, -.44)
Z = 4.44
HALF_WIDTH = .12


def span_mask(points, floor, wall_height=True):
    mask = ((points[:, 0] >= X_BOUNDS[0]) & (points[:, 0] <= X_BOUNDS[1])
            & (np.abs(points[:, 2] - Z) < HALF_WIDTH))
    if wall_height:
        mask &= (points[:, 1] < floor - .25) & (points[:, 1] > floor - 3.)
    return mask


def crossing_rays(camera, endpoints, floor, clearance=.10):
    """Measured rays cross the query with clearance on BOTH sides, at wall height.

    This is pose-conditional free-space evidence, not semantic opening truth.
    Returns the qualifying ray mask and their intersections in aligned XYZ.
    """
    direction = endpoints - camera
    t = np.divide(Z - camera[2], direction[:, 2], out=np.full(len(endpoints), np.nan),
                  where=np.abs(direction[:, 2]) > 1e-12)
    intersections = camera + t[:, None] * direction
    lengths = np.linalg.norm(direction, axis=1)
    mask = (np.isfinite(t) & (t > 0) & (t < 1)
            & (t * lengths > clearance) & ((1 - t) * lengths > clearance)
            & (intersections[:, 0] >= X_BOUNDS[0]) & (intersections[:, 0] <= X_BOUNDS[1])
            & (intersections[:, 1] < floor - .25) & (intersections[:, 1] > floor - 3.))
    return mask, intersections[mask]


def traversals(path, ids, breaks=()):
    rows = []
    for i, (a, b) in enumerate(zip(path[:-1], path[1:])):
        if (a[1] - Z) * (b[1] - Z) >= 0:
            continue
        t = (Z - a[1]) / (b[1] - a[1])
        x = float(a[0] + t * (b[0] - a[0]))
        if not X_BOUNDS[0] <= x <= X_BOUNDS[1]:
            continue
        step = float(np.linalg.norm(b - a))
        rows.append(dict(from_frame=int(ids[i]), to_frame=int(ids[i+1]), x_m=x,
                         step_m=step, endpoint_clearance_z_m=float(min(abs(a[1]-Z), abs(b[1]-Z))),
                         continuous_under_existing_guard=step <= 1.5 and i+1 not in breaks))
    return rows


def x_profile(points, floor):
    edges = np.linspace(*X_BOUNDS, 13)
    rows = []
    for index, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
        selected = points[(points[:, 0] >= a) & ((points[:, 0] <= b) if index == 11 else (points[:, 0] < b))]
        rows.append(dict(x_bounds_m=[float(a), float(b)], points=len(selected),
                         height_span_m=float(np.ptp(selected[:, 1])) if len(selected) else 0,
                         height_range_m=[float(floor-selected[:, 1].max()), float(floor-selected[:, 1].min())] if len(selected) else None))
    return rows


def trace(run, source, out, dense_sensor=False):
    run, source, out = (Path(p).resolve() for p in (run, source, out))
    out.mkdir(parents=True, exist_ok=False)
    read = lambda name: json.loads((run/name).read_text(encoding='utf-8'))
    ledger = read('run.json'); meta = read('artifacts/layout_evidence.json')
    sequence = read('normalized_sequence.json'); rgbd = read('artifacts/rgbd_summary.json')
    artifacts = ['artifacts/'+name for name in ('cloud.npz', 'trajectory.json', 'rgbd_summary.json', 'layout_evidence.json')]
    hashes = {name: sha256(run/name) for name in ['run.json', 'plan.json', 'normalized_sequence.json'] + artifacts}
    if any(ledger['geometry_artifact_sha256'][name] != hashes[name] for name in artifacts):
        raise ValueError('Frozen artifact hash mismatch')
    code = {p.name: sha256(p) for p in Path(layout.__file__).parent.glob('*.py')}
    if any(code.get(name) != value for name, value in ledger['code_sha256'].items()):
        raise ValueError('Frozen reconstruction producer mismatch')
    if any(sha256(Path(name)) != value for name, value in ledger['inputs'].items()):
        raise ValueError('Baseline sensor input changed')
    basis = np.asarray(meta['basis_columns_in_input']); floor = meta['wall_sampling_slab_bound_m']
    poses = {p['frame_id']: np.asarray(p['camera_to_first']) for p in read('artifacts/trajectory.json')}
    rows = []; clouds = []; weights = []; colors = []; ray_clouds = []; source_hashes = {}
    for frame in sequence['frames']:
        fid = frame['id']; pose = poses[fid]
        dp, cp = run/Path(frame['depth']), run/Path(frame['confidence'])
        for original, extracted in ((source/'depth'/f'{fid:06d}.png', dp), (source/'confidence'/f'{fid:06d}.png', cp)):
            value = sha256(original); source_hashes[str(original)] = value
            if value != sha256(extracted):
                raise ValueError(f'Extraction changed sensor payload {fid}')
        depth = cv2.imread(str(dp), cv2.IMREAD_UNCHANGED).astype(float)/sequence['depth_scale']
        confidence = cv2.imread(str(cp), cv2.IMREAD_UNCHANGED)
        yy, xx = np.indices(depth.shape); positive = np.isfinite(depth) & (depth > 0)
        pixels = np.column_stack((xx[positive], yy[positive]))
        kd = frame.get('intrinsics', sequence['intrinsics'])
        k = np.array([[kd['fx'],0,kd['cx']], [0,kd['fy'],kd['cy']], [0,0,1]])
        xyz = _backproject(pixels, depth[positive], k)
        world = xyz@pose[:3,:3].T + pose[:3,3]; aligned = world@basis
        region = span_mask(aligned, floor)
        valid = (depth[positive] >= .2) & (depth[positive] <= sequence.get('depth_max_m', 8.))
        conf = confidence[positive]; accepted = valid & (conf >= sequence.get('minimum_confidence', 1))
        sampled = accepted & (pixels[:, 0] % 8 == 0) & (pixels[:, 1] % 8 == 0)
        raw_pose = np.asarray(frame['camera_to_world'])
        raw_aligned = (xyz@raw_pose[:3,:3].T + raw_pose[:3,3])@basis
        rays, intersections = crossing_rays(pose[:3,3]@basis, aligned[accepted], floor)
        high_rays, _ = crossing_rays(pose[:3,3]@basis, aligned[accepted & (conf == 2)], floor)
        # Histograms retain frame provenance but counts are repeated observations.
        ray_clouds.append(intersections)
        rows.append(dict(frame_id=fid, timestamp_s=frame.get('timestamp_s'),
                         positive_span_pixels=int(region.sum()),
                         range_valid_span_pixels=int((region & valid).sum()),
                         confident_span_pixels=int((region & accepted).sum()),
                         confidence_0_span_pixels=int((region & valid & (conf == 0)).sum()),
                         confidence_1_span_pixels=int((region & valid & (conf == 1)).sum()),
                         confidence_2_span_pixels=int((region & valid & (conf == 2)).sum()),
                         stride8_span_points=int((region & sampled).sum()),
                         raw_pose_confident_span_pixels=int((span_mask(raw_aligned, floor) & accepted).sum()),
                         free_space_crossing_rays=int(rays.sum()), confidence_2_crossing_rays=int(high_rays.sum())))
        clouds.append(world[sampled]); z = depth[positive][sampled]
        weights.append((conf[sampled].astype(float)+1)/np.maximum(z, .5)**2)
        rgb = cv2.imread(str(run/Path(frame['rgb'])))
        colors.append(rgb[pixels[sampled, 1], pixels[sampled, 0], ::-1])
    sampled_cloud = np.concatenate(clouds)
    replay, _, _ = layout.weighted_voxels(sampled_cloud, np.concatenate(colors), np.concatenate(weights))
    cloud = np.load(run/'artifacts/cloud.npz')['points']
    if not np.array_equal(replay, cloud):
        raise ValueError('Sensor fusion replay differs from baseline')
    q = cloud@basis; region = span_mask(q, floor)
    planes = rgbd['planes'] + meta.get('wall_seed_planes', [])
    initial = layout._projection_wall_proposals(cloud, planes, basis, floor)
    remaining = np.ones(len(cloud), bool); removals = []
    for i, plane in enumerate(planes+initial):
        hit = np.abs(cloud@np.asarray(plane['normal'])+plane['offset']) < .035
        removals.append(dict(plane_id=i, first_removed_span_points=int((region & remaining & hit).sum()),
                             vertical_dot=float(abs(np.asarray(plane['normal'])@basis[:, 1]))))
        remaining &= ~hit
    proposals = layout._supported_wall_proposals(cloud, planes, basis, floor)
    if json.loads(json.dumps(proposals)) != meta['wall_plane_proposals']:
        raise ValueError('Proposal replay differs from baseline')
    _, voxel_ids = np.unique(np.floor(sampled_cloud/.02).astype(np.int64), axis=0, return_inverse=True)
    offset = 0
    for row, points in zip(rows, clouds):
        ids = np.unique(voxel_ids[offset:offset+len(points)]); offset += len(points)
        row['fused_span_voxels_contributed'] = int(region[ids].sum())
        row['residual_span_voxels_contributed'] = int((region[ids] & remaining[ids]).sum())
    dense = None
    if dense_sensor:
        dense_rows = []; sensor_path = []; sensor_ids = []; dense_hashes = {}
        with (source/'odometry.csv').open(newline='', encoding='utf-8-sig') as handle:
            odometry = list(csv.DictReader(handle, skipinitialspace=True))
        for row in odometry:
            fid = int(row['frame']); dp = source/'depth'/f'{fid:06d}.png'; cp = source/'confidence'/f'{fid:06d}.png'
            if not dp.is_file() or not cp.is_file():
                raise ValueError(f'Missing dense sensor pair {fid}')
            dense_hashes[str(dp)] = sha256(dp); dense_hashes[str(cp)] = sha256(cp)
            depth = cv2.imread(str(dp), cv2.IMREAD_UNCHANGED)[::8, ::8].astype(float)/sequence['depth_scale']
            conf = cv2.imread(str(cp), cv2.IMREAD_UNCHANGED)[::8, ::8]
            yy, xx = np.indices(depth.shape)
            valid = (depth >= .2) & (depth <= sequence.get('depth_max_m', 8.))
            pixels = np.column_stack((xx[valid]*8, yy[valid]*8))
            # Supplied RGB calibration is 1920x1440; per-frame values are authoritative.
            k = np.array([[float(row['fx'])*256/1920,0,float(row['cx'])*256/1920],
                          [0,float(row['fy'])*192/1440,float(row['cy'])*192/1440], [0,0,1]])
            rot = Rotation.from_quat([float(row[key]) for key in ('qx','qy','qz','qw')]).as_matrix()
            position = np.array([float(row[key]) for key in ('x','y','z')])
            aligned = (_backproject(pixels, depth[valid], k)@rot.T + position)@basis
            sensor_path.append((position@basis)[[0, 2]]); sensor_ids.append(fid)
            region_dense = span_mask(aligned, floor); c = conf[valid]
            dense_rows.append(dict(frame_id=fid, confident_span_stride8_points=int((region_dense & (c >= 1)).sum()),
                                   low_confidence_span_stride8_points=int((region_dense & (c == 0)).sum())))
        dense = dict(frames=len(dense_rows), per_frame=dense_rows, raw_sensor_sha256=dense_hashes,
                     confident_span_stride8_points=sum(r['confident_span_stride8_points'] for r in dense_rows),
                     frames_with_span_returns=sum(r['confident_span_stride8_points'] > 0 for r in dense_rows),
                     camera_crossings=traversals(np.asarray(sensor_path), sensor_ids),
                     pose_policy='Original odometry only; not interpolated refined poses',
                     limitation='All raw frames at stride 8; does not exclude thin geometry missed between stride samples')
    ids = [frame['id'] for frame in sequence['frames']]
    raw_path = np.asarray([np.asarray(frame['camera_to_world'])[:3, 3]@basis for frame in sequence['frames']])[:, [0, 2]]
    intersections = np.concatenate(ray_clouds)
    totals = {key: sum(row[key] for row in rows) for key in rows[0] if key.endswith(('_pixels', '_points', '_rays'))}
    result = dict(experiment='lower_adjoining_span_sensor_and_traversal_trace', run=str(run), source=str(source),
                  query=dict(x_bounds_m=X_BOUNDS, z_m=Z, half_width_m=HALF_WIDTH, wall_height_bounds_m=[.25,3.],
                             query_is_not_a_proposed_boundary=True),
                  input_sha256=hashes, raw_sensor_sha256=source_hashes, code_sha256=code,
                  script_sha256=sha256(Path(__file__)), frames=len(rows), totals=totals, per_frame=rows,
                  fusion_replay_exact=True, proposals_replay_exact=True,
                  fused_all_height_span_points=int(span_mask(q, floor, False).sum()),
                  fused_wall_height_span_points=int(region.sum()), residual_span_points=int((region & remaining).sum()),
                  fused_wall_span_profile=x_profile(q[region], floor), residual_span_profile=x_profile(q[region & remaining], floor),
                  free_space_crossing_profile=x_profile(intersections, floor),
                  frames_with_free_space_crossings=sum(row['free_space_crossing_rays'] > 0 for row in rows),
                  plane_removals=removals, refined_camera_crossings=traversals(np.asarray(meta['camera_path_2d']), ids, rgbd.get('camera_path_breaks', [])),
                  raw_camera_crossings=traversals(raw_path, ids), dense_sensor_audit=dense,
                  camera_coverage_fraction=meta['camera_center_coverage_fraction'],
                  accuracy_validated=False, geometry_changed=False,
                  limitations=['Repeated observations and frame contributions are dependent, not independent truth',
                               'Depth rays and camera crossings depend on supplied calibration and poses',
                               'The query is not a semantic wall/door annotation or an opening-width measurement',
                               'No connecting boundary is justified merely by rectangular closure',
                               'Earlier ceiling boundary shift of 0.703 m remains unvalidated'])
    if hashes != {name: sha256(run/name) for name in hashes} or code != {p.name:sha256(p) for p in Path(layout.__file__).parent.glob('*.py')}:
        raise ValueError('Baseline changed during audit')
    (out/'trace.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(11, 7))
    axes[0].plot(ids, [row['confident_span_pixels'] for row in rows], label='Confident wall-height returns')
    axes[0].plot(ids, [row['free_space_crossing_rays'] for row in rows], label='Measured rays crossing query')
    axes[0].set(xlabel='Selected sensor frame ID', ylabel='Repeated observation count'); axes[0].legend()
    for mask, label in ((region & remaining, 'Residual'), (region & ~remaining, 'Explained')):
        axes[1].scatter(q[mask, 0], floor-q[mask, 1], s=10, label=label)
    axes[1].set(xlabel='Aligned x (m)', ylabel='Height above sampling bound (m)'); axes[1].legend()
    fig.suptitle('Lower adjoining-span audit; no surveyed ground truth'); fig.tight_layout()
    fig.savefig(out/'trace.png', dpi=140); plt.close(fig)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path); parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path); parser.add_argument('--dense-sensor', action='store_true')
    args = parser.parse_args(); result = trace(args.run, args.source, args.out, args.dense_sensor)
    print(json.dumps({key:value for key,value in result.items() if key not in
                     ('input_sha256','raw_sensor_sha256','code_sha256','per_frame','dense_sensor_audit','plane_removals')}, indent=2))
    if result['dense_sensor_audit']:
        print(json.dumps({key:value for key,value in result['dense_sensor_audit'].items() if key not in ('per_frame','raw_sensor_sha256')}, indent=2))
