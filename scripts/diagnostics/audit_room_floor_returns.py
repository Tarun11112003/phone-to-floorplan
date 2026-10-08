"""Read-only source-return inventory for a fixed room and horizontal plane.

No fitting, frame insertion, pose optimization or acceptance decisions are made.
Dense source returns are diagnostic witnesses, not a replacement fused cloud.
Raw-pose frame-selection comparisons are kept separate from refined-pose ones.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import cv2
import numpy as np
import shapely
from scipy.spatial.transform import Rotation
from shapely.geometry import Polygon, box

from floorplan import layout
from floorplan.provenance import sha256
from floorplan.rgbd import _backproject

BAND_M = .035
CELL_M = .20
BUFFER_M = .05
STRIDE = 8
RESIDUAL_EDGES = np.array([-.15, -.075, -.035, .035, .075, .15])


def pixel_masks(depth, confidence, scale, minimum_confidence=1, maximum_depth=8.):
    if depth.ndim != 2 or confidence.shape != depth.shape:
        raise ValueError('Expected matching two-dimensional depth/confidence')
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Expected positive finite depth scale')
    z = depth.astype(float) / scale
    valid = np.isfinite(z) & (z >= .2) & (z <= maximum_depth)
    accepted = valid & (confidence >= minimum_confidence)
    yy, xx = np.indices(depth.shape)
    lattice = (xx % STRIDE == 0) & (yy % STRIDE == 0)
    return z, valid, accepted, lattice


def support_mask(aligned, normal, offset, poly):
    near = np.abs(aligned @ normal + offset) < BAND_M
    result = np.zeros(len(aligned), dtype=bool)
    ids = np.flatnonzero(near)
    result[ids] = shapely.covers(poly.buffer(BUFFER_M), shapely.points(aligned[ids][:, [0, 2]]))
    return result


def cell_keys(aligned):
    return {tuple(map(int, p)) for p in np.floor(aligned[:, [0, 2]] / CELL_M).astype(int)}


def clipped_coverage(poly, cells):
    # Same cell definition, clipping and deterministic ordering as native code.
    area = sum(poly.intersection(box(x * CELL_M, z * CELL_M,
                    (x + 1) * CELL_M, (z + 1) * CELL_M)).area for x, z in sorted(cells))
    return dict(occupied_cells=len(cells), clipped_area_m2=float(area),
                coverage_fraction=float(min(area / poly.area, 1.)),
                cells=[list(c) for c in sorted(cells)])


def summarize_frame(aligned, confidence, lattice, normal, offset, poly):
    """Input contains all in-range pixels; confidence exclusions remain visible."""
    local = support_mask(aligned, normal, offset, poly)
    masks = dict(in_range=local, accepted=local & (confidence >= 1),
                 confidence2=local & (confidence == 2),
                 stride8=local & (confidence >= 1) & lattice,
                 off_lattice=local & (confidence >= 1) & ~lattice,
                 confidence_rejected=local & (confidence < 1))
    stats = {key: dict(points=int(mask.sum()), cells=cell_keys(aligned[mask]))
             for key, mask in masks.items()}
    inside = shapely.covers(poly.buffer(BUFFER_M), shapely.points(aligned[:, [0, 2]]))
    residual = aligned[inside] @ normal + offset
    histogram = np.histogram(residual, RESIDUAL_EDGES)[0].tolist()
    return stats, dict(room_in_range_pixels=int(inside.sum()),
        signed_plane_residual_edges_m=RESIDUAL_EDGES.tolist(),
        signed_plane_residual_bin_counts=histogram,
        outside_residual_histogram=int(inside.sum() - sum(histogram))), masks


def aggregate_into(aggregate, stats):
    for name, value in stats.items():
        row = aggregate.setdefault(name, dict(points=0, frames_with_support=0, cells=set()))
        row['points'] += value['points']
        row['frames_with_support'] += int(value['points'] > 0)
        row['cells'].update(value['cells'])


def finish_aggregate(aggregate, poly):
    return {name: dict(points=value['points'], frames_with_support=value['frames_with_support'],
                      **clipped_coverage(poly, value['cells'])) for name, value in aggregate.items()}


def fusion_lineage(samples, weights, sample_floor, frozen_cloud, frozen_weights, basis, normal, offset, poly):
    """Replay native global fusion; then attribute support through exact voxel IDs."""
    fused, _, total = layout.weighted_voxels(samples, weights=weights)
    checks = dict(points_bit_identical=bool(np.array_equal(fused, frozen_cloud)),
                  weights_bit_identical=bool(np.array_equal(total, frozen_weights)))
    if not all(checks.values()):
        raise ValueError(f'Native current-cloud replay failed: {checks}')
    _, voxel_ids = np.unique(np.floor(samples / .02).astype(np.int64), axis=0, return_inverse=True)
    before = set(voxel_ids[sample_floor].tolist())
    aligned = fused @ basis
    fused_support = support_mask(aligned, normal, offset, poly)
    after = set(np.flatnonzero(fused_support).tolist())
    before_cells = cell_keys((samples @ basis)[sample_floor])
    after_cells = cell_keys(aligned[fused_support])
    native_count, native_coverage = layout._horizontal_support(poly, aligned, normal, offset)
    report = dict(checks=checks, global_sample_points=len(samples), fused_points=len(fused),
        pre_fusion_local_returns=int(sample_floor.sum()),
        pre_fusion_local_voxels=len(before), post_fusion_local_points=len(after),
        floor_voxels_retained=len(before & after), floor_voxels_lost=len(before - after),
        floor_voxels_gained=len(after - before),
        pre_fusion_support=clipped_coverage(poly, before_cells),
        post_fusion_support=clipped_coverage(poly, after_cells),
        lost_occupied_cells=[list(c) for c in sorted(before_cells - after_cells)],
        gained_occupied_cells=[list(c) for c in sorted(after_cells - before_cells)],
        native_helper_return=[int(native_count), float(native_coverage)],
        lost_voxel_witnesses=[dict(voxel_id=i, fused_aligned_xyz=aligned[i].tolist(),
             fused_signed_residual_m=float(aligned[i] @ normal + offset),
             contributor_count=int(np.sum(voxel_ids == i))) for i in sorted(before - after)])
    if native_count != len(after) or (native_count >= 100 and native_coverage != report['post_fusion_support']['coverage_fraction']):
        raise ValueError('Diagnostic occupied-cell calculation disagrees with native helper')
    return report, fused_support[voxel_ids]


def raw_calibration(row, shape, rgb_shape):
    height, width = shape; rgb_width, rgb_height = rgb_shape
    camera = {k: float(row[k]) * (width/rgb_width if k in ('fx', 'cx') else height/rgb_height)
              for k in ('fx', 'fy', 'cx', 'cy')}
    k = np.array([[camera['fx'], 0, camera['cx']], [0, camera['fy'], camera['cy']], [0, 0, 1.]])
    q = np.array([float(row[name]) for name in ('qx', 'qy', 'qz', 'qw')])
    pose = np.eye(4)
    pose[:3, :3] = Rotation.from_quat(q / np.linalg.norm(q)).as_matrix()
    pose[:3, 3] = [float(row[name]) for name in ('x', 'y', 'z')]
    return camera, k, pose


def run(run_dir, source, room_id, plane_index, out):
    started = time.perf_counter()
    run_dir, source, out = [Path(p).resolve() for p in (run_dir, source, out)]
    if out.exists() or any(out == p or p in out.parents or out in p.parents for p in (run_dir, source)):
        raise ValueError('Use a fresh output separate from all source artifacts')
    read = lambda p: json.loads(p.read_text(encoding='utf-8'))
    plan = read(run_dir/'plan.json'); meta = read(run_dir/'artifacts/layout_evidence.json')
    sequence = read(run_dir/'normalized_sequence.json'); trajectory = read(run_dir/'artifacts/trajectory.json')
    fitted = read(run_dir/'artifacts/rgbd_summary.json'); ledger = read(run_dir/'run.json')
    paths = [run_dir/name for name in ('plan.json', 'run.json', 'normalized_sequence.json')]
    paths += [run_dir/name for name in ledger['geometry_artifact_sha256']]
    paths += [source/'odometry.csv', Path(layout.__file__), Path(__file__).resolve().parents[2]/'floorplan/rgbd.py']
    frozen = {str(p): sha256(p) for p in paths}
    if any(sha256(run_dir/name) != digest for name, digest in ledger['geometry_artifact_sha256'].items()):
        raise ValueError('Retained geometry hashes changed')
    rooms = [r for r in plan['rooms'] if r['id'] == room_id]
    if len(rooms) != 1: raise ValueError('Expected one retained room')
    room = rooms[0]; poly = Polygon(room['corners'])
    basis = np.asarray(meta['basis_columns_in_input'])
    planes = fitted['planes'] + meta.get('wall_seed_planes', []) + meta['wall_plane_proposals']
    plane = planes[plane_index]; normal = np.asarray(plane['normal']) @ basis; offset = plane['offset']
    refined = {r['frame_id']: np.asarray(r['camera_to_first']) for r in trajectory}
    selected = {r['id']: r for r in sequence['frames']}
    if len(selected) != len(sequence['frames']) or list(selected) != list(refined):
        raise ValueError('Selected and retained frame identity/order must agree exactly')
    if sequence.get('minimum_confidence', 1) != 1:
        raise ValueError('This audit expects the retained confidence>=1 policy')
    with (source/'odometry.csv').open(encoding='utf-8', newline='') as stream:
        sensors = list(csv.DictReader(stream, skipinitialspace=True))
    if [int(r['frame']) for r in sensors] != list(range(len(sensors))) or np.any(np.diff([float(r['timestamp']) for r in sensors]) <= 0):
        raise ValueError('Original sensor frame identities/timestamps are inconsistent')
    video = cv2.VideoCapture(str(source/'rgb.mp4'))
    rgb_shape = (video.get(cv2.CAP_PROP_FRAME_WIDTH), video.get(cv2.CAP_PROP_FRAME_HEIGHT)); video.release()
    if min(rgb_shape) <= 0: raise ValueError('Missing RGB calibration dimensions')
    depths = {int(p.stem): p for p in (source/'depth').glob('*.png')}
    confidences = {int(p.stem): p for p in (source/'confidence').glob('*.png')}
    available = sorted(depths.keys() & confidences.keys())
    if not set(selected).issubset(available) or any(fid >= len(sensors) for fid in available):
        raise ValueError('Missing selected or source sensor identities')
    aggregates = {k: {} for k in ('selected_refined', 'selected_raw', 'unselected_raw', 'all_available_raw')}
    rows = []; samples = {}; weights = {}; source_hashes = {}; dimensions = set()
    histograms = {key: np.zeros(len(RESIDUAL_EDGES)-1, dtype=np.int64) for key in aggregates}
    witnesses = []
    for index, fid in enumerate(available):
        dp, cp = depths[fid], confidences[fid]
        source_hashes[str(dp)] = sha256(dp); source_hashes[str(cp)] = sha256(cp)
        depth = cv2.imread(str(dp), cv2.IMREAD_UNCHANGED); confidence = cv2.imread(str(cp), cv2.IMREAD_UNCHANGED)
        if depth is None or confidence is None: raise ValueError('Unreadable original sensor PNG')
        dimensions.add(tuple(depth.shape))
        z, valid, accepted, lattice = pixel_masks(depth, confidence, sequence['depth_scale'],
            sequence.get('minimum_confidence', 1), sequence.get('depth_max_m', 8.))
        yy, xx = np.indices(depth.shape); pixels = np.column_stack((xx.ravel(), yy.ravel()))
        camera, k, raw_pose = raw_calibration(sensors[fid], depth.shape, rgb_shape)
        xyz = _backproject(pixels[valid.ravel()], z[valid], k)
        conf = confidence[valid]; stride = lattice[valid]
        row = dict(frame_id=fid, sensor_timestamp_s=float(sensors[fid]['timestamp']), selected=fid in selected,
            in_range_pixels=int(valid.sum()), accepted_pixels=int(accepted.sum()),
            accepted_stride8_pixels=int((accepted & lattice).sum()),
            native_depth_count_guard_passes=bool(accepted.sum() >= 100 and (accepted & lattice).sum() >= 30))
        modes = [('raw', raw_pose)]
        if fid in selected:
            frame = selected[fid]
            if any(frame['intrinsics'][key] != value for key, value in camera.items()):
                raise ValueError('Per-frame intrinsic extraction differs from original')
            if not np.array_equal(raw_pose, frame['camera_to_world']):
                raise ValueError('Original pose extraction mismatch')
            if float(sensors[fid]['timestamp']) != frame['source_sensor_timestamp_s']:
                raise ValueError('Retained sensor timing mismatch')
            for original, copy in ((dp, Path(frame['depth'])), (cp, Path(frame['confidence']))):
                if source_hashes[str(original)] != sha256(copy):
                    raise ValueError('Original/extracted sensor PNG differs')
                frozen[str(copy)] = sha256(copy)
            if not row['native_depth_count_guard_passes']: raise ValueError('Retained frame fails native depth count guard')
            modes.append(('refined', refined[fid]))
            # Match the native lattice projection and multiplication order exactly.
            uv = pixels[(accepted & lattice).ravel()]; zs = z[accepted & lattice]
            local = _backproject(uv, zs, k); pose = refined[fid]
            samples[fid] = local @ pose[:3, :3].T + pose[:3, 3]
            weights[fid] = (confidence[accepted & lattice].astype(float)+1) / np.maximum(zs, .5)**2
        for mode, pose in modes:
            aligned = (xyz @ pose[:3, :3].T + pose[:3, 3]) @ basis
            stats, residual, masks = summarize_frame(aligned, conf, stride, normal, offset, poly)
            row[mode] = dict(support_counts={name: value['points'] for name, value in stats.items()},
                support_cell_counts={name: len(value['cells']) for name, value in stats.items()}, **residual)
            target = ('selected_raw' if fid in selected else 'unselected_raw') if mode == 'raw' else 'selected_refined'
            aggregate_into(aggregates[target], stats)
            histograms[target] += residual['signed_plane_residual_bin_counts']
            if mode == 'raw':
                aggregate_into(aggregates['all_available_raw'], stats)
                histograms['all_available_raw'] += residual['signed_plane_residual_bin_counts']
            if mode == 'refined' and masks['off_lattice'].any():
                ids = np.flatnonzero(masks['off_lattice'])
                chosen = ids[np.linspace(0, len(ids)-1, min(6, len(ids)), dtype=int)]
                valid_uv = pixels[valid.ravel()]
                witnesses.extend(dict(frame_id=fid, pixel_uv=valid_uv[i].tolist(),
                    depth_m=float(z[valid][i]), confidence=int(conf[i]), aligned_xyz=aligned[i].tolist(),
                    signed_plane_residual_m=float(aligned[i] @ normal + offset)) for i in chosen)
        rows.append(row)
        if index % 250 == 0: print(f'Original floor returns: {index+1}/{len(available)}', flush=True)
    ordered_samples = np.concatenate([samples[fid] for fid in selected])
    ordered_weights = np.concatenate([weights[fid] for fid in selected])
    sample_floor = support_mask(ordered_samples @ basis, normal, offset, poly)
    with np.load(run_dir/'artifacts/cloud.npz') as cloud:
        fusion, final_contributors = fusion_lineage(ordered_samples, ordered_weights, sample_floor,
            cloud['points'], cloud['weights'], basis, normal, offset, poly)
    position = 0
    for row in rows:
        if not row['selected']: continue
        count = len(samples[row['frame_id']])
        row['contributions_to_final_local_floor_voxels'] = int(final_contributors[position:position+count].sum())
        position += count
    if position != len(ordered_samples): raise ValueError('Fusion provenance order mismatch')
    if any(sha256(p) != digest for p, digest in {**frozen, **source_hashes}.items()):
        raise ValueError('Input data changed during audit')
    result = dict(room_id=room_id, plane_index=plane_index, plane=plane, aligned_plane_normal=normal.tolist(),
        polygon_area_m2=poly.area, polygon_corners=room['corners'], basis=basis.tolist(),
        fixed_policy=dict(plane_band_m=BAND_M, buffer_m=BUFFER_M, coverage_cell_m=CELL_M, pixel_stride=STRIDE,
            minimum_confidence=1, depth_min_m=.2, depth_max_m=sequence.get('depth_max_m', 8.),
            floor_coverage_guard=.25, occupancy_minimum_points=100, fusion_voxel_m=.02),
        source_inventory=dict(depth_files=len(depths), confidence_files=len(confidences), odometry_rows=len(sensors),
            paired_frames=len(available), selected_frames=len(selected), unselected_paired_frames=len(available)-len(selected),
            confidence_frames_without_depth=len(confidences.keys()-depths.keys()), dimensions=[list(d) for d in sorted(dimensions)],
            rgb_dimensions=list(rgb_shape), selected_runtime_skips=len(fitted.get('skipped_frames', [])),
            available_frames_failing_native_depth_count_guard=sum(not r['native_depth_count_guard_passes'] for r in rows)),
        aggregate_support={key: finish_aggregate(value, poly) for key, value in aggregates.items()},
        aggregate_signed_residual_histograms={key: value.tolist() for key, value in histograms.items()},
        fusion=fusion, frames=rows, off_lattice_witnesses=witnesses,
        input_sha256=frozen, sensor_sha256=source_hashes, script_sha256=sha256(__file__),
        runtime_s=time.perf_counter()-started, production_changed=False, geometry_changed=False, thresholds_changed=False,
        accuracy_validated=False, acceptance_claimed=False,
        limitations=['Dense pixel unions are repeated sensor observations, not native accepted fused planes',
            'All-frame selection comparison uses raw poses only; unselected refined poses do not exist',
            'Retained supplied sensor poses/depth are not independent physical ground truth',
            'Plane membership does not establish semantic floor identity or physical perimeter'])
    out.mkdir(parents=True)
    (out/'audit.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    compact = dict(source_inventory=result['source_inventory'], fusion=fusion,
        aggregate_support={mode: {name: {key: value for key, value in values.items() if key != 'cells'}
                          for name, values in stats.items()} for mode, stats in result['aggregate_support'].items()},
        runtime_s=result['runtime_s'])
    print(json.dumps(compact, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default='demo/phase3_strip_trace/current_exterior/ceiling')
    parser.add_argument('--source', default='datasets/Given_dataset/single_scan_with_ceiling/c7d28f72c6')
    parser.add_argument('--room', default='room_2')
    parser.add_argument('--plane', type=int, default=1)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    run(args.run, args.source, args.room, args.plane, args.out)
