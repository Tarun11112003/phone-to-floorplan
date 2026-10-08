"""Compare repeated 32-view context models to the frozen 24-view evidence."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.provenance import sha256
from scripts.audit_transition_tracks import audit_trial, draw_pair, track_components
from scripts.compare_transition_matchers import compare
from scripts.experimental_video_bridge import baseline_digest


def group_track_status(tracks, groups):
    spanning=[nodes for nodes in tracks if all(set(g)&{n[0] for n in nodes} for g in groups)]
    return dict(group_spanning_tracks=len(spanning), clean_group_spanning_tracks=sum(
        len({n[0] for n in nodes})==len(nodes) for nodes in spanning))


def immutable_trial_files(folders):
    """SQLite SHM read marks are mutable bookkeeping; DB and WAL are actual data."""
    return {str(p):sha256(p) for folder in folders for p in folder.rglob('*')
            if p.is_file() and not p.name.endswith('.db-shm')}


def retained_subset_check(current, old):
    """Compare all original rows against the enlarged database, including zeros."""
    new,previous=baseline_digest(current/'features.db'),baseline_digest(old/'features.db')
    return {table:dict(original_rows=len(rows),changed_or_missing=sum(new[table].get(k)!=v for k,v in rows.items()))
            for table,rows in previous.items()}


def model_safety(trial, record):
    import pycolmap
    rows=[]
    for saved in record['models']:
        model=pycolmap.Reconstruction(trial/'sparse'/str(saved['model_id']))
        counts=Counter();errors=[];depths=[];group_tracks=0;duplicate_tracks=0
        duplicate_spreads=[]
        for point in model.points3D.values():
            images=[model.images[e.image_id] for e in point.track.elements]
            duplicate_tracks+=len({i.image_id for i in images})!=len(images)
            by_image={}
            for e,image in zip(point.track.elements,images):
                by_image.setdefault(image.name,[]).append(image.points2D[e.point2D_idx].xy)
            duplicate_spreads.extend(float(np.ptp(pixels,axis=0).max()) for pixels in by_image.values() if len(pixels)>1)
            group_tracks+=all(set(g)&{i.name for i in images} for g in record['target_groups'])
            for e,image in zip(point.track.elements,images):
                camera=model.cameras[image.camera_id]
                xyz=image.cam_from_world()*point.xyz
                depths.append(float(xyz[2]))
                pixel=camera.img_from_cam(xyz)
                if pixel is not None:
                    errors.append(float(np.linalg.norm(pixel-image.points2D[e.point2D_idx].xy)))
                counts[image.name]+=1
        rows.append(dict(model_id=saved['model_id'],registered_views=saved['registered_images'],
                         point_tracks_spanning_original_groups=group_tracks,duplicate_image_point_tracks=duplicate_tracks,
                         same_image_duplicate_separation_lower_bound_max_px=max(duplicate_spreads,default=0.),
                         observations=len(depths),nonpositive_depth_observations=sum(d<=0 for d in depths),
                         reprojection_observations=len(errors),
                         observation_reprojection_quantiles_px=np.quantile(errors,[0,.5,.95,1]).tolist() if errors else [],
                         registered_image_observations=dict(counts)))
    return rows


def model_overlap_safety(trial, record):
    """Report identical-feature overlap and relative depth; never align models."""
    import pycolmap
    rows=[]
    loaded=[(saved,pycolmap.Reconstruction(trial/'sparse'/str(saved['model_id']))) for saved in record['models']]
    for i,(saved_a,model_a) in enumerate(loaded):
        for saved_b,model_b in loaded[i+1:]:
            names=sorted(set(saved_a['image_names'])&set(saved_b['image_names']))
            links=[]
            for name in names:
                images=[next(v for v in model.images.values() if v.has_pose and v.name==name) for model in (model_a,model_b)]
                observations=[]
                for model,image in zip((model_a,model_b),images):
                    observations.append({idx:model.points3D[p.point3D_id] for idx,p in enumerate(image.points2D) if p.has_point3D()})
                shared=sorted(set(observations[0])&set(observations[1]))
                ratios=[];original_group_support=0
                for index in shared:
                    points=[p[index] for p in observations]
                    z=[float((image.cam_from_world()*point.xyz)[2]) for image,point in zip(images,points)]
                    if all(np.isfinite(z)) and min(z)>0: ratios.append(z[1]/z[0])
                    memberships=[{model.images[e.image_id].name for e in point.track.elements}
                                 for model,point in zip((model_a,model_b),points)]
                    groups=list(map(set,record['target_groups']))
                    original_group_support+=bool((memberships[0]&groups[0] and memberships[1]&groups[1])
                                                  or (memberships[0]&groups[1] and memberships[1]&groups[0]))
                links.append(dict(image=name,common_reconstructed_keypoint_indices=len(shared),
                    common_indices_with_opposite_original_group_3D_support=original_group_support,
                    positive_depth_ratio_quantiles=np.quantile(ratios,[0,.5,.95,1]).tolist() if ratios else [],
                    valid_positive_depth_ratios=len(ratios)))
            rows.append(dict(model_ids=[saved_a['model_id'],saved_b['model_id']],shared_registered_images=names,
                             overlap=links,alignment_or_merge_attempted=False))
    return rows


def evaluate(root, retained, out):
    root,retained,out=map(lambda p:p.resolve(),(root,retained,out))
    folders=[root/n for n in ('sift1','sift2','lightglue1','lightglue2')]
    records=[json.loads((p/'experiment.json').read_text()) for p in folders]
    for record in records:
        if record['experiment']!='matched_32_view_RGB_context' or len(record['image_sha256'])!=32:
            raise ValueError('Expected completed 32-view context results')
        if record['dependency_sha256']!=records[0]['dependency_sha256']:
            raise ValueError('Experiment helper code differs across trials')
        if any(sha256(p)!=h for p,h in record['dependency_sha256'].items()):
            raise ValueError('Experiment helper changed since execution')
    frozen=immutable_trial_files(folders)
    out.mkdir(parents=True,exist_ok=False)
    comparison=compare(*folders,out/'repeats')
    comparison['experiment']='matched_32_view_RGB_context_comparison'
    (out/'repeats/comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
    diagnostics=[]
    for trial,record,old in zip((folders[0],folders[2]),(records[0],records[2]),
                               (retained/'sift4',retained/'lightglue_thread4_1')):
        output=out/record['mode'];output.mkdir()
        safety=audit_trial(trial,output)
        with sqlite3.connect((trial/'features.db').as_uri()+'?mode=ro',uri=True) as db:
            ids=dict(db.execute('SELECT image_id,name FROM images'))
            coords={ids[i]:np.frombuffer(blob,np.float32).reshape(n,c)[:,:2] for i,n,c,blob in db.execute('SELECT * FROM keypoints')}
            edges=[(ids[p//2147483647],ids[p%2147483647],np.frombuffer(data,np.uint32).reshape(n,2))
                for p,n,data in db.execute('SELECT pair_id,rows,data FROM two_view_geometries WHERE rows>0 ORDER BY pair_id')]
        safety['group_tracks']=group_track_status(track_components(edges),record['target_groups'])
        safety['native_model_safety']=model_safety(trial,record)
        safety['model_overlap_safety']=model_overlap_safety(trial,record)
        safety['retained_24_row_comparison']=retained_subset_check(trial,old)
        safety['target_group_path']=record['graph']['target_group_path']
        safety['target_group_path_pairs']=[]
        for a,b in zip(safety['target_group_path'][:-1],safety['target_group_path'][1:]):
            x,y,m=next(e for e in edges if {e[0],e[1]}=={a,b})
            image=output/f'group_{a}_{b}.jpg'
            draw_pair(trial,x,y,coords[x][m[:,0]],coords[y][m[:,1]],image)
            pair=next(p for p in record['graph']['pairs'] if {p['image_a'],p['image_b']}=={a,b})
            safety['target_group_path_pairs'].append(dict(**pair,visualization=image.name))
        safety['joint_target_group_model']=record['joint_target_group_model']
        (output/'safety.json').write_text(json.dumps(safety,indent=2)+'\n',encoding='utf-8')
        diagnostics.append(safety)
    if any(sha256(p)!=h for p,h in frozen.items()): raise ValueError('Comparison changed retained trial artifacts')
    baseline=json.loads((retained/'comparison/comparison.json').read_text())
    result=dict(experiment='matched_32_view_context_evaluation',comparison=comparison,
                diagnostics=diagnostics,retained_24_baseline=baseline,
                baseline_comparison_sha256=sha256(retained/'comparison/comparison.json'),
                source_trial_sha256=frozen,script_sha256=sha256(__file__),production_policy_changed=False,
                sqlite_shared_memory_excluded=True,sqlite_database_and_wal_hashed=True,
                metric_accuracy_validated=False,production_adoption_demonstrated=False,
                limitations=['SIFT frozen feature/pair control and learned fresh-inference timings have different scopes',
                             'Extra local registration is not joint target-group reconstruction',
                             'Transitive conflicts do not uniquely identify each incorrect edge',
                             'Same-input repeats do not establish independent capture repeatability'])
    (out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([dict(mode=r['mode'],tracks=r['tracks'],group_tracks=r['group_tracks'],
                           native_model_safety=r['native_model_safety'],joint_target_group_model=r['joint_target_group_model'],
                           retained_24_row_comparison=r['retained_24_row_comparison']) for r in diagnostics],indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('demo/phase3_transition_context'))
    p.add_argument('--retained',type=Path,default=Path('demo/phase3_transition_matchers'))
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();evaluate(a.root,a.retained,a.out)
