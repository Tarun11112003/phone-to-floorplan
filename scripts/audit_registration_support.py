"""Read-only audit of saved frame34 registration candidates and associations.

No matching, registration, pose solver, BA, filtering or production changes.
Sensor ray intersections are post-hoc diagnostics using prior observations only;
the held-out target pixel never contributes to their geometry.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import itertools
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.provenance import sha256
from scripts.audit_late_landmarks import (acute_triangulation_angle,directed_matches,
    fundamental,local_triangles,pose_condition,sampson_residuals,shape_diagnostics)
from scripts.audit_registration_stage import gate_saved_replay
from scripts.audit_transition_odometry import (REFERENCE_PAIR,motion,percentiles,
    read_odometry,relative_comparison,verify_retained_summaries)
from scripts.audit_transition_tracks import spatial_support
from scripts.experimental_fixed_intrinsics import check_saved_intrinsics
from scripts.experimental_mapping_only import require_pose_free_database
from scripts.experimental_registration_stage import RETAINED
from scripts.experimental_transition_context import copy_context_database
from scripts.experimental_video_bridge import baseline_digest

SUMMARIES=RETAINED+['docs/results/phase3_registration_stage_summary.json']
TARGET='frame_00034.png'
ANCHOR='frame_00031.png'


def collect_candidates(model,graph,image_id,mapper_options):
    """Enumerate direct registered support; retain competing landmark identities."""
    rows=[]; excluded=Counter()
    image=model.images[image_id]
    for feature,point in enumerate(image.points2D):
        groups={}
        for corr in graph.extract_correspondences(image_id,feature):
            other=model.images[corr.image_id]
            if not other.has_pose:
                excluded['unregistered_origin']+=1; continue
            p=other.points2D[corr.point2D_idx]
            if not p.has_point3D():
                excluded['origin_without_landmark']+=1; continue
            camera=model.cameras[other.camera_id]
            if camera.has_bogus_params(mapper_options['min_focal_length_ratio'],
                mapper_options['max_focal_length_ratio'],mapper_options['max_extra_param']):
                excluded['bogus_origin_camera']+=1; continue
            groups.setdefault(int(p.point3D_id),[]).append(dict(image=other.name,
                image_id=int(corr.image_id),feature_index=int(corr.point2D_idx)))
        if groups:
            rows.append(dict(feature_index=feature,pixel=point.xy.tolist(),
                landmark_alternatives=groups,multiple_landmark_identities=len(groups)>1))
    return rows,dict(excluded)


def accepted_associations(image,candidates):
    possibilities={r['feature_index']:set(r['landmark_alternatives']) for r in candidates}
    accepted={k:int(p.point3D_id) for k,p in enumerate(image.points2D) if p.has_point3D()}
    if any(k not in possibilities or pid not in possibilities[k] for k,pid in accepted.items()):
        raise ValueError('Saved accepted association is absent from native candidate support')
    return accepted


def track_identity_conflicts(observations):
    by_image=defaultdict(list)
    for name,index in observations:
        by_image[name].append(index)
    return {name:indices for name,indices in by_image.items() if len(indices)>1}


def projection(camera,camera_xyz,pixel):
    camera_xyz=np.asarray(camera_xyz,dtype=float)
    depth=float(camera_xyz[2])
    uv=camera.img_from_cam(camera_xyz) if depth>0 else None
    return dict(depth=depth,residual_px=float(np.linalg.norm(uv-pixel)) if uv is not None else None,
        positive_depth=depth>0)


def sensor_ray_point(observations):
    """Intersect prior sensor rays algebraically; no target or pose optimization."""
    centers=[]; rays=[]
    for camera,pixel,sensor in observations:
        ray=np.r_[camera.cam_from_img(pixel),1.]
        ray=sensor['rotation']@(ray/np.linalg.norm(ray))
        centers.append(sensor['center']); rays.append(ray)
    if len(rays)<2:
        return dict(unavailable_reason='Fewer than two prior rays')
    blocks=[np.eye(3)-np.outer(ray,ray) for ray in rays]
    matrix=sum(blocks)
    if np.linalg.matrix_rank(matrix)<3:
        return dict(unavailable_reason='Arithmetically singular ray intersection')
    xyz=np.linalg.solve(matrix,sum(block@center for block,center in zip(blocks,centers)))
    return dict(xyz_m=xyz.tolist(),ray_intersection_condition=float(np.linalg.cond(matrix)),
        prior_observations=len(observations),target_observation_used=False)


def fixed_sensor_motion_projection(local_point,source_sensor,target_sensor,scale):
    rotation=target_sensor['rotation'].T@source_sensor['rotation']
    translation=target_sensor['rotation'].T@(source_sensor['center']-target_sensor['center'])
    return rotation@local_point+translation*scale


def group_metrics(rows,image,camera):
    if not rows: return dict(candidate_rows=0)
    unique={r['feature_index']:r['pixel'] for r in rows}
    return dict(candidate_rows=len(rows),unique_target_features=len(unique),
        unique_source_landmarks=len({r['point3D_id'] for r in rows}),
        multiple_landmark_features=len({r['feature_index'] for r in rows if r['multiple_landmark_identities']}),
        prior_view_counts=dict(Counter(r['prior_views'] for r in rows)),
        prior_frames=dict(Counter(n for r in rows for n in r['prior_images'])),
        native_positive_target_depth=sum(r['native_projection']['positive_depth'] for r in rows),
        native_projection_residual_px=percentiles([r['native_projection']['residual_px'] for r in rows]),
        sensor_epipolar_median_px=percentiles([r['sensor_epipolar_px'].get('median') for r in rows]),
        sensor_prior_epipolar_median_px=percentiles([r['sensor_prior_epipolar_px'].get('median') for r in rows]),
        source_reprojection_max_px=percentiles([r['source_reprojection_px'].get('max') for r in rows]),
        prior_maximum_triangulation_angle_deg=percentiles([r['prior_maximum_triangulation_angle_deg'] for r in rows]),
        sensor_prior_reprojection_max_px=percentiles([r['sensor_prior_reprojection_px'].get('max') for r in rows]),
        sensor_holdout_residual_px=percentiles([r['sensor_holdout_projection'].get('residual_px') for r in rows]),
        sensor_holdout_positive_depth=sum(r['sensor_holdout_projection'].get('positive_depth',False) for r in rows),
        all_prior_sensor_depths_positive=sum(r['all_prior_sensor_depths_positive'] for r in rows),
        inherited_depth_ratio=percentiles([r['inherited_depth_ratio'] for r in rows]),
        sensor_motion_fixed_landmark_residual_px=percentiles([r['sensor_motion_fixed_landmark_projection'].get('residual_px') for r in rows]),
        triangle_conflict_candidates=sum(any(v['conflicting'] for v in r['origin_triangles']) for r in rows),
        source_identity_conflict_landmarks=len({r['point3D_id'] for r in rows if r['source_same_image_features']}),
        spatial=spatial_support(list(unique.values()),(camera.width,camera.height)),
        saved_point_shape=shape_diagnostics([r['source_xyz_model_units'] for r in rows]),
        fixed_landmark_pose_condition=pose_condition([r['native_camera_xyz'] for r in rows],camera.calibration_matrix()))


def run(trial,out):
    import pycolmap
    import sqlite3
    start=time.perf_counter(); trial,out=Path(trial).resolve(),Path(out).resolve()
    if out.exists() or out==trial or trial in out.parents or out in trial.parents:
        raise ValueError('Audit output must be fresh and outside retained inputs')
    if pycolmap.__version__!='4.2.1': raise ValueError('Require pinned PyCOLMAP4.2.1')
    frozen=verify_retained_summaries(SUMMARIES)
    record_path=trial/'experiment.json'; record=json.loads(record_path.read_text(encoding='utf-8'))
    reproduction=gate_saved_replay(record)
    require_pose_free_database(trial/'features.db')
    out.mkdir(parents=True); database=out/'features.db'
    copy_context_database(trial/'features.db',database,list(record['image_sha256']),True,pycolmap)
    require_pose_free_database(database)
    opts=record['options']['mapping']
    cache_options=pycolmap.DatabaseCacheOptions(min_num_matches=opts['min_num_matches'],
        ignore_watermarks=opts['ignore_watermarks'],image_names=set(opts['image_names']),
        load_all_images=opts['load_all_images'],convert_pose_priors_to_enu=opts['use_prior_position'])
    with pycolmap.Database.open(database) as db:
        cache=pycolmap.DatabaseCache.create(db,cache_options)
    before=pycolmap.Reconstruction(record['source_snapshot']['path'])
    before.load(cache)  # native metadata only; never register or optimize
    accepted_path=next(Path(s['path']) for s in record['stages'] if s['stage']=='accepted_registration')
    after=pycolmap.Reconstruction(accepted_path)
    image_id=record['registered_image_id']; image=after.images[image_id]
    if image.name!=TARGET or before.images[image_id].has_pose:
        raise ValueError('Wrong saved native registration interval')
    expected={int(k):v for k,v in record['camera_parameters'].items()}
    check_saved_intrinsics(before,expected); check_saved_intrinsics(after,expected)
    if set(before.points3D)!=set(after.points3D) or any(not np.array_equal(p.xyz,after.points3D[k].xyz)
        for k,p in before.points3D.items()): raise ValueError('Registration changed inherited landmarks')
    for k,i in before.images.items():
        if not np.array_equal(np.array([p.xy for p in i.points2D]),np.array([p.xy for p in cache.images[k].points2D])):
            raise ValueError('Source feature identity differs from frozen native cache')
        if i.has_pose and (not np.array_equal(i.cam_from_world().rotation.quat,after.images[k].cam_from_world().rotation.quat)
            or not np.array_equal(i.cam_from_world().translation,after.images[k].cam_from_world().translation)):
            raise ValueError('Absolute registration moved existing camera poses')
    candidates,excluded=collect_candidates(before,cache.correspondence_graph,image_id,record['effective_mapper_options'])
    observation_manager=pycolmap.ObservationManager(before,cache.correspondence_graph)
    if len(candidates)!=83 or observation_manager.num_visible_points3D(image_id)!=83:
        raise ValueError('Native visible-candidate count does not reproduce83')
    associations=accepted_associations(image,candidates)
    if len(associations)!=37: raise ValueError('Saved accepted observation count differs from37')
    # Sensor files are opened only after all reproduction/identity checks.
    timing_path=Path('demo/phase3_transition_odometry/audit1/audit.json').resolve()
    timing=json.loads(timing_path.read_text()); odometry=Path(next(p for p in timing['input_sha256'] if Path(p).name=='odometry.csv'))
    if sha256(odometry)!=timing['input_sha256'][str(odometry)]: raise ValueError('Post-hoc reference changed')
    sensors=read_odometry(odometry); stamps={v['image']:v for v in timing['alignment']['views']}
    sensor={name:sensors[v['sensor_frame']] for name,v in stamps.items()}
    names={k:i.name for k,i in before.images.items()}; registered={i.name for i in before.images.values() if i.has_pose}
    poses={i.name:dict(center=i.projection_center(),rotation=i.cam_from_world().rotation.matrix().T) for i in after.images.values()}
    lengths=[float(np.linalg.norm(motion(p[REFERENCE_PAIR[0]],p[REFERENCE_PAIR[1]])[1])) for p in (poses,sensor)]
    if min(lengths)<=1e-12: raise ValueError('Singular scale reference')
    scale=lengths[0]/lengths[1]
    camera=after.cameras[image.camera_id]; source_anchor=next(i for i in before.images.values() if i.name==ANCHOR)
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
        verified=directed_matches(db.execute('SELECT pair_id,rows,cols,data FROM two_view_geometries').fetchall(),names)
    maps={pair:{int(a):int(b) for a,b in rows} for pair,rows in verified.items()
        if len(rows)>=opts['min_num_matches'] and set(pair)<=(registered|{TARGET})}
    rows=[]
    for candidate in candidates:
        feature=candidate['feature_index']; pixel=np.array(candidate['pixel'])
        for pid,origins in candidate['landmark_alternatives'].items():
            point=before.points3D[pid]; prior=[]; observed=[]; residuals=[]; identities=[]; inverse_ok=True
            for el in point.track.elements:
                old=before.images[el.image_id]; cam=before.cameras[old.camera_id]; p=old.points2D[el.point2D_idx]
                inverse_ok &= p.has_point3D() and p.point3D_id==pid
                prior.append((old,cam,p.xy))
                identities.append((old.name,int(el.point2D_idx)))
                observed.append((cam,p.xy,sensor[old.name]))
                residuals.append(projection(cam,old.cam_from_world()*point.xyz,p.xy)['residual_px'])
            if not inverse_ok:
                raise ValueError('Source landmark violates its inverse feature association')
            collisions=track_identity_conflicts(identities)
            epipolar=[]; prior_epipolar=[]
            for old,cam,p in prior:
                epipolar.extend(sampson_residuals(fundamental(sensor[old.name],sensor[TARGET],
                    cam.calibration_matrix(),camera.calibration_matrix()),[p],[pixel]))
            for (one,ca,pa),(two,cb,pb) in itertools.combinations(prior,2):
                prior_epipolar.extend(sampson_residuals(fundamental(sensor[one.name],sensor[two.name],
                    ca.calibration_matrix(),cb.calibration_matrix()),[pa],[pb]))
            angles=[acute_triangulation_angle(point.xyz,one.projection_center(),two.projection_center())
                for (one,_,_),(two,_,_) in itertools.combinations(prior,2)]
            angles=[v for v in angles if v is not None]
            independent=sensor_ray_point(observed); sensor_source=[]; source_depths=[]; holdout={}; depth_ratio=None
            if 'xyz_m' in independent:
                xyz=np.array(independent['xyz_m'])
                for old,cam,p in prior:
                    value=projection(cam,sensor[old.name]['rotation'].T@(xyz-sensor[old.name]['center']),p)
                    sensor_source.append(value['residual_px']); source_depths.append(value['positive_depth'])
                holdout=projection(camera,sensor[TARGET]['rotation'].T@(xyz-sensor[TARGET]['center']),pixel)
                sensor_local=sensor[ANCHOR]['rotation'].T@(xyz-sensor[ANCHOR]['center'])
                if sensor_local[2]>0:
                    depth_ratio=float((source_anchor.cam_from_world()*point.xyz)[2]/(sensor_local[2]*scale))
            native_local=np.asarray(image.cam_from_world()*point.xyz)
            sensor_motion_local=fixed_sensor_motion_projection(source_anchor.cam_from_world()*point.xyz,
                sensor[ANCHOR],sensor[TARGET],scale)
            triangles=[local_triangles(origin['image'],TARGET,origin['feature_index'],feature,maps) for origin in origins]
            rows.append(dict(feature_index=feature,point3D_id=pid,pixel=candidate['pixel'],
                accepted=associations.get(feature)==pid,
                acceptance='saved native association, not an inferred internal RANSAC mask',
                multiple_landmark_identities=candidate['multiple_landmark_identities'],direct_origins=origins,
                prior_views=len({i.name for i,_,_ in prior}),prior_observations=len(prior),
                prior_images=sorted({i.name for i,_,_ in prior}),source_same_image_features=collisions,
                support_class='two_prior_views' if len({i.name for i,_,_ in prior})==2 else 'multiple_prior_views',
                source_xyz_model_units=point.xyz.tolist(),native_camera_xyz=native_local.tolist(),
                source_reprojection_px=percentiles(residuals),
                prior_maximum_triangulation_angle_deg=max(angles) if angles else None,
                native_projection=projection(camera,native_local,pixel),
                sensor_epipolar_px=percentiles(epipolar),sensor_prior_epipolar_px=percentiles(prior_epipolar),
                sensor_ray_intersection=independent,sensor_prior_reprojection_px=percentiles(sensor_source),
                all_prior_sensor_depths_positive=bool(source_depths) and all(source_depths),
                sensor_holdout_projection=holdout,inherited_depth_ratio=depth_ratio,
                sensor_motion_fixed_landmark_projection=projection(camera,sensor_motion_local,pixel),
                origin_triangles=triangles))
    accepted_rows=[r for r in rows if r['accepted']]; rejected=[r for r in rows if not r['accepted']]
    if len(rows)!=87 or len(accepted_rows)!=37: raise ValueError('Native support rows differ from controlled probe')
    groups={label:group_metrics(group,image,camera) for label,group in (
        ('accepted',accepted_rows),('not_accepted',rejected),
        ('accepted_unambiguous',[r for r in accepted_rows if not r['multiple_landmark_identities']]),
        ('accepted_multiple_prior_views',[r for r in accepted_rows if r['prior_views']>2]),
        ('accepted_no_triangle_conflict',[r for r in accepted_rows if not any(v['conflicting'] for v in r['origin_triangles'])]))}
    comparisons=[relative_comparison(a,b,poses,sensor,lengths,stamps[b]['sensor_timestamp_s']-stamps[a]['sensor_timestamp_s'])
        for a,b in [('frame_00022.png','frame_00023.png'),('frame_00027.png',ANCHOR),
            ('frame_00028.png',ANCHOR),('frame_00024.png',ANCHOR),(ANCHOR,TARGET)]]
    if baseline_digest(database)!=record['source_database_tables']:
        raise ValueError('Audit changed retained frontend rows')
    require_pose_free_database(database)
    if any(sha256(p)!=digest for p,digest in frozen.items()): raise ValueError('Pinned evidence changed')
    result=dict(experiment='native_frame34_visible_and_accepted_support_audit',candidates=rows,groups=groups,
        visible_features=len(candidates),candidate_rows=len(rows),unique_source_landmarks=len({r['point3D_id'] for r in rows}),
        accepted_observations=len(associations),not_accepted_features=len(candidates)-len(associations),
        multiple_landmark_features=sum(c['multiple_landmark_identities'] for c in candidates),
        source_same_image_identity_collisions=len({r['point3D_id'] for r in rows if r['source_same_image_features']}),
        accepted_source_identity_conflicts=sum(bool(r['source_same_image_features']) for r in accepted_rows),
        accepted_duplicate_landmarks=len(associations)-len(set(associations.values())),
        skipped_origin_edges=excluded,inherited_poses_and_points_exact=True,
        snapshot_reproduction=reproduction,source_motion_comparisons=comparisons,
        alignment=timing['alignment'],reference_pair=REFERENCE_PAIR,
        model_units_per_sensor_meter_from_19_24=scale,
        scale_definition='Fixed19->24 displacement normalization; no fitted similarity or geometry correction',
        sensor_ray_definition='Prior observations only, unweighted algebraic ray intersection; hold out frame34 and all future observations',
        sensor_poses_used_in_inference=False,sensor_poses_used_to_optimize=False,
        reconstruction_solver_called=False,production_changed=False,production_adoption=False,
        physical_accuracy_validated=False,assessment_acceptance=False,pose_acceptance_tolerance=None,
        limitations=['Sensor poses/calibration lack independent covariance or physical survey truth',
            'Algebraic ray intersections are noisy post-hoc references, not corrected reconstruction or measured dimensions',
            'Source tracks and native camera geometry can share systematic biases',
            'Geometric consistency does not prove every feature identity correct'],
        input_sha256={str(p.resolve()):sha256(p) for p in (record_path,timing_path,odometry)},
        script_sha256=sha256(__file__),frozen_hashes_checked=len(frozen),runtime_s=time.perf_counter()-start)
    (out/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['visible_features','candidate_rows','unique_source_landmarks',
        'accepted_observations','not_accepted_features','multiple_landmark_features','groups','runtime_s']},indent=2),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trial',default='demo/phase3_preregistration/trial1')
    p.add_argument('--out',required=True)
    a=p.parse_args(); run(a.trial,a.out)
