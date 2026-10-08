"""Read-only saved-landmark audit; no matching, verification or mapping calls.

Saved final tracks are not the unrecorded PnP registration-inlier set. Raw graph
conflicts are distinguished from collisions in actually saved native tracks.
Sensor poses are reused only from the completed post-hoc audit for diagnostics.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import itertools
import json
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.provenance import sha256
from scripts.audit_transition_odometry import percentiles, verify_retained_summaries
from scripts.audit_transition_tracks import spatial_support, track_components, track_spread
from scripts.compare_transition_context import immutable_trial_files
from scripts.experimental_fixed_intrinsics import check_saved_intrinsics
from scripts.experimental_mapping_only import RETAINED_SUMMARIES

SUMMARIES = RETAINED_SUMMARIES + ['docs/results/phase3_mapping_only_summary.json']
TARGET = ('frame_00031.png', 'frame_00034.png')
PAIRS = (('frame_00019.png','frame_00022.png'), ('frame_00022.png','frame_00023.png'),
         ('frame_00019.png','frame_00024.png'), ('frame_00028.png','frame_00031.png'),
         TARGET, ('frame_00034.png','frame_00037.png'))
MAX_ID = 2147483647


def acute_triangulation_angle(xyz, center_a, center_b):
    rays = [np.asarray(xyz)-np.asarray(c) for c in (center_a,center_b)]
    if min(np.linalg.norm(v) for v in rays) == 0:
        return None
    angle = float(np.degrees(np.arctan2(np.linalg.norm(np.cross(*rays)), rays[0]@rays[1])))
    return min(angle,180.-angle)


def skew(v):
    x,y,z = v
    return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])


def fundamental(pose_a, pose_b, intrinsic_a, intrinsic_b):
    # Rotations are camera-to-world; this is x_b.T F x_a = 0.
    rotation = np.asarray(pose_b['rotation']).T @ np.asarray(pose_a['rotation'])
    translation = np.asarray(pose_b['rotation']).T @ (np.asarray(pose_a['center'])-np.asarray(pose_b['center']))
    return np.linalg.inv(intrinsic_b).T @ skew(translation) @ rotation @ np.linalg.inv(intrinsic_a)


def sampson_residuals(matrix, pixels_a, pixels_b):
    x = np.column_stack([np.asarray(pixels_a),np.ones(len(pixels_a))])
    y = np.column_stack([np.asarray(pixels_b),np.ones(len(pixels_b))])
    fx, fty = x@matrix.T, y@matrix
    denominator = np.sqrt(np.sum(fx[:,:2]**2+fty[:,:2]**2,axis=1))
    return [float(abs(v)/d) if d > 0 and np.isfinite(d) else None
            for v,d in zip(np.sum(y*fx,axis=1),denominator)]


def shape_diagnostics(points):
    points = np.asarray(points,dtype=float)
    if len(points) < 3:
        return dict(count=len(points),unavailable_reason='Fewer than three points')
    centered = points-points.mean(axis=0)
    _,singular,vectors = np.linalg.svd(centered,full_matrices=False)
    distances = abs(centered@vectors[-1])
    return dict(count=len(points),singular_values_model_units=singular.tolist(),
        smallest_over_middle=float(singular[-1]/singular[-2]) if singular[-2] > 0 else None,
        smallest_over_largest=float(singular[-1]/singular[0]) if singular[0] > 0 else None,
        plane_abs_distance_model_units=percentiles(distances),
        interpretation='Shape diagnostic of saved points; not independent truth or a pass threshold')


def pose_condition(camera_points, intrinsic):
    """Fixed-landmark projection Jacobian; excludes BA landmark uncertainty."""
    camera_points = np.asarray(camera_points,dtype=float)
    if not len(camera_points) or np.any(camera_points[:,2] <= 0):
        return dict(unavailable_reason='No points or nonpositive depths')
    depth_scale = float(np.median(camera_points[:,2]))
    blocks = []
    for point in camera_points:
        x,y,z = point
        projection = np.array([[intrinsic[0,0]/z,0.,-intrinsic[0,0]*x/z**2],
                               [0.,intrinsic[1,1]/z,-intrinsic[1,1]*y/z**2]])
        blocks.append(np.column_stack([projection@(-skew(point)),projection*depth_scale]))
    jacobian = np.vstack(blocks)
    singular = np.linalg.svd(jacobian,compute_uv=False)
    return dict(observations=len(camera_points),singular_values_px=singular.tolist(),
        condition_number=float(singular[0]/singular[-1]) if singular[-1] > 0 else None,
        translation_normalization_median_depth_model_units=depth_scale,
        interpretation='Local fixed-landmark pose block; not joint-BA conditioning, uncertainty or acceptance')


def native_status(image_a, index_a, image_b, index_b):
    a,b = image_a.points2D[index_a],image_b.points2D[index_b]
    if a.has_point3D() and b.has_point3D():
        return 'shared_saved_point' if a.point3D_id == b.point3D_id else 'different_saved_points'
    if a.has_point3D(): return 'only_a_saved'
    if b.has_point3D(): return 'only_b_saved'
    return 'neither_saved'


def directed_matches(rows, names):
    pairs = {}
    for pid, count, columns, blob in rows:
        a,b = names[pid//MAX_ID],names[pid%MAX_ID]
        indices = np.frombuffer(blob,np.uint32).reshape(count,columns) if count else np.empty((0,2),np.uint32)
        pairs[a,b] = indices
        pairs[b,a] = indices[:,::-1]
    return pairs


def local_triangles(a, b, index_a, index_b, verified):
    agrees,conflicts = [],[]
    for middle in sorted({x for edge in verified for x in edge}-{a,b}):
        first,last = verified.get((a,middle)),verified.get((middle,b))
        if first is None or last is None: continue
        k = first.get(index_a)
        if k is None or k not in last: continue
        target = last[k]
        row = dict(via=middle,feature_via=k,feature_b_composed=target)
        (agrees if target == index_b else conflicts).append(row)
    return dict(agreeing=agrees,conflicting=conflicts)


def run(trial, out):
    import pycolmap
    started = time.perf_counter(); trial,out = [Path(p).resolve() for p in (trial,out)]
    if out.exists() or out == trial or trial in out.parents or out in trial.parents:
        raise ValueError('Audit output must be a new directory outside the retained trial')
    frozen = verify_retained_summaries(SUMMARIES)
    inputs = immutable_trial_files([trial])
    record = json.loads((trial/'experiment.json').read_text(encoding='utf-8'))
    if record['mode'] != 'xfeat_mapping_only_fixed' or len(record['models']) != 1:
        raise ValueError('Expected retained single-model mapping-only XFeat ablation')
    model = pycolmap.Reconstruction(trial/'sparse'/str(record['models'][0]['model_id']))
    images = {i.name:i for i in model.images.values() if i.has_pose}
    intrinsics = check_saved_intrinsics(model,{int(k):v for k,v in record['camera_parameters'].items()})
    # Reuse already-audited sensor identities/poses; do not feed them to inference.
    pose_audit_path = Path('demo/phase3_mapping_only/evaluation/evaluation.json')
    old = json.loads(pose_audit_path.read_text(encoding='utf-8'))['trials'][0][0]
    timeline = {v['image']:v for v in old['registered_timeline']}
    sensor = {n:dict(center=v['sensor_center_m'],rotation=v['sensor_camera_to_world_rotation']) for n,v in timeline.items()}
    candidate = {n:dict(center=i.projection_center(),rotation=i.cam_from_world().rotation.matrix().T) for n,i in images.items()}
    camera = {n:model.cameras[i.camera_id] for n,i in images.items()}
    coords = {}
    with sqlite3.connect((trial/'features.db').as_uri()+'?mode=ro',uri=True) as db:
        names = dict(db.execute('SELECT image_id,name FROM images'))
        for image_id,count,columns,blob in db.execute('SELECT * FROM keypoints'):
            coords[names[image_id]] = np.frombuffer(blob,np.float32).reshape(count,columns)[:,:2]
        raw = directed_matches(db.execute('SELECT pair_id,rows,cols,data FROM matches').fetchall(),names)
        verified = directed_matches(db.execute('SELECT pair_id,rows,cols,data FROM two_view_geometries').fetchall(),names)
        matrices = {}
        for pid,blob in db.execute('SELECT pair_id,F FROM two_view_geometries WHERE rows>0'):
            a,b=names[pid//MAX_ID],names[pid%MAX_ID]
            matrix = np.frombuffer(blob,np.float64).reshape(3,3)
            matrices[a,b]=matrix;matrices[b,a]=matrix.T
    for name,image in images.items():
        if not np.array_equal(np.array([p.xy for p in image.points2D]),coords[name]):
            raise ValueError('Saved model feature coordinates differ from retained keypoints')
    edges = [(a,b,v) for (a,b),v in verified.items() if a < b and len(v)]
    components = track_components(edges)
    component_rows = []; node_component = {}
    for idx,nodes in enumerate(components):
        counts = Counter(n for n,_ in nodes)
        row = dict(component_id=idx,views=len(counts),observations=len(nodes),
            conflicting=any(n > 1 for n in counts.values()),
            same_image_separation_lower_bound_px=track_spread(nodes,coords))
        component_rows.append(row)
        node_component.update({node:idx for node in nodes})
    maps = {(a,b):{int(x):int(y) for x,y in v} for (a,b),v in verified.items() if len(v)}
    if any(len(set(v.values())) != len(v) or len(v) != len(verified[k]) for k,v in maps.items()):
        raise ValueError('Expected unchanged one-to-one verified feature rows')
    native_features = {}
    for name,image in images.items():
        by_point = defaultdict(list)
        for index,p in enumerate(image.points2D):
            if p.has_point3D(): by_point[int(p.point3D_id)].append(index)
        native_features[name] = by_point
    point_sets = {n:set(indices) for n,indices in native_features.items()}
    selected = set.union(*(point_sets[a]&point_sets[b] for a,b in PAIRS),
                         point_sets[TARGET[0]],point_sets[TARGET[1]])
    landmarks = {}
    for pid in sorted(selected):
        point = model.points3D[pid]; observations = []; by_image = defaultdict(list)
        for element in point.track.elements:
            image = model.images[element.image_id]; index = int(element.point2D_idx)
            p2d = image.points2D[index]
            if not p2d.has_point3D() or p2d.point3D_id != pid:
                raise ValueError('Saved native track violates image/point inverse association')
            local = np.asarray(image.cam_from_world()*point.xyz)
            projected = camera[image.name].img_from_cam(local)
            component_id = node_component.get((image.name,index))
            observations.append(dict(image=image.name,image_id=image.image_id,feature_index=index,
                pixel=p2d.xy.tolist(),depth_model_units=float(local[2]),
                reprojection_px=float(np.linalg.norm(projected-p2d.xy)) if projected is not None else None,
                raw_component_id=component_id))
            by_image[image.name].append(index)
        collisions = {n:dict(feature_indices=indices,
            same_image_separation_lower_bound_px=float(np.ptp(coords[n][indices],axis=0).max()))
            for n,indices in by_image.items() if len(indices)>1}
        angles = [acute_triangulation_angle(point.xyz, candidate[a]['center'],candidate[b]['center'])
                  for a,b in itertools.combinations(by_image,2)]
        valid_angles = [v for v in angles if v is not None]
        component_ids = sorted({v['raw_component_id'] for v in observations if v['raw_component_id'] is not None})
        landmarks[str(pid)] = dict(point3D_id=pid,xyz_model_units=point.xyz.tolist(),
            native_track_observations=len(observations),unique_views=len(by_image),observations=observations,
            native_same_image_collisions=collisions,raw_components=[component_rows[i] for i in component_ids],
            maximum_acute_triangulation_angle_deg=max(valid_angles) if valid_angles else None,
            point_mean_reprojection_px=float(point.error))
    pairs = []
    motion = {(v['image_a'],v['image_b']):v for v in old['adjacent']+old['selected_pairs']+old['transition_anchor_comparisons']}
    for a,b in PAIRS:
        ia,ib=images[a],images[b]; shared = sorted(point_sets[a]&point_sets[b])
        raw_pairs = {tuple(map(int,v)) for v in raw[a,b]}
        verified_pairs = {tuple(map(int,v)) for v in verified[a,b]}
        native_pairs = {(x,y) for pid in shared
                        for x,y in itertools.product(native_features[a][pid],native_features[b][pid])}
        tuples = sorted(raw_pairs|verified_pairs|native_pairs)
        pixel_a,pixel_b = [coords[n][[v[k] for v in tuples]] for k,n in enumerate((a,b))]
        K,L = [camera[n].calibration_matrix() for n in (a,b)]
        diagnostic = {label:sampson_residuals(F,pixel_a,pixel_b) for label,F in (
            ('stored_F',matrices[a,b]),('saved_pose',fundamental(candidate[a],candidate[b],K,L)),
            ('sensor_pose',fundamental(sensor[a],sensor[b],K,L)))}
        rows = []
        for index,(x,y) in enumerate(tuples):
            status = native_status(ia,x,ib,y)
            components_touched = sorted({node_component[node] for node in ((a,x),(b,y)) if node in node_component})
            pid = int(ia.points2D[x].point3D_id) if status == 'shared_saved_point' else None
            row = dict(feature_a=x,feature_b=y,pixel_a=pixel_a[index].tolist(),pixel_b=pixel_b[index].tolist(),
                retained_raw_candidate=(x,y) in raw_pairs,verified_inlier=(x,y) in verified_pairs,
                final_native_status=status,shared_point3D_id=pid,
                raw_components=[component_rows[i] for i in components_touched],
                sampson_px={k:v[index] for k,v in diagnostic.items()},
                verified_triangle_support=local_triangles(a,b,x,y,maps) if (x,y) in verified_pairs else None)
            rows.append(row)
        pair_points = np.array([model.points3D[p].xyz for p in shared])
        local_points = {n:np.array([images[n].cam_from_world()*p for p in pair_points]) for n in (a,b)}
        pair_angle = [acute_triangulation_angle(model.points3D[p].xyz,candidate[a]['center'],candidate[b]['center']) for p in shared]
        exact_shared = [v for v in rows if v['final_native_status']=='shared_saved_point']
        saved_observations = [o for p in shared for o in landmarks[str(p)]['observations'] if o['image'] in (a,b)]
        subsets = {}
        for label,subset in (('verified',[v for v in rows if v['verified_inlier']]),
            ('verified_shared',[v for v in rows if v['verified_inlier'] and v['final_native_status']=='shared_saved_point']),
            ('verified_not_shared',[v for v in rows if v['verified_inlier'] and v['final_native_status']!='shared_saved_point']),
            ('unverified_raw',[v for v in rows if v['retained_raw_candidate'] and not v['verified_inlier']])):
            subsets[label] = dict(count=len(subset),native_status_counts=dict(Counter(v['final_native_status'] for v in subset)),
                in_conflicting_raw_components=sum(any(c['conflicting'] for c in v['raw_components']) for v in subset),
                with_local_triangle_conflicts=sum(bool(v['verified_triangle_support'] and v['verified_triangle_support']['conflicting']) for v in subset),
                triangle_agreements=sum(len(v['verified_triangle_support']['agreeing']) for v in subset if v['verified_triangle_support']),
                triangle_conflicts=sum(len(v['verified_triangle_support']['conflicting']) for v in subset if v['verified_triangle_support']),
                sampson_px={k:percentiles([v['sampson_px'][k] for v in subset]) for k in diagnostic})
        by_name = {n:[[o['pixel'][0],o['pixel'][1]] for o in saved_observations if o['image']==n] for n in (a,b)}
        pair_motion = motion.get((a,b))
        pairs.append(dict(images=[a,b],shared_landmark_ids=shared,
            direct_verified_shared_landmark_ids=sorted({v['shared_point3D_id'] for v in exact_shared if v['verified_inlier']}),
            raw_candidates=len(raw_pairs),verified_inliers=len(verified_pairs),shared_landmarks=len(shared),
            observations_in_images=[ia.num_points3D,ib.num_points3D],subsets=subsets,
            shared_native_collision_landmarks=sum(bool(landmarks[str(p)]['native_same_image_collisions']) for p in shared),
            shared_unique_view_histogram=dict(Counter(landmarks[str(p)]['unique_views'] for p in shared)),
            shared_unique_views=percentiles([landmarks[str(p)]['unique_views'] for p in shared]),
            shared_reprojection_px=percentiles([o['reprojection_px'] for o in saved_observations]),
            shared_depth_model_units={n:percentiles(local_points[n][:,2]) for n in (a,b)},
            shared_nonpositive_depths=sum(o['depth_model_units']<=0 for o in saved_observations),
            shared_pair_acute_angle_deg=percentiles(pair_angle),
            shared_maximum_track_angle_deg=percentiles([landmarks[str(p)]['maximum_acute_triangulation_angle_deg'] for p in shared]),
            shared_shape=shape_diagnostics(pair_points),
            spatial_support={n:spatial_support(by_name[n],(camera[n].width,camera[n].height)) for n in (a,b)},
            fixed_landmark_pose_condition={n:pose_condition(local_points[n],camera[n].calibration_matrix()) for n in (a,b)},
            sensor_motion_comparison={k:pair_motion[k] for k in ('relative_rotation_error_deg','translation_direction_error_deg','relative_length_ratio')} if pair_motion else None,
            indexed_correspondences=rows))
    log = Path('demo/mapping_only_trial1_native.log').read_text(encoding='utf-8')
    lines=log.splitlines(); registrations=[]; last_registered=None; warnings=[]
    for line_number,line in enumerate(lines,1):
        if 'Registering image #' in line:
            last_registered=int(line.split('Registering image #')[1].split()[0])
            registrations.append(dict(log_line=line_number,image_id=last_registered,image=names[last_registered],
                saved_final_track_is_registration_inlier_set=False,
                native_reported_support=lines[line_number] if line_number<len(lines) else None))
        if 'Linear solver failure.' in line:
            warnings.append(dict(log_line=line_number,most_recent_registration_image=names.get(last_registered)))
    if any(sha256(p)!=h for p,h in {**frozen,**inputs}.items()):
        raise ValueError('Read-only audit mutated retained evidence or source')
    out.mkdir(parents=True)
    payload = dict(experiment='saved_31_34_landmark_identity_geometry_audit',pairs=pairs,landmarks=landmarks,
        target_all_observed_landmark_ids=sorted(point_sets[TARGET[0]]|point_sets[TARGET[1]]),
        registration_log=registrations,solver_warning_context=warnings,fixed_intrinsics=intrinsics,
        registered_views=model.num_reg_images(),sparse_points=model.num_points3D(),
        mean_reprojection_error_px=model.compute_mean_reprojection_error(),
        sensor_poses_used_only_posthoc=True,reconstruction_rerun=False,matching_rerun=False,
        verification_rerun=False,filtering_changed=False,production_changed=False,
        physical_accuracy_validated=False,assessment_acceptance=False)
    (out/'landmarks.json').write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    summary = dict(experiment=payload['experiment'],pairs=[{k:v for k,v in p.items() if k!='indexed_correspondences'} for p in pairs],
        target_all_observed_landmark_ids=payload['target_all_observed_landmark_ids'],
        selected_landmarks=len(landmarks),fixed_intrinsics=intrinsics,registration_log=registrations,
        solver_warning_context=dict(total=len(warnings),by_last_registration=dict(Counter(v['most_recent_registration_image'] for v in warnings))),
        input_sha256=inputs,posthoc_audit_sha256=sha256(pose_audit_path),script_sha256=sha256(__file__),
        retained_prior_hash_entries_checked=len(frozen),retained_artifacts_unchanged=True,
        landmarks_sha256=sha256(out/'landmarks.json'),runtime_s=time.perf_counter()-started,
        reconstruction_rerun=False,production_changed=False,physical_accuracy_validated=False,assessment_acceptance=False,
        limitations=['Final saved landmarks are not the unrecorded registration PnP inliers or pre/post BA states',
            'Raw transitive conflicts do not identify which edge is wrong',
            'Sensor epipolar diagnostics assume supplied calibration and pose accuracy; no covariance or physical truth',
            'SVD and Jacobian diagnostics are not acceptance thresholds; pose block fixes uncertain landmarks'])
    (out/'audit.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(pairs=[{k:v for k,v in p.items() if k not in ('indexed_correspondences','shared_landmark_ids','direct_verified_shared_landmark_ids')} for p in pairs],
        selected_landmarks=len(landmarks),solver_warning_context=summary['solver_warning_context'],runtime_s=summary['runtime_s']),indent=2),flush=True)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trial',default='demo/phase3_mapping_only/trial1')
    p.add_argument('--out',required=True)
    a=p.parse_args();run(a.trial,a.out)
