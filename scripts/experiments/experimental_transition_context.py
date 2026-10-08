"""Matched 32-view RGB context trial with frozen correspondence/mapping recipes.

Only original image/camera initialization metadata is imported, never saved poses.
SIFT keeps the retained source features/verified pairs, as in the 24-view control.
"""
from __future__ import annotations

import argparse
import json
import itertools
from pathlib import Path
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from floorplan.provenance import sha256
from floorplan.sfm import _matching_diagnostics
from scripts.experiments.experimental_transition_matchers import (
    frozen_options, geometry_report, learned_matches, pair_belongs, sift_candidates, VERSIONS)

CONTEXT = tuple(f'frame_{i:05d}.png' for i in (16,19,22,23,28,31,34,37))


def context_window(retained, source_mapping):
    if len(retained)!=24 or len({r['image'] for r in retained})!=24:
        raise ValueError('Expected the exact 24 retained transition views')
    lookup={r['image']:r for r in source_mapping}
    if not set(CONTEXT).issubset(lookup) or set(CONTEXT)&{r['image'] for r in retained}:
        raise ValueError('Missing or duplicate original RGB context anchors')
    window=[dict(r) for r in retained]+[dict(lookup[n]) for n in CONTEXT]
    return sorted(window,key=lambda r:(r['source_timestamp_s'],r['image']))


def copy_context_database(source, target, names, sift, pycolmap):
    if len(names)!=32 or len(set(names))!=32 or not set(CONTEXT).issubset(names):
        raise ValueError('Expected 32 unique declared RGB views including all eight anchors')
    with pycolmap.Database.open(target): pass
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(target) as dst:
        marks=','.join('?' for _ in names)
        images=src.execute(f'SELECT * FROM images WHERE name IN ({marks}) ORDER BY image_id',names).fetchall()
        if len(images)!=32: raise ValueError('A declared RGB view is absent from the original database')
        ids={r[0] for r in images}; camera_ids={r[2] for r in images}
        frame_data=[r for r in src.execute('SELECT * FROM frame_data') if r[1] in ids and r[3]==0]
        frames=[r for r in src.execute('SELECT * FROM frames') if r[0] in {d[0] for d in frame_data}]
        rig_ids={r[1] for r in frames}
        tables={'images':images,'cameras':[r for r in src.execute('SELECT * FROM cameras') if r[0] in camera_ids],
                'frames':frames,'frame_data':frame_data,
                'rigs':[r for r in src.execute('SELECT * FROM rigs') if r[0] in rig_ids],
                'rig_sensors':[r for r in src.execute('SELECT * FROM rig_sensors') if r[0] in rig_ids]}
        if sift:
            for table in ('keypoints','descriptors'):
                tables[table]=[r for r in src.execute(f'SELECT * FROM {table}') if r[0] in ids]
            for table in ('matches','two_view_geometries'):
                tables[table]=[r for r in src.execute(f'SELECT * FROM {table}') if pair_belongs(r[0],ids)]
        for table,rows in tables.items():
            if rows: dst.executemany(f"INSERT INTO {table} VALUES ({','.join('?' for _ in rows[0])})",rows)
        if dst.execute('SELECT COUNT(*) FROM pose_priors').fetchone()[0]:
            raise ValueError('Pose priors must not enter RGB inference')
    return {r[1]:r[0] for r in images}


def group_model_status(names, groups):
    members=[sorted(set(names)&set(g)) for g in groups]
    return dict(target_group_registered_members=members, both_target_groups_registered=all(members))


def run(trial, retained, mapping, out, mode, site, cache):
    import pycolmap
    trial,retained,mapping,out=map(lambda p:Path(p).resolve(),(trial,retained,mapping,out))
    experiment=json.loads((trial/'experiment.json').read_text())
    control=json.loads((retained/'sift4/experiment.json').read_text())
    if pycolmap.__version__!=VERSIONS['pycolmap']: raise ValueError('PyCOLMAP differs from frozen pin')
    window=context_window(control['temporal_window'],json.loads(mapping.read_text()))
    names=[r['image'] for r in window]
    expected=set(control['image_sha256'])|set(CONTEXT)
    if set(names)!=expected or set(control['image_sha256'])!=set(experiment['added_images'])|set(
            ('frame_00024.png','frame_00025.png','frame_00026.png','frame_00027.png')):
        raise ValueError('Context selection differs from the retained transition')
    inputs={str(p):sha256(p) for p in (trial/'experiment.json',trial/'features.db',mapping,
                                      retained/'sift4/experiment.json',retained/'lightglue_thread4_1/experiment.json',
                                      retained/'comparison/comparison.json')}
    for p,h in control['input_sha256'].items():
        if sha256(p)!=h: raise ValueError('A frozen control input changed')
    for name in names:
        p=trial/'images'/name; h=sha256(p)
        if h!=experiment['image_sha256'][name] or (name in control['image_sha256'] and h!=control['image_sha256'][name]):
            raise ValueError('An original RGB input changed')
        inputs[str(p)]=h
    code={str(p.resolve()):sha256(p) for p in Path('floorplan').glob('*.py')}
    if code!=control['production_code_sha256']: raise ValueError('Production baseline changed')
    dependencies={str(p.resolve()):sha256(p) for p in (
        Path(__file__),Path('scripts/experiments/experimental_transition_matchers.py'),Path('scripts/experiments/experimental_video_bridge.py'))}
    verification,mapper=frozen_options(pycolmap,experiment)
    out.mkdir(parents=True,exist_ok=False);images=out/'images';images.mkdir()
    for name in names: shutil.copy2(trial/'images'/name,images/name)
    started=time.perf_counter();database=out/'features.db'
    ids=copy_context_database(trial/'features.db',database,names,mode=='sift',pycolmap)
    if mode=='lightglue':
        candidates,identity=learned_matches(database,images,names,ids,site,cache)
        pair_file=out/'pairs.txt'
        pair_file.write_text('\n'.join(f'{a} {b}' for a,b in itertools.combinations(names,2))+'\n')
        pycolmap.verify_matches(database,pair_file,options=verification)
    else:
        candidates,identity=sift_candidates(database,names,ids,pycolmap,experiment)
    graph=geometry_report(database,names,candidates)
    groups=experiment['diagnostics']['target_groups']
    from scripts.experiments.experimental_video_bridge import shortest_bridge
    graph['target_group_path']=shortest_bridge(names,
        [(p['image_a'],p['image_b']) for p in graph['pairs'] if p['verified_inliers']],
        set(groups[0])&set(names),set(groups[1])&set(names))
    sparse=out/'sparse';sparse.mkdir()
    models=pycolmap.incremental_mapping(database,images,sparse,options=mapper)
    rows=[]
    for key,model in models.items():
        registered=sorted(i.name for i in model.images.values() if i.has_pose)
        errors=[p.error for p in model.points3D.values() if np.isfinite(p.error) and p.error>=0]
        rows.append(dict(model_id=key,image_names=registered,registered_images=len(registered),
                         sparse_points=model.num_points3D(),mean_reprojection_error_px=model.compute_mean_reprojection_error(),
                         point_mean_error_quantiles_px=np.quantile(errors,[0,.5,.95,1]).tolist() if errors else [],
                         both_endpoints_registered={'frame_00024.png','frame_00027.png'}.issubset(registered),
                         **group_model_status(registered,groups),
                         binary_sha256={p.name:sha256(p) for p in (sparse/str(key)).glob('*.bin')}))
    result=dict(experiment='matched_32_view_RGB_context',mode=mode,input_sha256=inputs,
                image_sha256={n:sha256(images/n) for n in names},temporal_window=window,context_anchors=list(CONTEXT),
                options=experiment['options'],identity=identity,graph=graph,models=rows,target_groups=groups,
                matching_diagnostics=_matching_diagnostics(database,len(names)),
                maximum_registered_images=max((r['registered_images'] for r in rows),default=0),
                total_registered_images=len({n for r in rows for n in r['image_names']}),
                joint_endpoint_model=any(r['both_endpoints_registered'] for r in rows),
                joint_target_group_model=any(r['both_target_groups_registered'] for r in rows),
                runtime_s=time.perf_counter()-started,script_sha256=sha256(__file__),dependency_sha256=dependencies,
                production_code_sha256=code,accuracy_validated=False,metric_scale=False,production_policy_changed=False,
                limitations=['Same-input software repeats are not independent physical captures',
                             'SIFT uses frozen source features/pairs; candidates are separately replayed',
                             'A connected pair graph does not establish correct joint geometry',
                             'No saved optimized poses, depth, odometry, IMU or survey scale enters inference',
                             'Shared learned-matcher progress denominator is historically 276; this run actually evaluates all 496 pairs'])
    if any(sha256(p)!=h for p,h in {**inputs,**code,**dependencies}.items()):
        raise ValueError('Frozen inputs, producer code or experiment recipe changed during execution')
    (out/'experiment.json').write_text(json.dumps(result,indent=2,default=str)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('mode','maximum_registered_images','total_registered_images',
        'joint_endpoint_model','joint_target_group_model','models','runtime_s')},indent=2),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trial',type=Path,default=Path('demo/phase3_video_bridge/dense_trial1'))
    p.add_argument('--retained',type=Path,default=Path('demo/phase3_transition_matchers'))
    p.add_argument('--mapping',type=Path,default=Path('demo/phase3_sync_boundary/video_sampling_verified_input/video72/result/sfm/video_frame_mapping.json'))
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--mode',choices=('sift','lightglue'),required=True)
    p.add_argument('--site',type=Path,default=Path('.tools/lightglue_experiment/site'))
    p.add_argument('--cache',type=Path,default=Path('.tools/lightglue_cache'))
    a=p.parse_args();run(a.trial,a.retained,a.mapping,a.out,a.mode,a.site,a.cache)
