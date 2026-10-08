"""Read-only temporal-attachment and exact triangle witnesses for batch024.

Consumes saved models and the landmark audit; final observations are never
treated as the unavailable initial registration inlier sets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.provenance import sha256
from scripts.audit_late_landmarks import SUMMARIES, TARGET, shape_diagnostics, pose_condition
from scripts.audit_transition_odometry import verify_retained_summaries
from scripts.audit_transition_tracks import spatial_support
from scripts.compare_transition_context import immutable_trial_files


def run(trial, audit, out):
    import pycolmap
    started=time.perf_counter();trial,audit,out=[Path(p).resolve() for p in (trial,audit,out)]
    if out.exists() or any(out==p or p in out.parents or out in p.parents for p in (trial,audit)):
        raise ValueError('Attachment output must be a new separate directory')
    preserved=verify_retained_summaries(SUMMARIES)
    frozen=immutable_trial_files([trial,audit])
    record=json.loads((audit/'audit.json').read_text(encoding='utf-8'))
    if sha256('scripts/audit_late_landmarks.py')!=record['script_sha256']:
        raise ValueError('Landmark-audit source differs from retained execution')
    payload=json.loads((audit/'landmarks.json').read_text(encoding='utf-8'))
    if sha256(audit/'landmarks.json')!=record['landmarks_sha256']:
        raise ValueError('Landmark payload changed')
    target=next(p for p in payload['pairs'] if p['images']==list(TARGET))
    experiment=json.loads((trial/'experiment.json').read_text(encoding='utf-8'))
    model=pycolmap.Reconstruction(trial/'sparse'/str(experiment['models'][0]['model_id']))
    images={i.name:i for i in model.images.values() if i.has_pose}
    poses=json.loads(Path('demo/phase3_mapping_only/evaluation/evaluation.json').read_text(encoding='utf-8'))['trials'][0][0]
    stamps={v['image']:v['source_timestamp_s'] for v in poses['registered_timeline']}
    sets={n:{int(p.point3D_id) for p in i.points2D if p.has_point3D()} for n,i in images.items()}
    late={n for n in images if stamps[n]>=stamps[TARGET[0]]};early=set(images)-late
    anchor=set.union(*(sets[n] for n in early))
    memberships={str(pid):sorted({model.images[e.image_id].name for e in model.points3D[pid].track.elements})
                 for pid in target['shared_landmark_ids']}
    by_group={n:dict(saved_landmarks=len(sets[n]),landmarks_seen_in_earlier_views=len(sets[n]&anchor),
        earlier_support=[dict(image=k,shared_landmarks=len(sets[n]&sets[k])) for k in sorted(early) if sets[n]&sets[k]])
        for n in sorted(late)}
    anchored_geometry={}
    for first,second in (('frame_00022.png','frame_00023.png'),TARGET):
        before={n for n in images if stamps[n]<stamps[first]}
        prior=set.union(*(sets[n] for n in before))
        rows={}
        for name in (first,second):
            ids=sorted(sets[name]&prior);image=images[name];camera=model.cameras[image.camera_id]
            pixels=[p.xy for p in image.points2D if p.has_point3D() and int(p.point3D_id) in ids]
            points=np.array([model.points3D[p].xyz for p in ids])
            local=np.array([image.cam_from_world()*p for p in points])
            rows[name]=dict(landmark_ids=ids,count=len(ids),
                pixel_support=spatial_support(pixels,(camera.width,camera.height)),
                shape=shape_diagnostics(points),pose_condition=pose_condition(local,camera.calibration_matrix()))
        anchored_geometry[first+'->'+second]=rows
    with sqlite3.connect((trial/'features.db').as_uri()+'?mode=ro',uri=True) as db:
        count,columns,blob=db.execute('SELECT rows,cols,data FROM keypoints WHERE image_id=?',
                                    (images[TARGET[1]].image_id,)).fetchone()
    coords=np.frombuffer(blob,np.float32).reshape(count,columns)[:,:2]
    witnesses=[]
    for row in target['indexed_correspondences']:
        triangles=row['verified_triangle_support']
        if not triangles:continue
        for conflict in triangles['conflicting']:
            alternative=coords[conflict['feature_b_composed']]
            witnesses.append(dict(feature_a=row['feature_a'],feature_b=row['feature_b'],
                point3D_id=row['shared_point3D_id'],native_status=row['final_native_status'],**conflict,
                pixel_b=row['pixel_b'],alternative_pixel_b=alternative.tolist(),
                separation_b_px=float(np.linalg.norm(alternative-np.asarray(row['pixel_b'])))))
    if any(sha256(p)!=h for p,h in {**preserved,**frozen}.items()):
        raise ValueError('Attachment audit mutated retained data')
    result=dict(experiment='saved_late_temporal_attachment_audit',target_memberships=memberships,
        target_shared_landmarks_with_earlier_support=sum(bool(set(v)&early) for v in memberships.values()),
        target_only_late_landmarks=sum(not bool(set(v)&early) for v in memberships.values()),
        target_view_membership_histogram=[dict(images=list(k),landmarks=sum(v==list(k) for v in memberships.values()))
            for k in sorted({tuple(v) for v in memberships.values()})],
        native_earlier_attachment=by_group,anchored_geometry=anchored_geometry,
        local_triangle_witnesses=witnesses,registration_inlier_sets_available=False,
        reconstruction_changed=False,reconstruction_rerun=False,sensor_poses_used_only_posthoc=True,
        physical_accuracy_validated=False,assessment_acceptance=False,
        input_sha256=frozen,retained_prior_hash_entries_checked=len(preserved),script_sha256=sha256(__file__),
        runtime_s=time.perf_counter()-started)
    out.mkdir(parents=True)
    (out/'attachment.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('target_shared_landmarks_with_earlier_support','target_only_late_landmarks',
        'native_earlier_attachment','local_triangle_witnesses','runtime_s')},indent=2),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trial',default='demo/phase3_mapping_only/trial1')
    p.add_argument('--audit',default='demo/phase3_late_landmarks/audit1')
    p.add_argument('--out',required=True)
    a=p.parse_args();run(a.trial,a.audit,a.out)
