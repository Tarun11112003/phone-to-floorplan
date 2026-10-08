"""Audit native initialization suitability on a frozen-copy matcher database.

No reconstruction is registered or exported. Relative-pose angles are conditional
on RGB camera initialization priors, never independent physical measurements.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.provenance import sha256
from scripts.experimental_transition_matchers import frozen_options


def audit(trial, out):
    import pycolmap
    trial,out=Path(trial).resolve(),Path(out).resolve()
    record=json.loads((trial/'experiment.json').read_text())
    source=trial/'features.db';before=sha256(source)
    _,pipeline=frozen_options(pycolmap,record)
    out.mkdir(parents=True,exist_ok=False);copied=out/'diagnostic_copy.db'
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(copied) as dst:
        src.backup(dst)
    rows=[]
    with pycolmap.Database.open(copied) as db:
        images={i.image_id:i for i in db.read_all_images()}
        cache=pycolmap.DatabaseCache.create(db,pycolmap.DatabaseCacheOptions(
            min_num_matches=pipeline.min_num_matches,ignore_watermarks=pipeline.ignore_watermarks))
        mapper=pycolmap.IncrementalMapper(cache);model=pycolmap.Reconstruction()
        mapper.begin_reconstruction(model)
        with sqlite3.connect(copied.as_uri()+'?mode=ro',uri=True) as conn:
            verified=conn.execute('SELECT pair_id,rows FROM two_view_geometries WHERE rows>0 ORDER BY pair_id').fetchall()
        for pid,n in verified:
            a,b=pid//2147483647,pid%2147483647
            strict=mapper.estimate_initial_two_view_geometry(pipeline.mapper,a,b)
            geometry=db.read_two_view_geometry(a,b)
            points=[]
            for i in (a,b): points.append(db.read_keypoints(i)[:,:2].astype(float))
            camera1,camera2=(db.read_camera(images[i].camera_id) for i in (a,b))
            pose_ok=pycolmap.estimate_two_view_geometry_pose(camera1,points[0],camera2,points[1],geometry)
            angle=float(np.degrees(geometry.tri_angle)) if pose_ok else None
            if angle is not None and not np.isfinite(angle): angle=None
            rows.append(dict(image_a=images[a].name,image_b=images[b].name,
                             stored_verified_inliers=n,strict_native_initialization_pass=strict is not None,
                             prior_conditional_pose_estimated=pose_ok,
                             prior_conditional_triangulation_angle_deg=angle,
                             reaches_initial_inlier_count=n>=pipeline.mapper.init_min_num_inliers,
                             reaches_initial_angle=angle is not None and angle>=pipeline.mapper.init_min_tri_angle))
        mapper.end_reconstruction(discard=True)
    if sha256(source)!=before: raise ValueError('Frozen matcher database changed')
    angles=[r['prior_conditional_triangulation_angle_deg'] for r in rows if r['prior_conditional_triangulation_angle_deg'] is not None]
    result=dict(experiment='strict_native_initialization_audit',mode=record['mode'],input_database_sha256=before,
                input_experiment_sha256=sha256(trial/'experiment.json'),script_sha256=sha256(Path(__file__)),
                verified_pairs=len(rows),strict_initialization_passes=sum(r['strict_native_initialization_pass'] for r in rows),
                pairs_at_initial_inlier_count=sum(r['reaches_initial_inlier_count'] for r in rows),
                pose_estimated_pairs=len(angles),prior_conditional_angle_min_median_max_deg=
                    [float(np.min(angles)),float(np.median(angles)),float(np.max(angles))] if angles else None,
                pairs_at_initial_angle=sum(r['reaches_initial_angle'] for r in rows),pairs=rows,
                initial_inlier_minimum=pipeline.mapper.init_min_num_inliers,
                initial_angle_minimum_deg=pipeline.mapper.init_min_tri_angle,
                mapper_options=json.loads(json.dumps(pipeline.mapper.todict(),default=str)),
                no_registration_or_model_export=True,frozen_database_unchanged=True,physical_accuracy_validated=False,
                limitations=['Native suitability rejection is not a unique diagnosis of physical motion or calibration',
                             'Relative pose/angle diagnostics use uncertain RGB initialization intrinsics',
                             'Stored F inliers and native essential-pose inliers can differ',
                             'COLMAP pipeline internal fallback can relax its own initialization recipe; no application setting is changed'])
    (out/'audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('pairs','mapper_options')},indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('trial',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();audit(a.trial,a.out)
