"""Isolated stride4 LiDAR control with frozen frames/poses and unchanged guards.

No pose estimation, matching, sensor correction or production configuration change.
Only raw depth sampling differs. Increased coverage is not measured accuracy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import cv2
import numpy as np
from shapely.geometry import Polygon

from floorplan.layout import extract_layout, weighted_voxels
from floorplan.provenance import sha256
from floorplan.rgbd import _backproject, _fit_planes


def sample_depth(raw, confidence, camera, scale, minimum_confidence, maximum_depth, stride):
    if stride not in (4, 8) or isinstance(stride, bool):
        raise ValueError('This isolated control supports only strides4/8')
    if raw.ndim != 2 or raw.shape != confidence.shape:
        raise ValueError('Depth/confidence dimensions must match')
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Depth scale must be finite and positive')
    depth = raw.astype(float)/scale
    valid = (np.isfinite(depth) & (depth >= .2) & (depth <= maximum_depth)
             & (confidence >= minimum_confidence))
    yy, xx = np.mgrid[0:raw.shape[0]:stride, 0:raw.shape[1]:stride]
    mask = valid[yy, xx].ravel()
    pixels = np.column_stack((xx.ravel()[mask], yy.ravel()[mask]))
    z = depth[yy, xx].ravel()[mask]
    weights = (confidence[yy, xx].ravel()[mask].astype(float)+1)/np.maximum(z, .5)**2
    return _backproject(pixels, z, camera), weights, pixels


def rooms_in_source_frame(rooms, source_metadata, candidate_metadata):
    """Project through the known sensor-world bases, without fitting an alignment."""
    source = np.asarray(source_metadata['basis_columns_in_input'], float)
    candidate = np.asarray(candidate_metadata['basis_columns_in_input'], float)
    floor = candidate_metadata['wall_sampling_slab_bound_m']
    if (source.shape != (3,3) or candidate.shape != (3,3)
            or not np.isfinite(source).all() or not np.isfinite(candidate).all()
            or not np.isfinite(floor)):
        raise ValueError('Finite known floor bases and datum are required')
    transformed = []
    for room in rooms:
        xz = np.asarray(room['corners'], float)
        xyz = np.column_stack((xz[:,0], np.full(len(xz),floor), xz[:,1]))
        transformed.append({**room, 'corners': ((xyz@candidate.T)@source)[:,[0,2]].tolist()})
    return transformed


def compare_rooms(before, after):
    """Report preservation and movement, without making an accuracy claim."""
    rows = []
    for room in before:
        a = Polygon(room['corners'])
        options = []
        for candidate in after:
            b = Polygon(candidate['corners'])
            overlap = a.intersection(b).area
            options.append((overlap/a.union(b).area, overlap, candidate, b))
        if not options:
            rows.append(dict(source_room=room['id'], retained=False)); continue
        iou, overlap, candidate, b = max(options, key=lambda row: row[:2])
        rows.append(dict(source_room=room['id'], candidate_room=candidate['id'],
            source_inferred=bool(room.get('requires_boundary_review')),
            candidate_inferred=bool(candidate.get('requires_boundary_review')),
            corners_exact=json.loads(json.dumps(room['corners'])) == json.loads(json.dumps(candidate['corners'])),
            intersection_over_union=float(iou), source_area_m2=float(a.area), candidate_area_m2=float(b.area),
            boundary_hausdorff_m=float(a.boundary.hausdorff_distance(b.boundary)),
            source_area_retained_fraction=float(overlap/a.area)))
    return rows


def run(run, source, out):
    start = time.perf_counter()
    run, source, out = map(lambda p: Path(p).resolve(), (run, source, out))
    if out.exists() or any(out == p or p in out.parents or out in p.parents for p in (run, source)):
        raise ValueError('Output must be fresh and separate from retained captures')
    ledger = json.loads((run/'run.json').read_text(encoding='utf-8'))
    sequence = json.loads((run/'normalized_sequence.json').read_text(encoding='utf-8'))
    summary = json.loads((run/'artifacts/rgbd_summary.json').read_text(encoding='utf-8'))
    meta = json.loads((run/'artifacts/layout_evidence.json').read_text(encoding='utf-8'))
    before = json.loads((run/'plan.json').read_text(encoding='utf-8'))['rooms']
    trajectory = json.loads((run/'artifacts/trajectory.json').read_text(encoding='utf-8'))
    poses = {p['frame_id']: np.asarray(p['camera_to_first']) for p in trajectory}
    code = {str(p.resolve()): sha256(p) for p in Path('floorplan').rglob('*.py')}
    dependencies = ('layout.py', 'rgbd.py', 'supported_cells.py')
    if any(ledger['code_sha256'][n] != sha256(Path('floorplan')/n) for n in dependencies):
        raise ValueError('Retained geometry producer differs from current baseline')
    frozen = {str((run/n).resolve()): sha256(run/n) for n in
        ['run.json','plan.json','normalized_sequence.json']+list(ledger['geometry_artifact_sha256'])}
    if any(sha256(run/n) != digest for n,digest in ledger['geometry_artifact_sha256'].items()):
        raise ValueError('Retained geometry artifacts changed')
    out.mkdir(parents=True)
    clouds = {4: [], 8: []}; weights = {4: [], 8: []}; frames = []; sensors = {}
    for frame in sequence['frames']:
        fid = frame['id']
        if fid not in poses:
            continue
        dp, cp = (run/frame[name] for name in ('depth', 'confidence'))
        for path, original in ((dp, source/'depth'/f'{fid:06d}.png'),
                               (cp, source/'confidence'/f'{fid:06d}.png')):
            if sha256(path) != sha256(original):
                raise ValueError('Original depth/confidence extraction is not byte-identical')
            sensors[str(original)] = sha256(original)
        raw = cv2.imread(str(dp), cv2.IMREAD_UNCHANGED)
        confidence = cv2.imread(str(cp), cv2.IMREAD_UNCHANGED)
        k = frame.get('intrinsics', sequence['intrinsics'])
        matrix = np.array([[k['fx'],0,k['cx']],[0,k['fy'],k['cy']],[0,0,1.]])
        pose = poses[fid]; row = dict(frame_id=fid, input_depth_shape=list(raw.shape))
        for stride in (8, 4):
            xyz, weight, _ = sample_depth(raw, confidence, matrix, sequence['depth_scale'],
                sequence.get('minimum_confidence',1), sequence.get('depth_max_m',8.), stride)
            clouds[stride].append(xyz@pose[:3,:3].T+pose[:3,3]); weights[stride].append(weight)
            row[f'stride{stride}_accepted_points'] = len(xyz)
        frames.append(row)
    if len(frames) != len(trajectory):
        raise ValueError('All and only retained sensor frames must be replayed')
    baseline = np.load(run/'artifacts/cloud.npz')['points']
    replay, _, _ = weighted_voxels(np.concatenate(clouds[8]), weights=np.concatenate(weights[8]))
    if not np.array_equal(baseline, replay):
        raise ValueError('Stride8 fusion does not reproduce baseline exactly')
    dense, _, dense_weights = weighted_voxels(np.concatenate(clouds[4]), weights=np.concatenate(weights[4]))
    np.savez_compressed(out/'stride4_cloud.npz', points=dense, weights=dense_weights)
    planes = _fit_planes(dense)
    matrices = np.asarray([p['camera_to_first'] for p in trajectory])
    down = ledger['configuration'].get('down_direction', matrices[0,:3,1])
    rooms, candidate = extract_layout(dense, planes, matrices[:,:3,3], down,
        path_breaks=meta.get('path_breaks',()), wall_support_policy=meta.get('wall_support_policy','local_spatial'))
    (out/'stride4_layout.json').write_text(json.dumps(dict(rooms=rooms,metadata=candidate,planes=planes),indent=2),encoding='utf-8')
    result = dict(experiment='supplied_floor_stride4_frozen_pose_control', frames=len(frames),
        input_frames_identical=True, refined_sensor_poses_frozen=True, pose_optimization_rerun=False,
        matching_rerun=False, verification_rerun=False, production_changed=False,
        baseline_cloud_reproduced_exact=True, baseline_point_count=len(baseline), candidate_point_count=len(dense),
        baseline_coverage_fraction=meta['camera_center_coverage_fraction'],
        candidate_coverage_fraction=candidate['camera_center_coverage_fraction'],
        baseline_stages=meta['boundary_stages'], candidate_stages=candidate['boundary_stages'],
        baseline_cells=len(before), candidate_cells=len(rooms),
        room_comparison=compare_rooms(before,rooms_in_source_frame(rooms,meta,candidate)),
        comparison_frame='baseline floor basis via known sensor-world bases; no fitted alignment or scale',
        per_frame_sampling=frames,
        depth_confidence_shape=list(raw.shape), input_sha256=frozen, sensor_sha256=sensors,
        production_code_sha256=code, script_sha256=sha256(__file__),
        independent_ground_truth_available=False, accuracy_validated=False, acceptance_claimed=False,
        limitations=['Same supplied sensor poses and frames, not independent survey truth',
            'Coverage measures camera positions, not floor-area accuracy',
            'A changed boundary requires sensor support validation before adoption'],
        runtime_s=time.perf_counter()-start)
    if any(sha256(p) != h for p,h in {**frozen,**code,**sensors}.items()):
        raise ValueError('Retained inputs or production code changed during control')
    (out/'experiment.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default='demo/phase3_strip_trace/current_exterior/floor')
    parser.add_argument('--source', default='datasets/Given_dataset/single_scan_floor_only/1a8384c3f6')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    r = run(args.run, args.source, args.out)
    print(json.dumps({k:r[k] for k in ('baseline_cloud_reproduced_exact','baseline_point_count',
        'candidate_point_count','baseline_coverage_fraction','candidate_coverage_fraction',
        'baseline_stages','candidate_stages','room_comparison','runtime_s')},indent=2))
