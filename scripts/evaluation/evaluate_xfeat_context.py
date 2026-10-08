"""Audit two isolated XFeat trials against retained, never rerun, 32-view controls."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from floorplan.provenance import sha256
from scripts.diagnostics.audit_transition_tracks import audit_trial, draw_pair, track_components
from scripts.diagnostics.audit_transition_initialization import audit as initialization_audit
from scripts.evaluation.compare_transition_context import immutable_trial_files, group_track_status, model_safety, model_overlap_safety
from scripts.experiments.experimental_video_bridge import baseline_digest
import scripts.diagnostics.audit_transition_tracks as track_module


@contextmanager
def cached_track_spreads():
    """Memoize immutable audit components without changing the shared evaluator.

    Its per-observation comprehension otherwise rescans an entire component for
    every member. Hold references to prevent Python object-ID reuse. Coordinates
    and component membership are read-only throughout this diagnostic scope.
    """
    original=track_module.track_spread
    cache={};stats=dict(calls=0,component_computations=0,computed_nodes=0)
    def spread(nodes,coordinates):
        stats['calls']+=1
        key=(id(nodes),id(coordinates))
        if key not in cache:
            cache[key]=(nodes,coordinates,original(nodes,coordinates))
            stats['component_computations']+=1;stats['computed_nodes']+=len(nodes)
        return cache[key][2]
    track_module.track_spread=spread
    try: yield stats
    finally: track_module.track_spread=original


def assert_matched_context(reference, candidate):
    for field in ('image_sha256','options','production_code_sha256','temporal_window','target_groups','context_anchors'):
        if candidate[field]!=reference[field]: raise ValueError(f'Frozen context differs: {field}')
    if len(candidate['image_sha256'])!=32 or len(candidate['graph']['pairs'])!=496:
        raise ValueError('Expected the same 32 views and all 496 declared pairs')


def repeat_check(first, second, r1, r2):
    import pycolmap
    assert_matched_context(r1,r2)
    tables1,tables2=[baseline_digest(p/'features.db') for p in (first,second)]
    models=[]
    for m in r1['models']:
        other=next((n for n in r2['models'] if n['image_names']==m['image_names']),None)
        row=dict(images=m['image_names'],repeat_model_found=other is not None)
        if other:
            files=[];centers=[]
            for trial,saved in ((first,m),(second,other)):
                path=trial/'sparse'/str(saved['model_id'])
                hashes={p.name:sha256(p) for p in path.glob('*.bin')}
                if hashes!=saved['binary_sha256']: raise ValueError('Saved model bytes changed')
                files.append(hashes)
                model=pycolmap.Reconstruction(path)
                centers.append({i.name:i.projection_center() for i in model.images.values() if i.has_pose})
            row.update(binary_exact=files[0]==files[1],max_camera_center_difference=float(max(
                np.max(np.abs(centers[0][n]-centers[1][n])) for n in centers[0])))
        models.append(row)
    return dict(database_tables_exact={k:tables1[k]==tables2[k] for k in tables1},
        feature_outputs_exact=r1['identity']['feature_sha256']==r2['identity']['feature_sha256'],
        matcher_identity_exact=r1['identity']==r2['identity'],full_diagnostics_exact=r1['graph']==r2['graph'],
        models=models,all_model_memberships_reproduced=len(r1['models'])==len(r2['models'])
            and all(m['repeat_model_found'] for m in models))


def native_camera_metadata(trial):
    with sqlite3.connect((trial/'features.db').as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('SELECT COUNT(*) FROM pose_priors').fetchone()[0]:
            raise ValueError('Pose priors entered the RGB-only experiment')
        return {table:list(db.execute(f'SELECT * FROM {table} ORDER BY 1,2'))
                for table in ('cameras','images','rigs','rig_sensors','frames','frame_data')}


def shared_native_point(a, b):
    return bool(a.has_point3D() and b.has_point3D() and a.point3D_id==b.point3D_id)


def cross_group_native_support(trial, record, edges):
    """Retain every verified feature index; report native association, not truth."""
    import pycolmap
    rows=[];groups=list(map(set,record['target_groups']))
    for saved in record['models']:
        model=pycolmap.Reconstruction(trial/'sparse'/str(saved['model_id']))
        images={i.name:i for i in model.images.values() if i.has_pose}
        for a,b,matches in edges:
            if not ((a in groups[0] and b in groups[1]) or (a in groups[1] and b in groups[0])): continue
            observations=[]
            if a in images and b in images:
                for index,(ia,ib) in enumerate(matches):
                    pa,pb=images[a].points2D[int(ia)],images[b].points2D[int(ib)]
                    shared=shared_native_point(pa,pb)
                    observations.append(dict(display_index=index,feature_indices=[int(ia),int(ib)],
                        pixels=[pa.xy.tolist(),pb.xy.tolist()],has_3D=[pa.has_point3D(),pb.has_point3D()],
                        same_saved_point=shared,saved_point_error_px=model.points3D[pa.point3D_id].error if shared else None))
            rows.append(dict(model_id=saved['model_id'],image_a=a,image_b=b,verified_inliers=len(matches),
                both_images_registered=a in images and b in images,
                same_saved_point_matches=sum(r['same_saved_point'] for r in observations),observations=observations))
    return rows


def summarize(record, safety):
    pairs=record['graph']['pairs'];residuals=[r for r in record['graph']['sampson_residuals'] if r['available']]
    return dict(mode=record['mode'],candidate_pairs=len(pairs),candidate_matches=sum(p['candidate_matches'] for p in pairs),
        candidates_below_15=sum(p['candidate_matches']<15 for p in pairs),
        verified_pairs=record['graph']['verified_pairs'],component_sizes=list(map(len,record['graph']['components'])),
        isolated_views=record['graph']['isolated_views'],registered_views=record['total_registered_images'],
        models=record['models'],joint_target_group_model=record['joint_target_group_model'],
        joint_endpoint_model=record['joint_endpoint_model'],target_group_path=record['graph']['target_group_path'],
        maximum_sampson_px=max((r['max_px'] for r in residuals),default=None),
        geometry_configurations=record['matching_diagnostics']['verified_geometry_configurations'],
        tracks=safety['tracks'],cycles={k:v for k,v in safety['cycles'].items() if k!='rows'},
        group_tracks=safety['group_tracks'],native_model_safety=safety['native_model_safety'],
        runtime_s=record['runtime_s'],runtime_scope='cached features/pairs and diagnostic replay' if record['mode']=='sift'
                      else 'fresh features, all-pair matching, verification and mapping')


def evaluate(root, context, out):
    root,context,out=[Path(p).resolve() for p in (root,context,out)]
    folders=[root/'trial2',root/'trial3'];controls=[context/'sift1',context/'lightglue1']
    records=[json.loads((p/'experiment.json').read_text()) for p in folders]
    baselines=[json.loads((p/'experiment.json').read_text()) for p in controls]
    summary=json.loads(Path('benchmarks/results/transition_context_summary.json').read_text())
    for table in (summary['artifacts'],summary['source_trial_sha256'],summary['production_code_sha256']):
        if any(sha256(p)!=h for p,h in table.items()): raise ValueError('Retained baseline evidence changed')
    dependencies={str(Path(p).resolve()):sha256(p) for p in (__file__,
        'scripts/diagnostics/audit_transition_tracks.py','scripts/diagnostics/audit_transition_initialization.py',
        'scripts/evaluation/compare_transition_context.py','scripts/experiments/experimental_video_bridge.py')}
    for trial,record in zip(folders,records):
        assert_matched_context(baselines[0],record)
        if record['mode']!='xfeat_lighterglue': raise ValueError('Expected the declared XFeat trials')
        for table in (record['input_sha256'],record['dependency_sha256'],record['production_code_sha256']):
            if any(sha256(p)!=h for p,h in table.items()): raise ValueError('Trial inputs/recipe changed')
        if native_camera_metadata(trial)!=native_camera_metadata(controls[0]):
            raise ValueError('Initial camera/rig/frame/image metadata differs')
    frozen=immutable_trial_files(folders+controls)
    out.mkdir(parents=True,exist_ok=False)
    repeats=repeat_check(*folders,*records)
    with cached_track_spreads() as spread_stats:
        safety=audit_trial(folders[0],out)
    safety['diagnostic_spread_cache']=spread_stats
    safety['native_model_safety']=model_safety(folders[0],records[0])
    safety['model_overlap_safety']=model_overlap_safety(folders[0],records[0])
    safety['target_group_path']=records[0]['graph']['target_group_path']
    with sqlite3.connect((folders[0]/'features.db').as_uri()+'?mode=ro',uri=True) as db:
        ids=dict(db.execute('SELECT image_id,name FROM images'))
        coordinates={ids[i]:np.frombuffer(blob,np.float32).reshape(n,c)[:,:2]
            for i,n,c,blob in db.execute('SELECT * FROM keypoints')}
        edges=[(ids[p//2147483647],ids[p%2147483647],np.frombuffer(data,np.uint32).reshape(n,2))
            for p,n,data in db.execute('SELECT pair_id,rows,data FROM two_view_geometries WHERE rows>0 ORDER BY pair_id')]
    groups=records[0]['target_groups'];group_sets=list(map(set,groups))
    safety['group_tracks']=group_track_status(track_components(edges),groups)
    safety['direct_cross_group_pairs']=[p for p in records[0]['graph']['pairs'] if p['verified_inliers'] and (
        (p['image_a'] in group_sets[0] and p['image_b'] in group_sets[1]) or
        (p['image_b'] in group_sets[0] and p['image_a'] in group_sets[1]))]
    safety['direct_cross_group_native_support']=cross_group_native_support(folders[0],records[0],edges)
    selected={frozenset((p['image_a'],p['image_b'])) for p in safety['direct_cross_group_pairs']}
    selected.update(frozenset((a,b)) for a,b in zip(safety['target_group_path'][:-1],safety['target_group_path'][1:]))
    safety['cross_group_visualizations']=[]
    for a,b,m in edges:
        if frozenset((a,b)) in selected:
            path=out/f'group_{a}_{b}.jpg'
            draw_pair(folders[0],a,b,coordinates[a][m[:,0]],coordinates[b][m[:,1]],path)
            safety['cross_group_visualizations'].append(str(path))
    (out/'safety.json').write_text(json.dumps(safety,indent=2)+'\n',encoding='utf-8')
    initialization=initialization_audit(folders[0],out/'initialization')
    baseline_safety=[json.loads((context/'comparison2'/mode/'safety.json').read_text())
                     for mode in ('sift','lightglue')]
    results=[summarize(r,s) for r,s in zip(baselines+[records[0]],baseline_safety+[safety])]
    if any(sha256(p)!=h for p,h in frozen.items()): raise ValueError('Scientific trial artifacts changed during audit')
    if any(sha256(p)!=h for p,h in dependencies.items()): raise ValueError('Diagnostic recipe changed during audit')
    result=dict(experiment='matched_32_view_xfeat_lighterglue_evaluation',runs=results,
        repeat_checks=repeats,repeat_runtime_s=[r['runtime_s'] for r in records],
        stage_runtime_s=[r['stage_runtime_s'] for r in records],identity=records[0]['identity'],
        source_trial_sha256=frozen,report_sha256={str(p/'experiment.json'):sha256(p/'experiment.json') for p in folders+controls},
        script_sha256=sha256(__file__),dependency_sha256=dependencies,native_initialization=initialization,
        downstream_guards_identical=True,previous_optimized_poses_used=False,production_changed=False,
        production_adoption=False,physical_accuracy_validated=False,assessment_acceptance=False,
        floor_covered_samples=25,floor_total_samples=176,ceiling_boundary_shift_m=.702677,
        ceiling_shift_independently_validated=False,
        limitations=['Pairwise connectivity and clean identity tracks do not certify physical correspondence',
            'Same-input software repeats are not independent captures',
            'Residuals use different point sets and do not establish centimetre accuracy',
            'SIFT uses cached features/pairs: its timing scope differs from learned runs'])
    (out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(runs=results,repeat_checks=repeats,direct_cross_group_pairs=safety['direct_cross_group_pairs']),indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('demo/phase3_xfeat_context'))
    p.add_argument('--context',type=Path,default=Path('demo/phase3_transition_context'))
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();evaluate(a.root,a.context,a.out)
