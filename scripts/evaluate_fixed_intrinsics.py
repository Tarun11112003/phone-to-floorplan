"""Evaluate fixed-intrinsics controls with the unchanged withheld-odometry audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from floorplan.provenance import sha256
from scripts.audit_transition_odometry import audit_model, read_odometry, verify_retained_summaries, percentiles
from scripts.audit_transition_tracks import audit_trial
from scripts.compare_transition_context import immutable_trial_files, model_safety
from scripts.evaluate_xfeat_context import cached_track_spreads
from scripts.experimental_fixed_intrinsics import SUMMARIES, option_diff
from scripts.experimental_video_bridge import baseline_digest


def solver_warning_count(path):
    raw = Path(path).read_bytes()
    # Windows PowerShell redirects native output as UTF-16; the explicit Python
    # subprocess logger writes UTF-8. Decode losslessly, without ignoring errors.
    encoding = 'utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'
    return raw.decode(encoding).count('Linear solver failure.')


def matched_pair_comparison(before, after):
    def pairs(record):
        rows = record['selected_pairs'] + record['transition_anchor_comparisons'] + record['adjacent']
        return {(v['image_a'], v['image_b']): v for v in rows}
    old, new = pairs(before), pairs(after)
    keys = [('frame_00019.png','frame_00024.png'), ('frame_00024.png','frame_00027.png'),
            ('frame_00024.png','frame_00028.png'), ('frame_00027.png','frame_00028.png')]
    metrics = ('relative_rotation_error_deg','translation_direction_error_deg','relative_length_ratio',
               'candidate_length_model_units','sensor_length_m')
    return [dict(image_a=a,image_b=b, before={k:old[(a,b)][k] for k in metrics},
                 after={k:new[(a,b)][k] for k in metrics})
            for a,b in keys if (a,b) in old and (a,b) in new]


def evaluate(root, out):
    root, out = [Path(p).resolve() for p in (root, out)]
    if out.exists() or out == root or out in root.parents:
        raise ValueError('Evaluation output must be a new directory')
    preserved = verify_retained_summaries(SUMMARIES)
    trials = [root/f'trial{i}' for i in (1,2)]
    frozen = immutable_trial_files(trials)
    old_path = Path('demo/phase3_transition_odometry/audit1/audit.json')
    old = json.loads(old_path.read_text(encoding='utf-8'))
    rows = read_odometry('datasets/Given_dataset/single_room/c00a170fe1/odometry.csv')
    records = [json.loads((p/'experiment.json').read_text(encoding='utf-8')) for p in trials]
    baseline = json.loads(Path('demo/phase3_xfeat_context/trial2/experiment.json').read_text())
    for record, trial in zip(records,trials):
        option_diff(baseline['options'], record['options'])
        if (record['temporal_window'] != baseline['temporal_window']
                or record['image_sha256'] != baseline['image_sha256']
                or record['poses_used_in_reconstruction'] or record['previous_optimized_poses_used']):
            raise ValueError('Candidate changed RGB inputs or consumed poses')
        if any(sha256(trial/'images'/n) != h for n,h in baseline['image_sha256'].items()):
            raise ValueError('Control images changed; prior pixel witnesses cannot be reused')
    out.mkdir(parents=True)
    audited = []
    for index, (trial, record) in enumerate(zip(trials,records),1):
        models = []
        for saved in record['models']:
            if {'frame_00019.png','frame_00024.png'} <= set(saved['image_names']):
                models.append(audit_model(trial/'sparse'/str(saved['model_id']), record, old['alignment'], rows))
            else:
                models.append(dict(registered_views=saved['registered_images'],
                    unavailable_reason='No common 19->24 reference; no cross-model concatenation or assumed scale'))
        audited.append(models)
    repeat = dict(database_tables_exact=baseline_digest(trials[0]/'features.db') == baseline_digest(trials[1]/'features.db'),
                  model_binaries_exact=[m['binary_sha256'] for m in records[0]['models']] ==
                                       [m['binary_sha256'] for m in records[1]['models']],
                  model_memberships_exact=[m['image_names'] for m in records[0]['models']] ==
                                          [m['image_names'] for m in records[1]['models']],
                  graph_exact=records[0]['graph'] == records[1]['graph'], posthoc_pose_metrics_exact=audited[0] == audited[1])
    safety_dir = out/'safety'; safety_dir.mkdir()
    with cached_track_spreads() as cache:
        safety = audit_trial(trials[0],safety_dir)
    safety['native_model_safety'] = model_safety(trials[0],records[0])
    safety['diagnostic_cache'] = cache
    (safety_dir/'safety.json').write_text(json.dumps(safety,indent=2)+'\n')
    comparison = matched_pair_comparison(old['trials'][0],audited[0][0]) if audited[0] and 'selected_pairs' in audited[0][0] else []
    common_names = {v['image'] for v in old['trials'][0]['registered_timeline']}
    common_adjacent = {}
    for label, pose_audit in (('free',old['trials'][0]),('fixed',audited[0][0])):
        if 'adjacent' in pose_audit:
            common = [v for v in pose_audit['adjacent'] if v['image_a'] in common_names and v['image_b'] in common_names]
            common_adjacent[label] = dict(spans=len(common),
                rotation_error_deg=percentiles([v['relative_rotation_error_deg'] for v in common]),
                direction_error_deg=percentiles([v['translation_direction_error_deg'] for v in common]),
                relative_length_ratio=percentiles([v['relative_length_ratio'] for v in common]))
    warnings = [solver_warning_count(f'demo/fixed_intrinsics_trial{i}.log') for i in (1,2)]
    if any(sha256(p) != h for p,h in {**preserved,**frozen}.items()):
        raise ValueError('Retained evidence or completed controls mutated during evaluation')
    result = dict(experiment='fixed_intrinsics_withheld_odometry_comparison', trials=audited,
        before_after=comparison, common_adjacent=common_adjacent, repeat=repeat,
        safety_sha256=sha256(safety_dir/'safety.json'), source_trial_sha256=frozen,
        retained_hashes_checked=len(preserved), retained_artifacts_unchanged=True,
        mapper_linear_solver_warnings=warnings, script_sha256=sha256(__file__),
        old_audit_sha256=sha256(old_path), control_runtime_s=[r['runtime_s'] for r in records],
        sensor_poses_used_in_reconstruction=False, sensor_poses_used_to_correct_or_optimize=False,
        model_alignment_or_scale_fit=False, physical_accuracy_validated=False, assessment_acceptance=False)
    (out/'evaluation.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(before_after=comparison,repeat=repeat,
        mapper_linear_solver_warnings=warnings,tracks=safety['tracks'],
        cycles={k:v for k,v in safety['cycles'].items() if k!='rows'},
        native_model_safety=safety['native_model_safety']),indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default='demo/phase3_fixed_intrinsics')
    parser.add_argument('--out',required=True)
    args = parser.parse_args(); evaluate(args.root,args.out)
