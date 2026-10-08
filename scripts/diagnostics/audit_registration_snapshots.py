"""Post-hoc native stage audit; sensor poses never enter the replay runner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from floorplan.provenance import sha256
from scripts.diagnostics.audit_transition_odometry import (REFERENCE_PAIR, audit_model, motion,
    percentiles, read_odometry, relative_comparison, verify_retained_summaries)
from scripts.experiments.experimental_fixed_intrinsics import check_saved_intrinsics
from scripts.experiments.experimental_registration_snapshots import SUMMARIES, require_final_baseline
from scripts.experiments.experimental_video_bridge import baseline_digest

TARGET = ('frame_00031.png','frame_00034.png')
GLOBAL_MARKER = 'Retriangulation and Global bundle adjustment'
REGISTRATION = re.compile(r'Registering image #(\d+) \(num_reg_frames=(\d+)\)')


def snapshot_log_events(text):
    """Associate writes with log intervals, without labeling them raw PnP states."""
    events=[]; interval=[]
    for index,line in enumerate(text.splitlines(),1):
        match=REGISTRATION.search(line)
        if match:
            interval.append(dict(kind='registration_attempt',line=index,image_id=int(match[1]),
                                 registered_frames_before=int(match[2])))
        elif GLOBAL_MARKER in line:
            interval.append(dict(kind='global_refinement',line=index))
        elif 'Linear solver failure' in line:
            interval.append(dict(kind='solver_warning',line=index))
        elif 'Creating snapshot' in line:
            attempts=[e for e in interval if e['kind']=='registration_attempt']
            events.append(dict(snapshot_line=index,preceding_events=interval,
                last_registration_attempt=attempts[-1] if attempts else None,
                global_refinements=sum(e['kind']=='global_refinement' for e in interval),
                solver_warnings=sum(e['kind']=='solver_warning' for e in interval)))
            interval=[]
    return events,interval


def observation_residuals(model):
    """Recompute projections: native snapshot point.error can be stale before finalization."""
    residuals=[]; nonpositive=0
    for image in model.images.values():
        if not image.has_pose: continue
        observations=[p for p in image.points2D if p.has_point3D()]
        if not observations: continue
        xyz=np.array([model.points3D[p.point3D_id].xyz for p in observations])
        pixels=np.array([p.xy for p in observations])
        pose=image.cam_from_world()
        camera_xyz=xyz@pose.rotation.matrix().T+pose.translation
        good=camera_xyz[:,2]>0
        nonpositive+=int(np.count_nonzero(~good))
        projected=model.cameras[image.camera_id].img_from_cam(camera_xyz[good])
        residuals.extend(np.linalg.norm(projected-pixels[good],axis=1).tolist())
    return dict(observations=len(residuals)+nonpositive,nonpositive_depth=nonpositive,
        mean_observation_residual_px=float(np.mean(residuals)) if residuals else None,
        observation_residual_px=percentiles(residuals),
        definition='Euclidean per-observation reprojection recomputed read-only; distinct from final native per-point mean error')


def state_metrics(model,alignment,rows):
    stamps={v['image']:v for v in alignment['views']}
    candidate={i.name:dict(center=np.asarray(i.projection_center()),
               rotation=i.cam_from_world().rotation.matrix().T)
               for i in model.images.values() if i.has_pose}
    if not set(candidate)<=set(stamps): raise ValueError('Snapshot contains an undeclared view')
    sensors={name:rows[stamps[name]['sensor_frame']] for name in candidate}
    images={i.name:i for i in model.images.values() if i.has_pose}
    metrics={}
    if all(name in candidate for name in REFERENCE_PAIR):
        lengths=[float(np.linalg.norm(motion(p[REFERENCE_PAIR[0]],p[REFERENCE_PAIR[1]])[1]))
                 for p in (candidate,sensors)]
        if min(lengths)<=1e-12: raise ValueError('Snapshot reference motion is singular')
        for a,b in (TARGET,('frame_00022.png','frame_00023.png'),('frame_00028.png','frame_00031.png'),
                    ('frame_00024.png','frame_00034.png'),('frame_00034.png','frame_00037.png')):
            if a not in candidate or b not in candidate: continue
            comparison=relative_comparison(a,b,candidate,sensors,lengths,
                stamps[b]['sensor_timestamp_s']-stamps[a]['sensor_timestamp_s'])
            shared=({p.point3D_id for p in images[a].points2D if p.has_point3D()} &
                    {p.point3D_id for p in images[b].points2D if p.has_point3D()})
            comparison['shared_native_landmarks']=len(shared)
            metrics[f'{a}->{b}']=comparison
    return dict(registered_views=len(candidate),sparse_points=model.num_points3D(),
        image_names=sorted(candidate),joint_target_registered=set(TARGET)<=set(candidate),
        reference_registered=set(REFERENCE_PAIR)<=set(candidate),relative_motion=metrics,
        camera_poses={name:dict(center=pose['center'].tolist(),camera_to_world_rotation=pose['rotation'].tolist())
                      for name,pose in sorted(candidate.items())},
        reprojection=observation_residuals(model))


def saved_model_summary(native,path,model_id):
    path=Path(path); model=native.Reconstruction(path)
    return dict(model_id=model_id,image_names=sorted(i.name for i in model.images.values() if i.has_pose),
        registered_images=model.num_reg_images(),sparse_points=model.num_points3D(),
        mean_reprojection_error_px=model.compute_mean_reprojection_error(),
        binary_sha256={p.name:sha256(p) for p in path.glob('*.bin')})


def audit(trial,log,out,source_provenance):
    import pycolmap
    start=time.perf_counter()
    trial,log,out,source_provenance=map(Path,(trial,log,out,source_provenance))
    trial=trial.resolve(); out=out.resolve()
    if out.exists() or out==trial or trial in out.parents or out in trial.parents:
        raise ValueError('Audit output must be fresh and separate')
    frozen=verify_retained_summaries(SUMMARIES)
    record=json.loads((trial/'experiment.json').read_text())
    baseline=Path(record['baseline']); original=json.loads((baseline/'experiment.json').read_text())
    actual=[]; saved_baseline=[]
    for entry in record['models']:
        key=entry['model_id']
        actual.append(saved_model_summary(pycolmap,trial/'sparse'/str(key),key))
        saved_baseline.append(saved_model_summary(pycolmap,baseline/'sparse'/str(key),key))
    # Mandatory invariance gate happens BEFORE any sensor file is opened.
    tables=baseline_digest(baseline/'features.db'); replay_tables=baseline_digest(trial/'features.db')
    runtime_reproduction=require_final_baseline(original['models'],record['models'],tables,replay_tables)
    reproduction=require_final_baseline(saved_baseline,actual,
        tables,replay_tables)
    reproduction.update(runtime_summary_exact=runtime_reproduction['model_metrics_exact'],
        runtime_mean_error_px=record['models'][0]['mean_reprojection_error_px'],
        readback_mean_error_px=actual[0]['mean_reprojection_error_px'],
        comparison_method='Runtime against runtime; identical saved-model readback against readback; no numeric tolerance')
    expected={int(k):v for k,v in record['camera_parameters'].items()}
    provenance=json.loads(source_provenance.read_text())
    source_file=source_provenance.parent/'incremental_pipeline_4.2.1.cc'
    if sha256(source_file)!=provenance['sha256']:
        raise ValueError('Pinned snapshot call-site source changed')
    timing=json.loads(Path('demo/phase3_transition_odometry/audit1/audit.json').read_text())
    odometry=next(p for p in timing['input_sha256'] if Path(p).name=='odometry.csv')
    if sha256(odometry)!=timing['input_sha256'][odometry]: raise ValueError('Post-hoc odometry changed')
    rows=read_odometry(odometry); alignment=timing['alignment']
    events,tail=snapshot_log_events(log.read_text(encoding='utf-8'))
    if len(events)!=len(record['snapshots']): raise ValueError('Snapshot files/log writes do not align')
    stages=[]; previous=set()
    for index,(entry,event) in enumerate(zip(record['snapshots'],events)):
        path=Path(entry['path'])
        if {p.name:sha256(p) for p in path.glob('*.bin')}!=entry['binary_sha256']:
            raise ValueError('Snapshot bytes changed')
        model=pycolmap.Reconstruction(path); check_saved_intrinsics(model,expected)
        metrics=state_metrics(model,alignment,rows); current=set(metrics['image_names'])
        last=event['last_registration_attempt']
        if not last or not model.exists_image(last['image_id']) or not model.images[last['image_id']].has_pose:
            raise ValueError('Snapshot is not consistent with its native registration event')
        newly=current-previous
        if previous and newly!={model.images[last['image_id']].name}:
            raise ValueError('Snapshot registration order or frame filtering needs explicit review')
        stages.append(dict(index=index,path=str(path),stage='after registration, triangulation, local refinement and any triggered global refinement',
            newly_registered=sorted(newly),lost_views=sorted(previous-current),native_event=event,
            binary_sha256=entry['binary_sha256'],**metrics))
        previous=current
    final_model=pycolmap.Reconstruction(trial/'sparse'/'0'); check_saved_intrinsics(final_model,expected)
    final=dict(stage='final saved model after native finalization',**state_metrics(final_model,alignment,rows))
    full_final=audit_model(trial/'sparse'/'0',record,alignment,rows)
    target_key='->'.join(TARGET)
    joint=[s for s in stages if target_key in s['relative_motion']]
    result=dict(experiment='native_31_34_stage_history_audit',final_baseline_reproduction=reproduction,
        stages=stages,final=final,full_final_pose_audit=full_final,
        first_joint_snapshot_index=joint[0]['index'] if joint else None,
        post_last_snapshot_events=tail,native_source_provenance=provenance,
        snapshot_timing_limit='No raw accepted PnP or pre-local-BA state; cannot separate registration from immediate refinement',
        sensor_poses_used_in_inference=False,sensor_poses_used_to_optimize=False,
        pose_acceptance_tolerance=None,physical_accuracy_validated=False,assessment_acceptance=False,
        input_sha256={str(p.resolve()):sha256(p) for p in (trial/'experiment.json',log,source_provenance,Path(odometry))},
        frozen_hashes_checked=len(frozen),runtime_s=time.perf_counter()-start,script_sha256=sha256(__file__))
    if any(sha256(p)!=h for p,h in frozen.items()): raise ValueError('Audit mutated retained evidence')
    out.mkdir(parents=True)
    (out/'audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(first_joint_snapshot_index=result['first_joint_snapshot_index'],
        target_stages=[dict(index=s['index'],views=s['registered_views'],new=s['newly_registered'],
            global_refinements=s['native_event']['global_refinements'],**s['relative_motion'][target_key]) for s in joint],
        final=final['relative_motion'].get(target_key),reproduction=reproduction),indent=2),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trial',required=True); p.add_argument('--log',required=True); p.add_argument('--out',required=True)
    p.add_argument('--source-provenance',default='demo/phase3_registration_snapshots/source_provenance.json')
    a=p.parse_args(); audit(a.trial,a.log,a.out,a.source_provenance)
