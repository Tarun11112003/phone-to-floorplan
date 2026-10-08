"""Read-only post-hoc audit, gated on exact native snapshot reproduction."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.spatial.transform import Rotation
from floorplan.provenance import sha256
from scripts.audit_registration_snapshots import TARGET, state_metrics
from scripts.audit_transition_odometry import read_odometry, verify_retained_summaries
from scripts.experimental_fixed_intrinsics import check_saved_intrinsics
from scripts.experimental_registration_stage import RETAINED, require_snapshot_reproduction
from scripts.experimental_video_bridge import baseline_digest


def gate_saved_replay(record):
    """Check all saved stages and original frontend before opening sensor files."""
    for entry in record['stages']:
        actual={p.name:sha256(p) for p in Path(entry['path']).glob('*.bin')}
        if actual != entry['binary_sha256']:
            raise ValueError('Captured native stage changed')
    for entry in (record['source_snapshot'],record['expected_snapshot']):
        if {p.name:sha256(p) for p in Path(entry['path']).glob('*.bin')} != entry['binary_sha256']:
            raise ValueError('Retained native snapshot changed')
    for p,digest in record['input_sha256'].items():
        if sha256(p) != digest:
            raise ValueError('Replay source record changed')
    final=record['stages'][-1]
    if final['stage'] != 'after_color_extraction':
        raise ValueError('Incomplete native refinement sequence')
    check=require_snapshot_reproduction(record['expected_snapshot']['path'],final['path'])
    if check != record['snapshot_reproduction']:
        raise ValueError('Recorded reproduction evidence differs from saved models')
    if baseline_digest(Path(final['path']).parent/'features.db') != record['source_database_tables']:
        raise ValueError('Retained frontend rows changed')
    return check


def pose_changes(before,after):
    changes={}
    for name in TARGET:
        a,b=before['camera_poses'][name],after['camera_poses'][name]
        changes[name]=dict(rotation_change_deg=float(Rotation.from_matrix(
            np.array(a['camera_to_world_rotation']).T@np.array(b['camera_to_world_rotation'])
            ).magnitude()*180/np.pi),
            center_change_model_units=float(np.linalg.norm(np.array(a['center'])-np.array(b['center']))))
    return changes


def audit(trial,out):
    import pycolmap
    start=time.perf_counter(); trial,out=Path(trial).resolve(),Path(out).resolve()
    if out.exists() or out==trial or trial in out.parents or out in trial.parents:
        raise ValueError('Audit output must be fresh and separate')
    frozen=verify_retained_summaries(RETAINED)
    record_path=trial/'experiment.json'; record=json.loads(record_path.read_text(encoding='utf-8'))
    reproduction=gate_saved_replay(record)  # mandatory BEFORE sensor file access
    timing_path=Path('demo/phase3_transition_odometry/audit1/audit.json').resolve()
    timing=json.loads(timing_path.read_text(encoding='utf-8'))
    odometry=Path(next(p for p in timing['input_sha256'] if Path(p).name=='odometry.csv'))
    if sha256(odometry) != timing['input_sha256'][str(odometry)]:
        raise ValueError('Independent post-hoc odometry changed')
    rows=read_odometry(odometry); expected={int(k):v for k,v in record['camera_parameters'].items()}
    stages=[]
    for entry in record['stages']:
        model=pycolmap.Reconstruction(entry['path']); check_saved_intrinsics(model,expected)
        stages.append(dict(stage=entry['stage'],path=entry['path'],
            **state_metrics(model,timing['alignment'],rows)))
    retained=pycolmap.Reconstruction(record['expected_snapshot']['path'])
    retained_metrics=state_metrics(retained,timing['alignment'],rows)
    if stages[-1]['camera_poses'] != retained_metrics['camera_poses']:
        raise ValueError('Post-hoc retained camera poses not exact')
    if stages[-1]['relative_motion'] != retained_metrics['relative_motion']:
        raise ValueError('Post-hoc retained relative metrics not exact')
    final_path=Path(record['source'])/'sparse'/'0'
    final=state_metrics(pycolmap.Reconstruction(final_path),timing['alignment'],rows)
    target='->'.join(TARGET)
    if stages[1]['camera_poses'] != stages[2]['camera_poses']:
        raise ValueError('Triangulation unexpectedly altered saved poses')
    result=dict(experiment='native_accepted_registration_vs_local_refinement_audit',
        snapshot_reproduction=reproduction,stages=stages,retained_snapshot28=retained_metrics,
        retained_final_model=final,target=target,alignment=timing['alignment'],
        local_refinement_pose_changes=pose_changes(stages[2],stages[3]),
        triangulation_camera_poses_exact=True,retained_post_refinement_metrics_exact=True,
        sensor_poses_used_in_inference=False,sensor_poses_used_to_optimize=False,
        pose_acceptance_tolerance=None,physical_accuracy_validated=False,assessment_acceptance=False,
        comparison='Camera-to-world relative motion in first camera optical coordinates; relative length normalized by19->24, no odometry transform fit',
        input_sha256={str(p):sha256(p) for p in (record_path,timing_path,odometry)},
        script_sha256=sha256(__file__),frozen_hashes_checked=len(frozen),
        runtime_s=time.perf_counter()-start)
    if any(sha256(p)!=digest for p,digest in frozen.items()):
        raise ValueError('Prior pinned evidence changed')
    out.mkdir(parents=True)
    (out/'audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(stages=[dict(stage=s['stage'],registered_views=s['registered_views'],
        sparse_points=s['sparse_points'],target=s['relative_motion'].get(target),reprojection=s['reprojection'])
        for s in stages],local_refinement_pose_changes=result['local_refinement_pose_changes'],
        snapshot_reproduction=reproduction['model_state_exact'],runtime_s=result['runtime_s']),indent=2),flush=True)
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trial',required=True); p.add_argument('--out',required=True)
    a=p.parse_args(); audit(a.trial,a.out)
