"""Close the final frame31 diagnostic from saved evidence; never rerun mapping.

An unreproduced native continuation cannot identify the original registration,
triangulation or refinement cause. No sensor files are opened by this auditor.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from floorplan.provenance import sha256
from scripts.audit_registration_support import SUMMARIES
from scripts.audit_transition_odometry import verify_retained_summaries
from scripts.experimental_fixed_intrinsics import check_saved_intrinsics
from scripts.experimental_mapping_only import require_pose_free_database
from scripts.experimental_registration_stage import BINARIES, require_snapshot_reproduction
from scripts.experimental_video_bridge import baseline_digest

STAGES = ('before_registration', 'accepted_registration', 'after_triangulation',
          'after_local_refinement', 'after_global_refinement', 'after_frame_filter',
          'after_color_extraction')
RETAINED = SUMMARIES + ['docs/results/phase3_registration_support_summary.json']


def replay_gate(source, before, expected, final):
    """Require exact input state; record output failure without accepting poses."""
    initial = require_snapshot_reproduction(source, before)
    raw_equal = {name: sha256(Path(expected)/name) == sha256(Path(final)/name)
                 for name in sorted(BINARIES)}
    try:
        reproduced = require_snapshot_reproduction(expected, final)
        error = None
    except ValueError as exc:
        reproduced = dict(model_state_exact=False, numeric_tolerance_used=False)
        error = str(exc)
    return dict(input_reproduction=initial, output_reproduction=reproduced,
                final_raw_binary_equality=raw_equal, failure=error,
                intermediate_interpretation_allowed=error is None)


def native_interval(log, image_id, next_id):
    """Read only the original registration interval, excluding upstream warnings."""
    start = f'Registering image #{image_id} ('
    end = f'Registering image #{next_id} ('
    if log.count(start) != 1 or log.count(end) != 1:
        raise ValueError('Original registration interval is ambiguous or absent')
    a, b = log.index(start), log.index(end)
    if b <= a:
        raise ValueError('Original registration interval is out of order')
    return log[a:b]


def logged_stages(log):
    names = '|'.join(STAGES)
    rows = re.findall(rf'^({names}) (\d+) (\d+)[ \t\r]*$', log, re.MULTILINE)
    if tuple(row[0] for row in rows) != STAGES:
        raise ValueError('Incomplete or reordered native stage log')
    return {name: (int(views), int(points)) for name, views, points in rows}


def run(source, trial, log_path, original_log_path, out):
    import pycolmap
    if pycolmap.__version__ != '4.2.1':
        raise ValueError('Saved native models require pinned PyCOLMAP4.2.1')
    source, trial, log_path, original_log_path, out = map(Path,
        (source, trial, log_path, original_log_path, out))
    if out.exists() or not out.parent.is_dir():
        raise ValueError('Use a fresh audit JSON in an existing output directory')
    frozen = verify_retained_summaries(RETAINED)
    record_path = source/'experiment.json'
    record = json.loads(record_path.read_text(encoding='utf-8'))
    entries = record['snapshots'][26:28]
    if [r['registered_images'] for r in entries] != [29, 30]:
        raise ValueError('Expected exactly the retained frame31 interval')
    for entry in entries:
        if {p.name: sha256(p) for p in Path(entry['path']).glob('*.bin')} != entry['binary_sha256']:
            raise ValueError('Source snapshot changed')
    require_pose_free_database(source/'features.db')
    require_pose_free_database(trial/'features.db')
    tables = baseline_digest(source/'features.db')
    if tables != baseline_digest(trial/'features.db'):
        raise ValueError('Replay changed cameras, features, matches or verified rows')
    rgb = {name: sha256(source/'images'/name) for name in record['image_sha256']}
    if len(rgb) != 32 or rgb != record['image_sha256']:
        raise ValueError('Retained32 RGB inputs changed')
    log = log_path.read_text(encoding='utf-8')
    original = native_interval(original_log_path.read_text(encoding='utf-8'), 28, 31)
    counts = logged_stages(log)
    if 'selected [28, 31]' not in log or 'support 107 479' not in log:
        raise ValueError('Native frame31 selection or support changed')
    cameras = {int(k): v for k, v in record['camera_parameters'].items()}
    stages = []
    for name in STAGES:
        path = trial/name
        model = pycolmap.Reconstruction(path)
        count = (model.num_reg_images(), model.num_points3D())
        if count != counts[name]:
            raise ValueError('Saved model counts do not match native log')
        stages.append(dict(stage=name, registered_views=count[0], sparse_points=count[1],
            fixed_intrinsics=check_saved_intrinsics(model, cameras),
            path=str(path.resolve()), binary_sha256={n: sha256(path/n) for n in sorted(BINARIES)}))
    gate = replay_gate(entries[0]['path'], trial/STAGES[0], entries[1]['path'], trial/STAGES[-1])
    if gate['failure'] and gate['failure'] not in log:
        raise ValueError('Recorded native failure differs from saved model failure')
    if any(sha256(p) != h for p, h in frozen.items()):
        raise ValueError('Previous pinned evidence changed during read-only audit')
    result = dict(experiment='final_frame31_saved_replay_gate', native_reconstruction_rerun=False,
        source_snapshot_index=26, expected_snapshot_index=27, registered_image_id=28,
        registered_image_name='frame_00031.png', stages=stages, reproduction=gate,
        source_database_tables=tables, image_sha256=rgb,
        native_solver_warnings=log.count('Linear solver failure'),
        original_interval_solver_warnings=original.count('Linear solver failure'),
        original_interval=original, sensor_files_opened=False, sensor_stage_audit_performed=False,
        earlier_states_traced=False, frozen_hashes_checked=len(frozen),
        investigation_closed=True, production_changed=False, production_adoption=False,
        root_cause_classification=('INSUFFICIENT_SAVED_STATE_EVIDENCE' if gate['failure']
                                   else 'REPRODUCED_NOT_CAUSALLY_AUDITED'),
        earliest_trusted_landmark_stage='Retained snapshot27, after frame31 registration and refinement',
        prior_supported_hypothesis='Inherited local geometry bias with concentrated support; not proven',
        accuracy_validated=False, acceptance_claimed=False,
        input_sha256={str(p.resolve()): sha256(p) for p in (record_path, log_path, original_log_path)},
        script_sha256=sha256(__file__))
    out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(snapshot27_reproduced=gate['failure'] is None,
        intermediate_interpretation_allowed=gate['intermediate_interpretation_allowed'],
        native_solver_warnings=result['native_solver_warnings'], investigation_closed=True), indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='demo/phase3_registration_snapshots/trial1')
    parser.add_argument('--trial', default='demo/phase3_frame31_final/probe')
    parser.add_argument('--log', default='demo/phase3_frame31_final/native_api_probe.log')
    parser.add_argument('--original-log', default='demo/phase3_registration_snapshots/trial1_native.log')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    result = run(args.source, args.trial, args.log, args.original_log, args.out)
    # Distinguish an executed evidence audit from a successful replay experiment.
    raise SystemExit(2 if result['reproduction']['failure'] else 0)
