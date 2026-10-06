"""Measured-scale COLMAP bridge and bounded CPU stereo reconstruction."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np


def camera_path_quality(model, scale, ordered_capture):
    """Conservative discontinuity screen, not an accuracy certificate."""
    images = sorted(model.images.values(), key=lambda image: image.name)
    centers = np.asarray([image.projection_center()*scale for image in images])
    steps = np.linalg.norm(np.diff(centers, axis=0), axis=1)
    jumps = [dict(previous=images[i].name, current=images[i+1].name, distance_m=float(step))
             for i, step in enumerate(steps) if step > 2.0]
    return dict(checked=bool(ordered_capture), passed=not ordered_capture or not jumps,
                maximum_step_m=float(steps.max()) if len(steps) else 0.,
                maximum_allowed_step_m=2., suspicious_transitions=jumps if ordered_capture else [],
                limitation='Ordered continuous captures only; passing does not establish accurate poses')


def triangulate_control(observations, images, cameras):
    observations = [o for o in observations if o['image'] in images]
    rays, centers, rows = [], [], []
    for obs in observations:
        image = images[obs['image']]
        camera = cameras[image.camera_id]
        uv = np.asarray(obs['pixel'], float)
        if uv.shape != (2,) or not np.isfinite(uv).all() or not (0 <= uv[0] < camera.width and 0 <= uv[1] < camera.height):
            raise ValueError('Scale-control pixel is outside its registered image')
        xy = camera.cam_from_img(uv)
        if xy is None or not np.isfinite(xy).all():
            raise ValueError('Could not unproject scale-control pixel')
        p = image.cam_from_world().matrix()
        rows.extend([xy[0]*p[2]-p[0], xy[1]*p[2]-p[1]])
        centers.append(-p[:,:3].T @ p[:,3])
        ray = p[:,:3].T @ np.r_[xy, 1.0]
        rays.append(ray/np.linalg.norm(ray))
    if len(rows) < 4 or len({o['image'] for o in observations}) < 2:
        raise ValueError('Each scale endpoint needs at least two registered views')
    angles = [np.arccos(np.clip(np.dot(a,b), -1,1)) for a in rays for b in rays]
    if max(angles) < np.deg2rad(2):
        raise ValueError('Scale reference has less than 2 degrees triangulation parallax')
    _, _, vt = np.linalg.svd(rows)
    if abs(vt[-1,3]) < 1e-10:
        raise ValueError('Scale endpoint triangulates at infinity')
    point = vt[-1,:3]/vt[-1,3]
    residuals = []
    for obs in observations:
        image = images[obs['image']]
        p = image.cam_from_world().matrix()
        xyz = p[:,:3] @ point + p[:,3]
        if xyz[2] <= 0:
            raise ValueError('Scale endpoint lies behind a camera')
        residuals.append(np.linalg.norm(cameras[image.camera_id].img_from_cam(xyz)-obs['pixel']))
    if max(residuals) > 2:
        raise ValueError('Scale endpoint reprojection exceeds 2 pixels')
    return point, float(max(residuals))


def measured_scale(model, controls):
    images = {i.name:i for i in model.images.values()}
    estimates, evidence = [], []
    for control in controls:
        length = float(control['length_m'])
        if not np.isfinite(length) or length <= 0:
            raise ValueError('Measured reference length must be finite and positive')
        a, ar = triangulate_control(control['a'], images, model.cameras)
        b, br = triangulate_control(control['b'], images, model.cameras)
        distance = np.linalg.norm(a-b)
        if distance < 1e-6:
            raise ValueError('Scale endpoints coincide')
        estimates.append(length/distance)
        evidence.append({'length_m':length, 'reprojection_max_px':max(ar,br), 'scale':length/distance,
                         'excluded_evaluation_edges':control.get('excluded_evaluation_edges',[])})
    if not estimates:
        raise ValueError('RGB reconstruction needs a measured scale reference')
    scale = float(np.median(estimates))
    if max(abs(np.asarray(estimates)/scale-1)) > 0.03:
        raise ValueError('Measured references disagree by more than 3 percent')
    return scale, evidence


def _undistort(image, camera, cv2, max_width=640):
    ratio = min(1., max_width/camera.width)
    width, height = int(camera.width*ratio), int(camera.height*ratio)
    focal = camera.focal_length_x * ratio
    k = np.array([[focal,0,(width-1)/2],[0,camera.focal_length_y*ratio,(height-1)/2],[0,0,1.]])
    yy, xx = np.mgrid[:height,:width]
    rays = np.column_stack([(xx.ravel()-k[0,2])/k[0,0],(yy.ravel()-k[1,2])/k[1,1],np.ones(width*height)])
    uv = camera.img_from_cam(rays).reshape(height,width,2).astype(np.float32)
    return cv2.remap(image,uv[:,:,0],uv[:,:,1],cv2.INTER_LINEAR), k


def supported_sparse(model, scale):
    """Supplement stereo with long, low-error tracks with triangulation parallax."""
    centers={i.image_id:i.projection_center() for i in model.images.values()}
    xyz=[]; colors=[]
    for point in model.points3D.values():
        if point.error>.75 or point.track.length()<4: continue
        viewing=np.asarray([point.xyz-centers[e.image_id] for e in point.track.elements])
        viewing/=np.linalg.norm(viewing,axis=1)[:,None]
        if np.min(viewing@viewing.T)>np.cos(np.deg2rad(2)): continue
        xyz.append(point.xyz*scale); colors.append(point.color)
    return np.asarray(xyz).reshape(-1,3),np.asarray(colors).reshape(-1,3)


def reconstruct_dense(model_path: Path, images_path: Path, output: Path, controls, max_pairs=80, ordered_capture=False):
    import cv2
    import pycolmap
    from .rgbd import _fit_planes
    from .layout import weighted_voxels, extract_layout, export_layout
    cv2.setNumThreads(4)
    model = pycolmap.Reconstruction(model_path)
    scale, scale_evidence = measured_scale(model, controls)
    quality = camera_path_quality(model, scale, ordered_capture)
    if not quality['passed']:
        output.mkdir(parents=True, exist_ok=True)
        result = dict(status='incomplete_geometry', reason='Discontinuous camera trajectory; inspect matching or capture gaps',
                      floor_plan_ready=False, accuracy_validated=False, camera_path_quality=quality,
                      metric_scale=scale, scale_evidence=scale_evidence)
        (output/'dense_summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        return result
    images = sorted(model.images.values(),key=lambda i:i.name)
    tracks = {i.name:{p.point3D_id for p in i.points2D if p.has_point3D()} for i in images}
    poses = {}
    for image in images:
        p = np.eye(4)
        p[:3] = image.cam_from_world().matrix()
        pose = np.linalg.inv(p)
        pose[:3,3] *= scale
        poses[image.name] = pose
    clouds, colors, centers, logs = [], [], [], []
    cache = {}
    for a in images:
        if len(logs) >= max_pairs:
            break
        pose_a = poses[a.name]
        candidates = []
        for b in images:
            baseline = np.linalg.norm(pose_a[:3,3]-poses[b.name][:3,3])
            facing = np.dot(pose_a[:3,2],poses[b.name][:3,2])
            common = len(tracks[a.name] & tracks[b.name])
            if 0.10 <= baseline <= 0.65 and facing > 0.85 and common >= 30:
                candidates.append((common,b))
        if not candidates:
            continue
        _, b = max(candidates,key=lambda item:item[0])
        pair = tuple(sorted([a.name,b.name]))
        if pair in cache:
            continue
        cache[pair] = True
        ia = cv2.imread(str(images_path/a.name)); ib = cv2.imread(str(images_path/b.name))
        if ia is None or ib is None:
            raise ValueError('Registered images are missing from dense input')
        ia, ka = _undistort(ia,model.cameras[a.camera_id],cv2)
        ib, kb = _undistort(ib,model.cameras[b.camera_id],cv2)
        if ia.shape != ib.shape:
            continue
        relative = np.linalg.inv(poses[b.name]) @ pose_a
        size = (ia.shape[1],ia.shape[0])
        r1,r2,p1,p2,q,_,_ = cv2.stereoRectify(ka,None,kb,None,size,relative[:3,:3].copy(),relative[:3,3].reshape(3,1).copy(),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
        # StereoSGBM searches horizontal disparity only.
        if abs(p2[1,3]) > abs(p2[0,3]):
            logs.append({'pair':pair,'status':'unsupported_stereo_direction'})
            continue
        if p2[0,3] >= 0:
            a,b=b,a
            ia,ib=ib,ia; ka,kb=kb,ka
            pose_a=poses[a.name]
            relative=np.linalg.inv(poses[b.name])@pose_a
            r1,r2,p1,p2,q,_,_=cv2.stereoRectify(ka,None,kb,None,size,relative[:3,:3].copy(),relative[:3,3].reshape(3,1).copy(),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
        maps_a = cv2.initUndistortRectifyMap(ka,None,r1,p1[:,:3],size,cv2.CV_32FC1)
        maps_b = cv2.initUndistortRectifyMap(kb,None,r2,p2[:,:3],size,cv2.CV_32FC1)
        left = cv2.remap(ia,*maps_a,cv2.INTER_LINEAR)
        right = cv2.remap(ib,*maps_b,cv2.INTER_LINEAR)
        count = min(160, (size[0]//3//16)*16)
        matcher = cv2.StereoSGBM_create(minDisparity=0,numDisparities=count,blockSize=5,P1=8*25,P2=32*25,
            disp12MaxDiff=1,uniquenessRatio=12,speckleWindowSize=100,speckleRange=2)
        reverse = cv2.StereoSGBM_create(minDisparity=-count,numDisparities=count,blockSize=5,P1=8*25,P2=32*25,
            uniquenessRatio=12,speckleWindowSize=100,speckleRange=2)
        l = cv2.cvtColor(left,cv2.COLOR_BGR2GRAY); r = cv2.cvtColor(right,cv2.COLOR_BGR2GRAY)
        disparity = matcher.compute(l,r).astype(float)/16
        opposite = reverse.compute(r,l).astype(float)/16
        yy,xx = np.mgrid[:size[1],:size[0]]
        xr = np.rint(xx-disparity).astype(int)
        valid = (disparity > 0) & (xr >= 0) & (xr < size[0])
        valid &= np.abs(disparity+opposite[yy,np.clip(xr,0,size[0]-1)]) < 1
        xyz = cv2.reprojectImageTo3D(disparity.astype(np.float32),q)
        valid &= np.isfinite(xyz).all(axis=2) & (xyz[:,:,2] > 0.25) & (xyz[:,:,2] < 8)
        valid &= (xx % 3 == 0) & (yy % 3 == 0)
        local = xyz[valid] @ r1
        world = local @ pose_a[:3,:3].T+pose_a[:3,3]
        # A third view's sparse visibility supports pair selection; explicit
        # dense consistency is provided by independent pair voxel agreement below.
        clouds.append(world); colors.append(left[valid,::-1]); centers.append(pose_a[:3,3])
        logs.append({'pair':pair,'status':'depth','points':len(world)})
        print(f'CPU stereo: {len(logs)} pairs, {len(world)} points',flush=True)
    output.mkdir(parents=True,exist_ok=True)
    result = {'metric_scale':scale,'scale_evidence':scale_evidence,'pairs':logs,'floor_plan_ready':False,'accuracy_validated':False,
              'camera_path_quality':quality}
    if not clouds or sum(map(len,clouds)) < 1000:
        result.update(status='incomplete_geometry',reason='Insufficient consistent stereo depth')
    else:
        # Require support from at least two independent stereo pairs per 4cm cell.
        raw = np.concatenate(clouds)
        keys = np.floor(raw/0.04).astype(np.int64)
        _, inverse = np.unique(keys,axis=0,return_inverse=True)
        labels = np.concatenate([np.full(len(c),i) for i,c in enumerate(clouds)])
        unique = np.unique(np.column_stack([inverse,labels]),axis=0)
        support = np.bincount(unique[:,0],minlength=inverse.max()+1)
        good = support[inverse] >= 2
        sparse_xyz,sparse_rgb=supported_sparse(model,scale)
        points,rgb,_ = weighted_voxels(np.concatenate([raw[good],sparse_xyz]),np.concatenate([np.concatenate(colors)[good],sparse_rgb]))
        result['supplementary_supported_sparse_points']=len(sparse_xyz)
        np.savez_compressed(output/'cloud.npz',points=points,rgb=rgb)
        centers=np.asarray([poses[i.name][:3,3] for i in images])
        np.save(output/'camera_centers.npy',centers)
        try:
            planes = _fit_planes(points)
            # SfM world orientation is arbitrary; use first registered camera down.
            rooms,metadata = extract_layout(points,planes,centers,poses[images[0].name][:3,1],
                                            path_breaks=() if ordered_capture else range(1,len(centers)))
            metadata['ordered_capture']=ordered_capture
            metadata['scale_evidence'] = scale_evidence
            (output/'layout_evidence.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
            export_layout(rooms,metadata,output,'reference_scaled')
            result.update(status='partial' if metadata['unclosed_geometry'] else 'proposal_requires_review',
                          floor_plan_ready=not metadata['unclosed_geometry'],plan_produced=True,
                          camera_center_coverage_fraction=metadata['camera_center_coverage_fraction'])
        except ValueError as exc:
            result.update(status='incomplete_geometry',reason=str(exc))
        result['point_count'] = len(points)
    (output/'dense_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
