"""Post-hoc odometry/track audit of the frozen-inlier mapping-only ablation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from floorplan.provenance import sha256
from scripts.audit_transition_odometry import audit_model, percentiles, read_odometry, verify_retained_summaries
from scripts.audit_transition_tracks import audit_trial
from scripts.compare_transition_context import immutable_trial_files, model_safety
from scripts.evaluate_fixed_intrinsics import matched_pair_comparison, solver_warning_count
from scripts.evaluate_xfeat_context import cached_track_spreads
from scripts.experimental_mapping_only import RETAINED_SUMMARIES, require_retained_tables, require_same_options
from scripts.experimental_video_bridge import baseline_digest


def pair_metrics(audit):
    if 'selected_pairs' not in audit:
        return []
    rows = audit['selected_pairs'] + audit['transition_anchor_comparisons'] + audit['adjacent']
    metrics = ('relative_rotation_error_deg', 'translation_direction_error_deg', 'relative_length_ratio')
    pairs = {(v['image_a'],v['image_b']):v for v in rows}
    return [dict(image_a=a, image_b=b, **{k:v[k] for k in metrics}) for (a,b),v in pairs.items()
            if (a == 'frame_00024.png' and b in {'frame_00027.png','frame_00028.png',
                'frame_00031.png','frame_00034.png','frame_00037.png'}) or
                (a,b) == ('frame_00027.png','frame_00028.png')]


def common_adjacent_metrics(audits):
    available = {k:v for k,v in audits.items() if 'adjacent' in v}
    if not available:
        return {}
    # Compare exact same pair identities, not different adjacent timelines when
    # the number of registered views differs.
    pair_sets = [{(r['image_a'],r['image_b']) for r in v['adjacent']} for v in available.values()]
    common = set.intersection(*pair_sets)
    result = {}
    for name, audit in available.items():
        rows = [v for v in audit['adjacent'] if (v['image_a'],v['image_b']) in common]
        result[name] = dict(spans=len(rows),
            rotation_error_deg=percentiles([v['relative_rotation_error_deg'] for v in rows]),
            direction_error_deg=percentiles([v['translation_direction_error_deg'] for v in rows]),
            relative_length_ratio=percentiles([v['relative_length_ratio'] for v in rows]))
    return result


def evaluate(root, out):
    root, out = [Path(p).resolve() for p in (root, out)]
    if out.exists() or out == root or out in root.parents:
        raise ValueError('Evaluation output must be a new directory')
    preserved = verify_retained_summaries(RETAINED_SUMMARIES)
    trials = [root/f'trial{i}' for i in (1,2)]
    frozen = immutable_trial_files(trials)
    old_path = Path('demo/phase3_transition_odometry/audit1/audit.json')
    fixed_path = Path('demo/phase3_fixed_intrinsics/evaluation2/evaluation.json')
    old = json.loads(old_path.read_text(encoding='utf-8'))
    fixed = json.loads(fixed_path.read_text(encoding='utf-8'))
    baseline = json.loads(Path('demo/phase3_xfeat_context/trial2/experiment.json').read_text(encoding='utf-8'))
    previous = json.loads(Path('demo/phase3_fixed_intrinsics/trial1/experiment.json').read_text(encoding='utf-8'))
    source_tables = baseline_digest('demo/phase3_xfeat_context/trial2/features.db')
    records = [json.loads((p/'experiment.json').read_text(encoding='utf-8')) for p in trials]
    for record, trial in zip(records,trials):
        require_same_options(previous['options'], record['options'])
        require_retained_tables(source_tables, baseline_digest(trial/'features.db'))
        if (record['temporal_window'] != baseline['temporal_window']
                or record['image_sha256'] != baseline['image_sha256']
                or record['poses_used_in_reconstruction'] or record['previous_optimized_poses_used']
                or record['verification_rerun'] or record['matching_rerun']):
            raise ValueError('Mapping-only candidate changed inputs or consumed poses/frontend')
        if any(sha256(trial/'images'/n) != h for n,h in baseline['image_sha256'].items()):
            raise ValueError('RGB changed; old timing/pixel evidence cannot be reused')
    # Sensor poses are first read here, after both saved reconstructions exist.
    rows = read_odometry('datasets/Given_dataset/single_room/c00a170fe1/odometry.csv')
    out.mkdir(parents=True)
    audited = []
    for trial, record in zip(trials,records):
        models = []
        for saved in record['models']:
            if {'frame_00019.png','frame_00024.png'} <= set(saved['image_names']):
                models.append(audit_model(trial/'sparse'/str(saved['model_id']), record, old['alignment'], rows))
            else:
                models.append(dict(registered_views=saved['registered_images'],
                    unavailable_reason='Missing common 19->24 reference; no concatenation or assumed scale'))
        audited.append(models)
    repeat = dict(database_tables_exact=baseline_digest(trials[0]/'features.db') == baseline_digest(trials[1]/'features.db'),
        model_binaries_exact=[m['binary_sha256'] for m in records[0]['models']] ==
                             [m['binary_sha256'] for m in records[1]['models']],
        model_memberships_exact=[m['image_names'] for m in records[0]['models']] ==
                                [m['image_names'] for m in records[1]['models']],
        graph_exact=records[0]['graph'] == records[1]['graph'], posthoc_pose_metrics_exact=audited[0] == audited[1])
    safety_dir = out/'safety'; safety_dir.mkdir()
    with cached_track_spreads() as cache:
        safety = audit_trial(trials[0], safety_dir)
    safety['native_model_safety'] = model_safety(trials[0], records[0])
    safety['diagnostic_cache'] = cache
    (safety_dir/'safety.json').write_text(json.dumps(safety,indent=2)+'\n',encoding='utf-8')
    candidate = audited[0][0] if audited[0] else {}
    comparisons = dict(free_intrinsics=matched_pair_comparison(old['trials'][0],candidate) if 'selected_pairs' in candidate else [],
        fixed_with_reverification=matched_pair_comparison(fixed['trials'][0][0],candidate) if 'selected_pairs' in candidate else [])
    audits = dict(free_intrinsics=old['trials'][0], fixed_with_reverification=fixed['trials'][0][0],
                  mapping_only=candidate)
    warnings = [solver_warning_count(f'demo/mapping_only_trial{i}_native.log') for i in (1,2)]
    if any(sha256(p) != h for p,h in {**preserved,**frozen}.items()):
        raise ValueError('Retained source/evidence or candidate mutated during read-only audit')
    result = dict(experiment='mapping_only_fixed_intrinsics_withheld_odometry_audit',
        trials=audited, comparisons=comparisons, common_adjacent=common_adjacent_metrics(audits),
        transition_metrics={k:pair_metrics(v) for k,v in audits.items()}, repeat=repeat,
        safety_sha256=sha256(safety_dir/'safety.json'), source_trial_sha256=frozen,
        retained_hashes_checked=len(preserved), retained_artifacts_unchanged=True,
        mapper_linear_solver_warnings=warnings, script_sha256=sha256(__file__),
        old_audit_sha256=sha256(old_path), previous_fixed_audit_sha256=sha256(fixed_path),
        control_runtime_s=[r['runtime_s'] for r in records],
        original_verified_rows_preserved=True, verification_rerun=False, matching_rerun=False,
        sensor_poses_used_in_reconstruction=False, sensor_poses_used_to_correct_or_optimize=False,
        model_alignment_or_scale_fit=False, physical_accuracy_validated=False, assessment_acceptance=False)
    (out/'evaluation.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(transition_metrics=result['transition_metrics'],repeat=repeat,
        mapper_linear_solver_warnings=warnings,tracks=safety['tracks'],
        cycles={k:v for k,v in safety['cycles'].items() if k!='rows'},
        native_model_safety=safety['native_model_safety']),indent=2), flush=True)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',default='demo/phase3_mapping_only')
    p.add_argument('--out',required=True)
    a = p.parse_args(); evaluate(a.root,a.out)
