"""Isolated fixed-calibration control over retained XFeat feature/match indices.

Export whitelists intrinsic CSV columns. Mapping takes that pose-free JSON only;
sensor poses, saved camera poses, learned inference and production are excluded.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from PIL import Image
from floorplan.provenance import sha256
from floorplan.sfm import _matching_diagnostics
from scripts.diagnostics.audit_transition_odometry import verify_retained_summaries
from scripts.experiments.experimental_transition_context import copy_context_database, group_model_status
from scripts.experiments.experimental_transition_matchers import frozen_options, geometry_report
from scripts.experiments.experimental_video_bridge import baseline_digest, shortest_bridge

SUMMARIES = ['benchmarks/results/transition_context_summary.json',
             'benchmarks/results/xfeat_context_summary.json',
             'benchmarks/results/transition_odometry_summary.json']
CAMERA_FIELDS = {'image', 'sensor_frame', 'width', 'height', 'fx', 'fy', 'cx', 'cy'}
ALLOWED_OPTION_PATHS = {'mapping.ba_refine_focal_length', 'mapping.ba_refine_extra_params',
    'mapping.constant_cameras', 'mapping.mapper.constant_cameras',
    'mapping.mapper.abs_pose_refine_focal_length', 'mapping.mapper.abs_pose_refine_extra_params'}


def serialize(options):
    return json.loads(json.dumps(options.todict(), default=str))


def flatten(value, prefix=''):
    if not isinstance(value, dict):
        return {prefix: value}
    return {path: item for key, child in value.items()
            for path, item in flatten(child, f'{prefix}.{key}' if prefix else key).items()}


def option_diff(baseline, candidate):
    before, after = flatten(baseline), flatten(candidate)
    differences = {k: dict(before=before.get(k), after=after.get(k))
                   for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
    if set(differences)-ALLOWED_OPTION_PATHS:
        raise ValueError('Control changed verification/mapping guards outside intrinsic policy')
    return differences


def fixed_options(pycolmap, baseline, camera_ids):
    verification, mapper = frozen_options(pycolmap, baseline)
    mapper.ba_refine_focal_length = False
    mapper.ba_refine_principal_point = False  # Already false in the frozen recipe.
    mapper.ba_refine_extra_params = False
    mapper.mapper.abs_pose_refine_focal_length = False
    mapper.mapper.abs_pose_refine_extra_params = False
    mapper.constant_cameras = set(camera_ids)
    mapper.mapper.constant_cameras = set(camera_ids)
    if mapper.use_prior_position:
        raise ValueError('Sensor pose optimization must be disabled')
    candidate = copy.deepcopy(baseline['options'])
    candidate.update(verification=serialize(verification), mapping=serialize(mapper))
    return verification, mapper, candidate, option_diff(baseline['options'], candidate)


def validate_calibration(record, names):
    if set(record) != {'schema', 'source_sha256', 'alignment_audit_sha256', 'views'}:
        raise ValueError('Calibration JSON must contain only declared provenance and intrinsics')
    if record['schema'] != 'isolated-optical-intrinsics-v1':
        raise ValueError('Unsupported calibration schema')
    views = record['views']
    if len(views) != len(names) or [v['image'] for v in views] != list(names):
        raise ValueError('Calibration does not match the ordered retained views')
    for v in views:
        if set(v) != CAMERA_FIELDS:
            raise ValueError('Calibration view contains undeclared fields or sensor poses')
        if (not isinstance(v['sensor_frame'], int) or v['sensor_frame'] < 0
                or not isinstance(v['width'], int) or not isinstance(v['height'], int)
                or min(v['width'], v['height']) <= 0):
            raise ValueError('Invalid calibration identity or dimensions')
        values = np.array([v[k] for k in ('fx', 'fy', 'cx', 'cy')], dtype=float)
        if (not np.isfinite(values).all() or min(v['fx'], v['fy']) <= 0
                or v['fx'] != v['fy'] or not 0 <= v['cx'] < v['width']
                or not 0 <= v['cy'] < v['height']):
            raise ValueError('Calibration is incompatible with unchanged SIMPLE_RADIAL camera model')
    if np.any(np.diff([v['sensor_frame'] for v in views]) <= 0):
        raise ValueError('Calibration sensor identities are not strictly increasing')
    return views


def export_calibration(source, audit, images, output):
    source, audit, images, output = map(Path, (source, audit, images, output))
    if output.exists():
        raise ValueError('Calibration output already exists')
    evidence = json.loads(audit.read_text(encoding='utf-8'))
    expected = evidence['input_sha256'].get(str(source.resolve()))
    if not expected or sha256(source) != expected:
        raise ValueError('Odometry source differs from the verified timing audit')
    if not all(p['pixels_exact'] for p in evidence['pixel_witnesses']):
        raise ValueError('RGB identity is not verified')
    with source.open(encoding='utf-8', newline='') as stream:
        # The export intentionally never parses position, orientation or IMU columns.
        rows = [{k: row[k] for k in ('frame', 'fx', 'fy', 'cx', 'cy')}
                for row in csv.DictReader(stream, skipinitialspace=True)]
    views = []
    for v in evidence['alignment']['views']:
        row = rows[v['sensor_frame']]
        if int(row['frame']) != v['sensor_frame']:
            raise ValueError('Exported calibration frame identity differs')
        with Image.open(images/v['image']) as image:
            width, height = image.size
        views.append(dict(image=v['image'], sensor_frame=v['sensor_frame'], width=width, height=height,
                          **{k: float(row[k]) for k in ('fx', 'fy', 'cx', 'cy')}))
    record = dict(schema='isolated-optical-intrinsics-v1', source_sha256=sha256(source),
                  alignment_audit_sha256=sha256(audit), views=views)
    validate_calibration(record, [v['image'] for v in evidence['alignment']['views']])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    return record


def apply_intrinsics(database, views):
    with sqlite3.connect(database) as db:
        if db.execute('SELECT COUNT(*) FROM pose_priors').fetchone()[0]:
            raise ValueError('Control database contains sensor pose priors')
        if db.execute('SELECT COUNT(*) FROM rig_sensors').fetchone()[0]:
            raise ValueError('Expected single-camera frames with no supplied rig extrinsics')
        cameras = {}
        for v in views:
            row = db.execute('SELECT c.camera_id,c.model,c.width,c.height FROM cameras c '
                             'JOIN images i ON c.camera_id=i.camera_id WHERE i.name=?', (v['image'],)).fetchone()
            if not row or row[1:] != (2, v['width'], v['height']):
                raise ValueError('Control requires unchanged SIMPLE_RADIAL image dimensions')
            camera_id = row[0]
            if camera_id in cameras:
                raise ValueError('Expected independent per-frame calibration identities')
            params = np.array([v['fx'], v['cx'], v['cy'], 0.], dtype=np.float64)
            db.execute('UPDATE cameras SET params=?,prior_focal_length=1 WHERE camera_id=?',
                       (params.tobytes(), camera_id))
            cameras[camera_id] = params.tolist()
        # Force verification under the supplied calibration, not stale F/E records.
        db.execute('DELETE FROM two_view_geometries')
    return cameras


def candidates_from_database(database, names):
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True) as db:
        ids = dict(db.execute('SELECT image_id,name FROM images'))
        pairs = db.execute('SELECT pair_id,rows FROM matches ORDER BY pair_id').fetchall()
    rank = {n: i for i, n in enumerate(names)}
    result = []
    for pair, count in pairs:
        a, b = ids[pair//2147483647], ids[pair%2147483647]
        if rank[a] > rank[b]: a, b = b, a
        result.append(dict(image_a=a, image_b=b, candidate_matches=count))
    if len(result) != len(names)*(len(names)-1)//2:
        raise ValueError('Retained candidate table is incomplete')
    return sorted(result, key=lambda p: (rank[p['image_a']], rank[p['image_b']]))


def check_saved_intrinsics(model, expected):
    changes = []
    for camera in model.cameras.values():
        if camera.model_name != 'SIMPLE_RADIAL' or not np.array_equal(camera.params, expected[camera.camera_id]):
            changes.append(camera.camera_id)
    if changes:
        raise ValueError(f'Native mapping changed fixed intrinsics: {changes}')
    return dict(checked_cameras=len(model.cameras), maximum_parameter_change=0., all_exact=True)


def run(baseline, calibration, out):
    import pycolmap
    start = time.perf_counter()
    baseline, calibration, out = [Path(p).resolve() for p in (baseline, calibration, out)]
    if out.exists() or out == baseline or baseline in out.parents or out in baseline.parents:
        raise ValueError('Control output must be a new directory separate from retained inputs')
    if pycolmap.__version__ != '4.2.1':
        raise ValueError('PyCOLMAP version differs from the frozen pin')
    frozen = verify_retained_summaries(SUMMARIES)
    record = json.loads((baseline/'experiment.json').read_text(encoding='utf-8'))
    names = [v['image'] for v in record['temporal_window']]
    cal = json.loads(calibration.read_text(encoding='utf-8'))
    views = validate_calibration(cal, names)
    if len(names) != 32:
        raise ValueError('Control must preserve all 32 retained inputs, including unregistered context')
    hashes = {str(calibration): sha256(calibration), str(baseline/'experiment.json'): sha256(baseline/'experiment.json')}
    source_tables = baseline_digest(baseline/'features.db')
    out.mkdir(parents=True); images = out/'images'; images.mkdir()
    for name, digest in record['image_sha256'].items():
        if sha256(baseline/'images'/name) != digest:
            raise ValueError('Retained RGB changed')
        shutil.copy2(baseline/'images'/name, images/name)
    database = out/'features.db'
    copy_context_database(baseline/'features.db', database, names, True, pycolmap)
    expected = apply_intrinsics(database, views)
    verification, mapper, options, differences = fixed_options(pycolmap, record, expected)
    candidates = candidates_from_database(database, names)
    pair_file = out/'pairs.txt'
    pair_file.write_text('\n'.join(f"{v['image_a']} {v['image_b']}" for v in candidates)+'\n')
    setup = dict(input_sha256=hashes, image_sha256=record['image_sha256'],
                 temporal_window=record['temporal_window'], camera_parameters=expected,
                 calibration=cal, options=options, option_changes=differences,
                 poses_used_in_reconstruction=False, previous_optimized_poses_used=False,
                 correspondence_scope='retained post-verification raw rows; sub-15 rows were already cleared',
                 retained_candidate_matches=sum(v['candidate_matches'] for v in candidates))
    (out/'setup.json').write_text(json.dumps(setup, indent=2)+'\n')
    stage = time.perf_counter(); pycolmap.verify_matches(database, pair_file, options=verification)
    verify_runtime = time.perf_counter()-stage
    graph = geometry_report(database, names, candidates)
    groups = record['target_groups']
    graph['target_group_path'] = shortest_bridge(names,
        [(v['image_a'], v['image_b']) for v in graph['pairs'] if v['verified_inliers']],
        set(groups[0]) & set(names), set(groups[1]) & set(names))
    after = baseline_digest(database)
    retained = {t: source_tables[t] == after[t] for t in ('images', 'keypoints', 'descriptors', 'matches')}
    if not all(retained.values()):
        raise ValueError('Control changed retained feature or raw match indices')
    (out/'verified_frontend.json').write_text(json.dumps(dict(graph=graph, retained_tables_exact=retained), indent=2)+'\n')
    sparse = out/'sparse'; sparse.mkdir(); stage = time.perf_counter()
    models = pycolmap.incremental_mapping(database, images, sparse, options=mapper)
    mapping_runtime = time.perf_counter()-stage
    summaries = []
    for key, model in models.items():
        registered = sorted(i.name for i in model.images.values() if i.has_pose)
        summaries.append(dict(model_id=key, image_names=registered, registered_images=len(registered),
            sparse_points=model.num_points3D(), mean_reprojection_error_px=model.compute_mean_reprojection_error(),
            both_endpoints_registered={'frame_00024.png','frame_00027.png'}.issubset(registered),
            **group_model_status(registered, groups), fixed_intrinsics=check_saved_intrinsics(model, expected),
            binary_sha256={p.name: sha256(p) for p in (sparse/str(key)).glob('*.bin')}))
    result = dict(**setup, experiment='retained_xfeat_fixed_per_frame_intrinsics_control', mode='xfeat_fixed_intrinsics',
        graph=graph, models=summaries, target_groups=groups, matching_diagnostics=_matching_diagnostics(database, len(names)),
        total_registered_images=len({n for m in summaries for n in m['image_names']}),
        joint_endpoint_model=any(m['both_endpoints_registered'] for m in summaries),
        joint_target_group_model=any(m['both_target_groups_registered'] for m in summaries),
        retained_tables_exact=retained, script_sha256=sha256(__file__), frozen_hashes_checked=len(frozen),
        runtime_s=time.perf_counter()-start, stage_runtime_s=dict(verification_s=verify_runtime, mapping_s=mapping_runtime),
        production_changed=False, production_adoption=False, accuracy_validated=False, metric_scale=False)
    for path, digest in {**frozen, **hashes}.items():
        if sha256(path) != digest:
            raise ValueError('Control mutated retained evidence or source')
    (out/'experiment.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('models', 'joint_endpoint_model', 'total_registered_images', 'runtime_s')}, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    export = commands.add_parser('export')
    export.add_argument('--source', default='datasets/Given_dataset/single_room/c00a170fe1/odometry.csv')
    export.add_argument('--audit', default='demo/phase3_transition_odometry/audit1/audit.json')
    export.add_argument('--images', default='demo/phase3_xfeat_context/trial2/images')
    export.add_argument('--out', required=True)
    mapping = commands.add_parser('map')
    mapping.add_argument('--baseline', default='demo/phase3_xfeat_context/trial2')
    mapping.add_argument('--calibration', required=True)
    mapping.add_argument('--out', required=True)
    args = parser.parse_args()
    if args.command == 'export': export_calibration(args.source, args.audit, args.images, args.out)
    else: run(args.baseline, args.calibration, args.out)
