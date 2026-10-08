"""Native snapshot replay of batch023; no frontend or pose-prior inference.

Only snapshot output fields differ. Refuse to interpret intermediate models
unless the final model and complete feature database reproduce the baseline.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from floorplan.provenance import sha256
from scripts.audit_transition_odometry import verify_retained_summaries
from scripts.experimental_fixed_intrinsics import check_saved_intrinsics, fixed_options, flatten, serialize
from scripts.experimental_mapping_only import RETAINED_SUMMARIES, require_pose_free_database, require_same_options
from scripts.experimental_transition_context import copy_context_database, group_model_status
from scripts.experimental_video_bridge import baseline_digest

SUMMARIES = RETAINED_SUMMARIES + ['docs/results/phase3_mapping_only_summary.json',
                                'docs/results/phase3_late_landmarks_summary.json']
OUTPUT_FIELDS = {'mapping.snapshot_path', 'mapping.snapshot_frames_freq'}


def require_diagnostic_options(baseline, candidate, snapshot_path):
    before, after = flatten(baseline), flatten(candidate)
    diff = {k: dict(before=before.get(k), after=after.get(k))
            for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
    if (set(diff) != OUTPUT_FIELDS or after['mapping.snapshot_frames_freq'] != 1
            or after['mapping.snapshot_path'] != str(Path(snapshot_path).resolve())):
        raise ValueError('Replay may change only native snapshot output fields')
    return diff


def require_final_baseline(expected, actual, before_tables, after_tables):
    if before_tables != after_tables:
        raise ValueError('Replay changed the retained feature/camera database')
    keys = ('model_id', 'image_names', 'registered_images', 'sparse_points',
            'mean_reprojection_error_px', 'binary_sha256')
    if len(expected) != len(actual) or any(
            {k:a[k] for k in keys} != {k:b[k] for k in keys}
            for a,b in zip(expected, actual)):
        raise ValueError('Final replay does not reproduce baseline bytes and metrics')
    return dict(model_binaries_exact=True, model_metrics_exact=True, database_tables_exact=True)


def native_snapshot_mapping(native, database, images, sparse, mapper):
    # Deliberately use the same entry point, without callbacks or continuation.
    return native.incremental_mapping(database, images, sparse, options=mapper)


def run(baseline, frontend, out):
    import pycolmap
    start = time.perf_counter()
    baseline, frontend, out = map(lambda p: Path(p).resolve(), (baseline, frontend, out))
    if out.exists() or any(out == p or p in out.parents or out in p.parents for p in (baseline, frontend)):
        raise ValueError('Replay output must be fresh and separate from retained inputs')
    if pycolmap.__version__ != '4.2.1':
        raise ValueError('Replay requires the retained PyCOLMAP 4.2.1 pin')
    frozen = verify_retained_summaries(SUMMARIES)
    record = json.loads((baseline/'experiment.json').read_text(encoding='utf-8'))
    original = json.loads((frontend/'experiment.json').read_text(encoding='utf-8'))
    if record['mode'] != 'xfeat_mapping_only_fixed' or original['mode'] != 'xfeat_lighterglue':
        raise ValueError('Expected retained mapping-only and XFeat frontend controls')
    names = [v['image'] for v in record['temporal_window']]
    if len(names) != 32 or record['image_sha256'] != original['image_sha256']:
        raise ValueError('Replay must preserve all original 32 RGB inputs')
    if record['temporal_window'] != original['temporal_window']:
        raise ValueError('Replay view timing/order differs from original inputs')
    require_pose_free_database(baseline/'features.db')
    source_tables = baseline_digest(baseline/'features.db')
    expected = {int(k):v for k,v in record['camera_parameters'].items()}
    _, mapper, options, _ = fixed_options(pycolmap, original, expected)
    require_same_options(record['options'], options)
    out.mkdir(parents=True); images = out/'images'; images.mkdir()
    snapshots = out/'snapshots'; snapshots.mkdir()
    for name,digest in record['image_sha256'].items():
        if sha256(baseline/'images'/name) != digest:
            raise ValueError('Retained RGB input changed')
        shutil.copy2(baseline/'images'/name, images/name)
    database = out/'features.db'
    copy_context_database(baseline/'features.db', database, names, True, pycolmap)
    if baseline_digest(database) != source_tables:
        raise ValueError('Copied database is not identical by retained table rows')
    require_pose_free_database(database)
    mapper.snapshot_path = snapshots
    mapper.snapshot_frames_freq = 1
    diagnostic = copy.deepcopy(options)
    diagnostic['mapping'] = serialize(mapper)
    differences = require_diagnostic_options(record['options'], diagnostic, snapshots)
    setup = dict(experiment='native_per_registration_snapshot_replay',
        baseline=str(baseline), frontend=str(frontend), options=diagnostic,
        option_changes=differences, image_sha256=record['image_sha256'],
        temporal_window=record['temporal_window'], camera_parameters=record['camera_parameters'],
        source_database_tables=source_tables, input_sha256={str(p):sha256(p) for p in
            (baseline/'experiment.json', frontend/'experiment.json')},
        poses_used_in_reconstruction=False, previous_optimized_poses_used=False,
        matching_rerun=False, verification_rerun=False, snapshot_callback_used=False)
    (out/'setup.json').write_text(json.dumps(setup,indent=2)+'\n',encoding='utf-8')
    sparse = out/'sparse'; sparse.mkdir(); stage = time.perf_counter()
    models = native_snapshot_mapping(pycolmap, database, images, sparse, mapper)
    mapping_s = time.perf_counter()-stage
    summaries = []
    for key,model in sorted(models.items()):
        registered = sorted(i.name for i in model.images.values() if i.has_pose)
        summaries.append(dict(model_id=key, image_names=registered, registered_images=len(registered),
            sparse_points=model.num_points3D(), mean_reprojection_error_px=model.compute_mean_reprojection_error(),
            binary_sha256={p.name:sha256(p) for p in (sparse/str(key)).glob('*.bin')},
            fixed_intrinsics=check_saved_intrinsics(model,expected),
            **group_model_status(registered,record['target_groups'])))
    reproduction = require_final_baseline(record['models'],summaries,source_tables,baseline_digest(database))
    paths = sorted(p for p in snapshots.iterdir() if p.is_dir())
    if not paths:
        raise ValueError('Native mapper produced no snapshots')
    inventory = []
    for p in paths:
        model = pycolmap.Reconstruction(p)
        inventory.append(dict(path=str(p),registered_images=model.num_reg_images(),
            image_names=sorted(i.name for i in model.images.values() if i.has_pose),
            sparse_points=model.num_points3D(), fixed_intrinsics=check_saved_intrinsics(model,expected),
            binary_sha256={b.name:sha256(b) for b in p.glob('*.bin')}))
    if any(sha256(p) != digest for p,digest in frozen.items()):
        raise ValueError('Replay mutated prior pinned evidence')
    result = dict(**setup,models=summaries,snapshots=inventory,final_baseline_reproduction=reproduction,
        graph=record['graph'],target_groups=record['target_groups'],
        mapping_runtime_s=mapping_s,runtime_s=time.perf_counter()-start,
        frozen_hashes_checked=len(frozen),script_sha256=sha256(__file__),
        production_changed=False,production_adoption=False,accuracy_validated=False)
    (out/'experiment.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(models=summaries,snapshots=len(inventory),reproduction=reproduction,
                         mapping_runtime_s=mapping_s),indent=2),flush=True)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',default='demo/phase3_mapping_only/trial1')
    p.add_argument('--frontend',default='demo/phase3_xfeat_context/trial2')
    p.add_argument('--out',required=True)
    a = p.parse_args(); run(a.baseline,a.frontend,a.out)
