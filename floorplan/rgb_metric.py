"""Bounded, opt-in RGB metric-geometry experiment. Not an accepted scale source.

Only RGB and RGB-derived geometry enter this backend. Independent reference
assets are never opened. It must pass property-level gates before promotion.
"""
from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import time

import numpy as np

from .provenance import sha256

MODEL='Ruicheng/moge-2-vits-normal'
REVISION='26b477f41595707c5db6770294c0d1721e8ed4ed'
CODE_REVISION='74fbce054ebed49800de42d0ad0e83495065719a'
WEIGHTS_SHA256='79a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc'


def calibrated_prediction_grid(k, width, height):
    """MoGe accepts horizontal FOV, centered principal point and square pixels.

    Rectify into that virtual camera before inference, then sample its depth
    back into the original pinhole camera. Both cameras share the optical axis,
    so their z depth is unchanged. Unsupported border pixels remain masked.
    """
    k=np.asarray(k,dtype=float)
    if (k.shape!=(3,3) or not np.isfinite(k).all() or min(k[0,0],k[1,1])<=0
            or not np.allclose(k[2],[0,0,1]) or abs(k[0,1])+abs(k[1,0])>1e-9):
        raise ValueError('RGB prediction requires finite, rectified pinhole calibration')
    virtual=k.copy(); virtual[1,1]=k[0,0]
    # MoGe/utils3d uses pixel centers at (i+.5)/size in normalized coordinates.
    virtual[0,2]=(width-1)/2; virtual[1,2]=(height-1)/2
    yy,xx=np.mgrid[:height,:width]
    to_original=((xx-virtual[0,2])*k[0,0]/virtual[0,0]+k[0,2],
                 (yy-virtual[1,2])*k[1,1]/virtual[1,1]+k[1,2])
    to_virtual=((xx-k[0,2])*virtual[0,0]/k[0,0]+virtual[0,2],
                (yy-k[1,2])*virtual[1,1]/k[1,1]+virtual[1,2])
    return dict(fov_x=float(np.degrees(2*np.arctan(width/(2*virtual[0,0])))),
                virtual_k=virtual,
                to_original=tuple(a.astype(np.float32) for a in to_original),
                to_virtual=tuple(a.astype(np.float32) for a in to_virtual))


def robust_metric_scale(samples):
    """One RGB-prior scale, not a laser fit; require support across two views."""
    valid=[s for s in samples if np.isfinite([s['model_depth_m'],s['sfm_depth']]).all()
           and s['model_depth_m']>.2 and s['sfm_depth']>0]
    counts={image:sum(s['image']==image for s in valid) for image in {s['image'] for s in valid}}
    supported={image for image,count in counts.items() if count>=10}
    valid=[s for s in valid if s['image'] in supported]
    if len(valid)<50 or len(supported)<2:
        raise ValueError('Metric scale needs >=50 depth-supported tracks across >=2 views')
    logs=np.log([s['model_depth_m']/s['sfm_depth'] for s in valid])
    median=float(np.median(logs))
    deviations=np.abs(logs-median)
    dispersion=float(np.quantile(deviations,.80))
    if dispersion>.25:
        raise ValueError(f'RGB metric prior is inconsistent across verified tracks (log-ratio p80={dispersion:.6f}, limit=0.25)')
    good=deviations<=max(.03,3*float(np.median(deviations)))
    accepted=[s for s,keep in zip(valid,good) if keep]
    if len(accepted)<50 or len({s['image'] for s in accepted})<2:
        raise ValueError('Too few consistent depth tracks after robust scale filtering')
    scale=float(np.exp(np.median(logs[good])))
    return scale,dict(source='RGB-only learned depth prior; no surveyed scale',support_tracks=len(accepted),
                      support_views=len({s['image'] for s in accepted}),log_ratio_p80=dispersion,
                      rejection_threshold=.25,threshold_status='development setting, not assessment gate')


def predict_images(paths,output,*,cameras=None,runtime_budget_s=600):
    import cv2
    import torch
    from PIL import Image,ImageOps
    from huggingface_hub import hf_hub_download
    from moge.model.v2 import MoGeModel
    source=json.loads(importlib.metadata.distribution('moge').read_text('direct_url.json') or '{}')
    if source.get('vcs_info',{}).get('commit_id')!=CODE_REVISION:
        raise ValueError('MoGe code revision differs from the pinned feasibility experiment')
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter(); deadline=started+runtime_budget_s
    cache=Path(__file__).resolve().parents[1]/'.tools/hf_cache/hub'
    checkpoint=Path(hf_hub_download(MODEL,'model.pt',revision=REVISION,cache_dir=str(cache)))
    if sha256(checkpoint)!=WEIGHTS_SHA256: raise ValueError('MoGe checkpoint checksum mismatch before model loading')
    torch.set_num_threads(4)
    torch.manual_seed(7)
    torch.use_deterministic_algorithms(True)
    model=MoGeModel.from_pretrained(checkpoint).to('cpu').eval()
    frames=[]
    for index,path in enumerate(map(Path,paths)):
        if time.perf_counter()>deadline: raise TimeoutError('RGB experiment processing budget exceeded')
        with Image.open(path) as image: rgb=ImageOps.exif_transpose(image).convert('RGB')
        width,height=rgb.size
        factor=min(1.,1024/max(width,height))
        rgb=rgb.resize((max(8,round(width*factor)),max(8,round(height*factor))))
        array=np.asarray(rgb).copy()
        grid=None
        if cameras and path.name in cameras:
            k=np.array(cameras[path.name],float)
            k[0]*=rgb.width/width; k[1]*=rgb.height/height
            grid=calibrated_prediction_grid(k,rgb.width,rgb.height)
            inference_array=cv2.remap(array,*grid['to_original'],cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_CONSTANT)
        else:
            inference_array=array
        image=torch.from_numpy(inference_array).permute(2,0,1).float()/255
        frame_start=time.perf_counter()
        with torch.inference_mode():
            prediction=model.infer(image,use_fp16=False,num_tokens=1200,
                                   fov_x=grid['fov_x'] if grid else None)
        depth=prediction['depth'].detach().cpu().numpy()
        mask=prediction['mask'].detach().cpu().numpy().astype(bool)
        depth=np.where(mask & np.isfinite(depth) & (depth>.2) & (depth<8),depth,0).astype(np.float32)
        if grid:
            valid_input=cv2.remap(np.ones((rgb.height,rgb.width),np.uint8),
                                 *grid['to_original'],cv2.INTER_NEAREST,
                                 borderMode=cv2.BORDER_CONSTANT).astype(bool)
            depth=np.where(valid_input,depth,0)
            depth=cv2.remap(depth,*grid['to_virtual'],cv2.INTER_NEAREST,
                            borderMode=cv2.BORDER_CONSTANT)
        else:
            k=prediction['intrinsics'].detach().cpu().numpy().copy()
            k[0]*=rgb.width; k[1]*=rgb.height
            k[0,2]-=.5; k[1,2]-=.5
        if depth.shape!=(rgb.height,rgb.width) or not np.isfinite(k).all():
            raise ValueError('Invalid RGB point-map dimensions/calibration')
        rgb_path=output/f'rgb_{index:04d}.png'; rgb.save(rgb_path)
        depth_path=output/f'depth_{index:04d}.npy'; np.save(depth_path,depth)
        frames.append(dict(id=index,source_name=path.name,source_rgb_sha256=sha256(path),
                           rgb=str(rgb_path.resolve()),depth=str(depth_path.resolve()),
                           intrinsics=dict(width=rgb.width,height=rgb.height,fx=float(k[0,0]),fy=float(k[1,1]),
                                           cx=float(k[0,2]),cy=float(k[1,2])),
                           inference_s=time.perf_counter()-frame_start,
                           calibration_source='SfM-conditioned virtual camera' if grid else 'RGB-inferred camera',
                           inference_fov_x_deg=grid['fov_x'] if grid else None,
                           depth_provenance='RGB prediction, not phone depth',prediction_sha256=sha256(depth_path)))
        print(f'RGB metric experiment: predicted {index+1}/{len(paths)} views',flush=True)
    metadata=dict(model=MODEL,revision=REVISION,code_revision=CODE_REVISION,weights_sha256=WEIGHTS_SHA256,
                  device='cpu',long_edge=1024,num_tokens=1200,runtime_s=time.perf_counter()-started,
                  random_seed=7,deterministic_torch_algorithms=True,
                  experimental=True,accuracy_validated=False,frames=frames)
    (output/'predictions.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return frames,metadata


def reconstruct_metric_rgb(sparse,run_directory,*,ordered_capture=False,max_views=24,room_groups=None,room_image_source=None,property_id=None,optimize_poses=True):
    if room_groups and len(room_groups)>1 and (not sparse.get('model_directory') or sparse.get('registered_fraction',0)<.9):
        return reconstruct_photo_property(room_groups,room_image_source,run_directory,property_id,optimize_poses=optimize_poses)
    import cv2
    from .rgbd import reconstruct_rgbd
    from .dense import _undistort
    root=Path(run_directory); images=Path(sparse['images_directory'])
    root.mkdir(parents=True,exist_ok=True)
    model=None; cameras={}; poses={}
    if sparse.get('model_directory'):
        import pycolmap
        model=pycolmap.Reconstruction(str(sparse['model_directory']))
        target=root/'rectified_rgb'; target.mkdir()
        for image in sorted(model.images.values(),key=lambda image:image.name):
            pixels=cv2.imread(str(images/image.name))
            pixels,k=_undistort(pixels,model.cameras[image.camera_id],cv2,max_width=1024)
            cv2.imwrite(str(target/image.name),pixels)
            cameras[image.name]=k
            pose=np.eye(4); pose[:3]=image.cam_from_world().matrix()
            poses[image.name]=np.linalg.inv(pose)
        images=target
    paths=sorted(p for p in images.iterdir() if p.suffix.lower() in {'.png','.jpg','.jpeg'})
    if len(paths)<2: raise ValueError('RGB metric experiment needs two usable views')
    selected={paths[i] for i in np.unique(np.linspace(0,len(paths)-1,min(max_views,len(paths))).astype(int))}
    if room_groups:
        required=set()
        for room,names in sorted(room_groups.items()):
            available=[p for p in paths if p.name in names]
            if len(available)<2: raise ValueError(f'Insufficient registered RGB views for room {room}')
            required.update(available[i] for i in np.unique(np.linspace(0,len(available)-1,2).astype(int)))
        if len(required)>max_views: raise ValueError('RGB view budget cannot support every room; increase the explicit experiment budget')
        selected=required|set(sorted(selected-required)[:max_views-len(required)])
    paths=sorted(selected)
    frames,metadata=predict_images(paths,root/'rgb_predictions',cameras=cameras)
    for frame in frames:
        if room_groups:
            frame['source_room_folder']=next(room for room,names in room_groups.items() if frame['source_name'] in names)
    scale_evidence=None
    if model is not None:
        samples=[]
        lookup={image.name:image for image in model.images.values()}
        for frame in frames:
            image=lookup[frame['source_name']]; depth=np.load(frame['depth'],allow_pickle=False)
            camera=frame['intrinsics']; transform=image.cam_from_world().matrix()
            for point in image.points2D:
                if not point.has_point3D(): continue
                xyz=transform[:,:3]@model.points3D[point.point3D_id].xyz+transform[:,3]
                if xyz[2]<=0: continue
                x=round(camera['fx']*xyz[0]/xyz[2]+camera['cx']); y=round(camera['fy']*xyz[1]/xyz[2]+camera['cy'])
                if 0<=x<camera['width'] and 0<=y<camera['height'] and depth[y,x]>.2:
                    samples.append(dict(image=image.name,model_depth_m=float(depth[y,x]),sfm_depth=float(xyz[2])))
        attempt=dict(samples=samples,source='RGB prior versus registered sparse tracks; no survey truth',
                     rejection_threshold_log_ratio_p80=.25)
        evidence_path=root/'metric_scale_attempt.json'
        try:
            scale,scale_evidence=robust_metric_scale(samples)
        except ValueError as exc:
            attempt.update(status='rejected',reason=str(exc))
            evidence_path.write_text(json.dumps(attempt,indent=2),encoding='utf-8')
            raise
        attempt.update(status='accepted',scale=scale,evidence=scale_evidence)
        evidence_path.write_text(json.dumps(attempt,indent=2),encoding='utf-8')
        for frame in frames:
            pose=poses[frame['source_name']].copy(); pose[:3,3]*=scale
            frame['camera_to_world']=pose.tolist()
    sequence=dict(schema_version=1,intrinsics=frames[0]['intrinsics'],depth_scale=1.,frames=frames,
                  metric_status='model_scaled',depth_provenance='RGB-only learned prediction',
                  optimize_poses=bool(optimize_poses),layout='polygons',
                  pose_source='rgb_reconstruction' if model is not None else 'estimated',
                  ordered_capture=ordered_capture)
    if not ordered_capture: sequence['path_breaks']=list(range(1,len(frames)))
    sequence_path=root/'normalized_sequence.json'
    sequence_path.write_text(json.dumps(sequence,indent=2),encoding='utf-8')
    result=reconstruct_rgbd(sequence_path,root/'artifacts')
    if room_groups and len(room_groups)>1 and result.get('plan_produced'):
        from shapely.geometry import Point,Polygon
        from scipy.optimize import linear_sum_assignment
        plan_path=root/'artifacts/plan.json'; plan=json.loads(plan_path.read_text(encoding='utf-8'))
        basis=np.asarray(plan['provenance']['basis_columns_in_input']); rooms=plan['rooms']
        trajectory=json.loads((root/'artifacts/trajectory.json').read_text(encoding='utf-8'))
        centers={str(p['frame_id']):(np.asarray(p['camera_to_first'])[:3,3]@basis)[[0,2]] for p in trajectory}
        folders=sorted(room_groups); support=np.zeros((len(folders),len(rooms)),int)
        for frame in frames:
            if str(frame['id']) not in centers: continue
            for i,room in enumerate(rooms):
                if Polygon(room['corners']).buffer(.03).covers(Point(centers[str(frame['id'])])):
                    support[folders.index(frame['source_room_folder']),i]+=1
        row,col=linear_sum_assignment(-support)
        identities={folders[a]:dict(stitched_room_ids=[rooms[b]['id']],support_views=int(support[a,b]))
                    for a,b in zip(row,col) if support[a,b]>=2}
        plan['provenance']['photo_room_folders']=identities
        (plan_path).write_text(json.dumps(plan,indent=2),encoding='utf-8')
        result['plan_metadata']=plan['provenance']
        if len(identities)!=len(folders):
            result.update(status='incomplete_property',floor_plan_ready=False,
                          reason='Registered views cannot establish every supplied room identity')
    result.update(experimental_backend=True,metric_status='model_scaled',rgb_metric_model=metadata,
                  scale_evidence=scale_evidence,accuracy_validated=False,
                  reference_used_for_inference=False,
                  promotion_status='not_validated_on_surveyed_properties')
    return result


def reconstruct_photo_property(room_groups,image_source,run_directory,property_id,*,optimize_poses=True):
    """Attempt independent room reconstructions then verified overlap registration.

    Missing room models/disconnected graph are explicit failures. Manual door
    anchors, adjacency and reference dimensions never enter this fallback.
    """
    import shutil
    from .workflow import reconstruct
    from .stitching import stitch_runs
    root=Path(run_directory); inputs=Path(image_source); runs=[]; failures=[]; records=[]
    for room_id,names in sorted(room_groups.items()):
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]+',room_id): raise ValueError('Unsafe room identity')
        if not 2<=len(names)<=8: raise ValueError('Roomwise photos require 2–8 images for each room')
        room=root/'rooms'/room_id; images=room/'images'; images.mkdir(parents=True)
        for name in names:
            if Path(name).name!=name: raise ValueError('Unsafe normalized room image name')
            shutil.copy2(inputs/name,images/name)
        manifest=room/'capture.json'
        manifest.write_text(json.dumps(dict(schema_version=3,tier='photos',source='images',profile='assignment',
                                            property_id=property_id or 'unidentified',max_frames=8,
                                            matching='exhaustive',metric_backend='moge2_experimental',
                                            optimize_poses=bool(optimize_poses)),indent=2),encoding='utf-8')
        ledger=reconstruct(manifest,room/'result')
        records.append(dict(room_id=room_id,status=ledger['result']['status'],run_sha256=sha256(room/'result/run.json')))
        if ledger['result'].get('floor_plan_ready') and (room/'result/plan.json').exists(): runs.append(room/'result')
        else: failures.append(room_id)
    result=dict(status='incomplete_property',floor_plan_ready=False,accuracy_validated=False,
                experimental_backend=True,metric_status='model_scaled',room_results=records,missing_room_ids=failures,
                promotion_status='not_validated_on_surveyed_properties')
    if failures: result['reason']='Some photo folders did not produce supported room geometry'; return result
    result['registration_coverage_source']='verified_per_room_models'
    stitched=stitch_runs(runs,root/'property_graph',optimize_poses=optimize_poses)
    result['property_graph']=stitched
    component=root/'property_graph/component_0'
    if not stitched['connected'] or not (component/'plan.json').exists():
        result['reason']='No verified whole-property room graph'; return result
    plan=json.loads((component/'plan.json').read_text(encoding='utf-8'))
    if len(plan['rooms'])<len(room_groups):
        result['reason']='Stitched geometry lost one or more supplied room identities'; return result
    identities=plan.get('provenance',{}).get('source_room_identity',{})
    matches=identities.get('matches',{})
    if (identities.get('missing_source_rooms') or
            any(not any(key.startswith(f'capture_{i}:') for key in matches) for i in range(len(runs)))):
        result['reason']='Supplied room identities could not be verified against stitched polygons'; return result
    plan['provenance']['photo_room_folders']={room:dict(source_capture=i,
        stitched_room_ids=[value['room_id'] for key,value in matches.items() if key.startswith(f'capture_{i}:')])
        for i,room in enumerate(sorted(room_groups))}
    (component/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    artifacts=root/'artifacts'; artifacts.mkdir(exist_ok=True)
    for name in ('plan.json','plan.svg','plan.dxf','quantities.csv','cloud.npz'):
        if (component/name).is_file(): shutil.copy2(component/name,artifacts/name)
    shutil.copy2(component/'normalized_sequence.json',root/'normalized_sequence.json')
    shutil.copy2(component/'trajectory.json',artifacts/'trajectory.json')
    ready=not plan.get('provenance',{}).get('unclosed_geometry',True)
    result.update(status='proposal_requires_review' if ready else 'partial',floor_plan_ready=ready,
                  plan_produced=True,plan_metadata=plan.get('provenance',{}),
                  mapping=dict(enabled=bool(optimize_poses),
                               verified_loops=sum(edge.get('cycle',False) for edge in stitched['verified_edges'])),
                  reason='Verified room identities and registered views retained; metric accuracy and damage remain unvalidated')
    return result
