"""Map original XFeat verified rows with fixed calibration; no frontend rerun.

The input is batch020's database, not batch022's reverified database. Batch022
supplies only the pose-free calibration and frozen option recipe for comparison.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.provenance import sha256
from floorplan.sfm import _matching_diagnostics
from scripts.audit_transition_odometry import verify_retained_summaries
from scripts.experimental_fixed_intrinsics import (SUMMARIES, candidates_from_database,
    check_saved_intrinsics, fixed_options, validate_calibration)
from scripts.experimental_transition_context import copy_context_database, group_model_status
from scripts.experimental_transition_matchers import geometry_report
from scripts.experimental_video_bridge import baseline_digest, shortest_bridge

RETAINED_SUMMARIES = SUMMARIES + ['docs/results/phase3_fixed_intrinsics_summary.json']
FROZEN_TABLES = ('images', 'keypoints', 'descriptors', 'matches', 'two_view_geometries')


def require_pose_free_database(database):
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True) as db:
        if db.execute('SELECT COUNT(*) FROM pose_priors').fetchone()[0]:
            raise ValueError('Sensor pose priors must not enter mapping')
        if db.execute('SELECT COUNT(*) FROM rig_sensors').fetchone()[0]:
            raise ValueError('Supplied rig extrinsics must not enter this single-camera control')
        # Original batch020 has no cached relative poses or camera blobs. Retain
        # its F/E/H and verified inliers exactly, but reject a different source.
        if db.execute('SELECT COUNT(*) FROM two_view_geometries WHERE '
                      'qvec IS NOT NULL OR tvec IS NOT NULL OR '
                      'camera1 IS NOT NULL OR camera2 IS NOT NULL').fetchone()[0]:
            raise ValueError('Expected original verified rows without cached poses/cameras')


def apply_mapping_intrinsics(database, views):
    """Update cameras only, preserving every verified row and its F/E/H blobs."""
    require_pose_free_database(database)
    cameras = {}
    with sqlite3.connect(database) as db:
        for v in views:
            row = db.execute('SELECT c.camera_id,c.model,c.width,c.height FROM cameras c '
                             'JOIN images i ON c.camera_id=i.camera_id WHERE i.name=?', (v['image'],)).fetchone()
            if not row or row[1:] != (2, v['width'], v['height']):
                raise ValueError('Expected unchanged SIMPLE_RADIAL image dimensions')
            camera_id = row[0]
            if camera_id in cameras:
                raise ValueError('Expected independent per-frame calibration identities')
            params = np.array([v['fx'], v['cx'], v['cy'], 0.], dtype=np.float64)
            db.execute('UPDATE cameras SET params=?,prior_focal_length=1 WHERE camera_id=?',
                       (params.tobytes(), camera_id))
            cameras[camera_id] = params.tolist()
    return cameras


def require_retained_tables(source, candidate):
    same = {table: source[table] == candidate[table] for table in FROZEN_TABLES}
    if not all(same.values()):
        raise ValueError(f'Mapping-only control changed frozen frontend rows: {same}')
    return same


def require_same_options(control, candidate):
    if control != candidate:
        raise ValueError('Mapping-only recipe differs from batch022 fixed-intrinsics options')


def map_without_frontend(pycolmap, database, images, sparse, mapper):
    # No feature extraction, matching or verify_matches is called in this path.
    return pycolmap.incremental_mapping(database, images, sparse, options=mapper)


def run(baseline, control, calibration, out):
    import pycolmap
    start = time.perf_counter()
    baseline, control, calibration, out = [Path(p).resolve() for p in (baseline, control, calibration, out)]
    if out.exists() or any(out == p or p in out.parents or out in p.parents for p in (baseline, control)):
        raise ValueError('Output must be a new directory separate from retained trials')
    if pycolmap.__version__ != '4.2.1':
        raise ValueError('PyCOLMAP differs from the frozen pin')
    frozen = verify_retained_summaries(RETAINED_SUMMARIES)
    record = json.loads((baseline/'experiment.json').read_text(encoding='utf-8'))
    previous = json.loads((control/'experiment.json').read_text(encoding='utf-8'))
    if record['mode'] != 'xfeat_lighterglue' or previous['mode'] != 'xfeat_fixed_intrinsics':
        raise ValueError('Expected original batch020 XFeat rows and completed batch022 control')
    if (record['temporal_window'] != previous['temporal_window']
            or record['image_sha256'] != previous['image_sha256']):
        raise ValueError('Retained controls differ in input views')
    names = [v['image'] for v in record['temporal_window']]
    if len(names) != 32:
        raise ValueError('Preserve all 32 original inputs, including unregistered context')
    cal = json.loads(calibration.read_text(encoding='utf-8'))
    views = validate_calibration(cal, names)
    if cal != previous['calibration']:
        raise ValueError('Calibration differs from the preceding fixed-intrinsics control')
    require_pose_free_database(baseline/'features.db')
    source_tables = baseline_digest(baseline/'features.db')
    hashes = {str(p): sha256(p) for p in (calibration, baseline/'experiment.json', control/'experiment.json')}
    out.mkdir(parents=True); images = out/'images'; images.mkdir()
    for name, digest in record['image_sha256'].items():
        if sha256(baseline/'images'/name) != digest:
            raise ValueError('Retained RGB changed')
        shutil.copy2(baseline/'images'/name, images/name)
    database = out/'features.db'
    copy_context_database(baseline/'features.db', database, names, True, pycolmap)
    require_retained_tables(source_tables, baseline_digest(database))
    expected = apply_mapping_intrinsics(database, views)
    _, mapper, options, differences = fixed_options(pycolmap, record, expected)
    require_same_options(previous['options'], options)
    retained = require_retained_tables(source_tables, baseline_digest(database))
    candidates = candidates_from_database(database, names)
    graph = geometry_report(database, names, candidates)
    groups = record['target_groups']
    graph['target_group_path'] = shortest_bridge(names,
        [(v['image_a'], v['image_b']) for v in graph['pairs'] if v['verified_inliers']],
        set(groups[0]) & set(names), set(groups[1]) & set(names))
    setup = dict(input_sha256=hashes, image_sha256=record['image_sha256'],
        temporal_window=record['temporal_window'], camera_parameters=expected,
        calibration=cal, options=options, option_changes=differences,
        poses_used_in_reconstruction=False, previous_optimized_poses_used=False,
        correspondence_scope='original batch020 verified inliers and F/E/H, including zero-inlier records',
        matching_rerun=False, verification_rerun=False,
        retained_candidate_matches=sum(v['candidate_matches'] for v in candidates),
        source_database_tables=source_tables, retained_tables_exact=retained)
    (out/'setup.json').write_text(json.dumps(setup, indent=2)+'\n', encoding='utf-8')
    sparse = out/'sparse'; sparse.mkdir(); stage = time.perf_counter()
    models = map_without_frontend(pycolmap, database, images, sparse, mapper)
    mapping_runtime = time.perf_counter()-stage
    retained = require_retained_tables(source_tables, baseline_digest(database))
    summaries = []
    for key, model in models.items():
        registered = sorted(i.name for i in model.images.values() if i.has_pose)
        summaries.append(dict(model_id=key, image_names=registered, registered_images=len(registered),
            sparse_points=model.num_points3D(), mean_reprojection_error_px=model.compute_mean_reprojection_error(),
            both_endpoints_registered={'frame_00024.png','frame_00027.png'}.issubset(registered),
            **group_model_status(registered, groups), fixed_intrinsics=check_saved_intrinsics(model, expected),
            binary_sha256={p.name: sha256(p) for p in (sparse/str(key)).glob('*.bin')}))
    result = dict(**{k:v for k,v in setup.items() if k != 'retained_tables_exact'},
        experiment='mapping_only_fixed_intrinsics_original_verified_inliers', mode='xfeat_mapping_only_fixed',
        graph=graph, models=summaries, target_groups=groups,
        matching_diagnostics=_matching_diagnostics(database, len(names)),
        total_registered_images=len({n for m in summaries for n in m['image_names']}),
        joint_endpoint_model=any(m['both_endpoints_registered'] for m in summaries),
        joint_target_group_model=any(m['both_target_groups_registered'] for m in summaries),
        retained_tables_exact=retained, script_sha256=sha256(__file__), frozen_hashes_checked=len(frozen),
        runtime_s=time.perf_counter()-start, stage_runtime_s=dict(verification_s=0., mapping_s=mapping_runtime),
        production_changed=False, production_adoption=False, accuracy_validated=False, metric_scale=False)
    if any(sha256(p) != h for p,h in {**frozen, **hashes}.items()):
        raise ValueError('Mapping-only control mutated retained source/evidence')
    (out/'experiment.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('models','total_registered_images','joint_endpoint_model',
        'retained_tables_exact','runtime_s')}, indent=2), flush=True)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', default='demo/phase3_xfeat_context/trial2')
    p.add_argument('--control', default='demo/phase3_fixed_intrinsics/trial1')
    p.add_argument('--calibration', default='demo/phase3_fixed_intrinsics/calibration.json')
    p.add_argument('--out', required=True)
    a = p.parse_args(); run(a.baseline, a.control, a.calibration, a.out)
