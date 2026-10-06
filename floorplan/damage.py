"""Experimental wall discoloration/crack candidates with RGB-D surface projection.

This deterministic baseline is not a trained or validated damage classifier.
Candidates trigger inspection scope only; concealed damage is never asserted.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from shapely.geometry import box, mapping
from shapely.ops import unary_union

from .uncertainty import engineering_interval


def segment_wall_candidates(rgb,wall_mask):
    import cv2
    rgb=np.asarray(rgb,dtype=np.uint8)
    mask=np.asarray(wall_mask,dtype=bool)
    if mask.shape!=rgb.shape[:2]: raise ValueError('Wall mask dimensions differ from RGB')
    if mask.sum()<150: return []
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    # Colored material is not a neutral-wall stain baseline.
    neutral=np.median(hsv[:,:,1][mask])<70
    stain=mask & (hsv[:,:,0]>=5) & (hsv[:,:,0]<=40) & (hsv[:,:,1]>75) & (hsv[:,:,2]>55) if neutral else np.zeros_like(mask)
    blackhat=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,np.ones((9,9),np.uint8))
    crack=mask & (blackhat>35) & (gray<150)
    result=[]
    for label,binary in [('water_stain_candidate',stain),('crack_candidate',crack)]:
        count,components,stats,_=cv2.connectedComponentsWithStats(binary.astype(np.uint8),8)
        for i in range(1,count):
            x,y,w,h,area=stats[i]
            if area<max(12,rgb.shape[0]*rgb.shape[1]*.0005): continue
            if label=='crack_candidate' and max(w,h)/max(1,min(w,h))<4: continue
            result.append(dict(class_name=label,mask=components==i,review_required=True,
                               method='experimental color/morphology-v1'))
    return result


def merge_surface_regions(observations,cell_m=.02):
    """Union occupied surface cells; repeated views cannot multiply the quantity."""
    groups={}
    for observation in observations:
        key=(observation['surface_id'],observation['class_name'])
        group=groups.setdefault(key,dict(cells=set(),evidence=set()))
        uv=np.asarray(observation['uv_m'],float)
        if uv.ndim!=2 or uv.shape[1]!=2 or not np.isfinite(uv).all():
            raise ValueError('Damage coordinates must be finite Nx2 surface coordinates')
        group['cells'].update(map(tuple,np.floor(uv/cell_m).astype(int)))
        group['evidence'].update(observation.get('evidence_ids',[]))
    regions=[]
    for (surface,label),group in sorted(groups.items()):
        polygon=unary_union([box(x*cell_m,y*cell_m,(x+1)*cell_m,(y+1)*cell_m) for x,y in sorted(group['cells'])])
        if polygon.is_empty: continue
        bounds=polygon.bounds
        regions.append(dict(id=f'damage:{len(regions)}',surface_id=surface,class_name=label,
                            review_required=True,observed_damage_confirmed=False,
                            surface_geometry=mapping(polygon),area_m2=float(polygon.area),
                            width_m=bounds[2]-bounds[0],height_m=bounds[3]-bounds[1],
                            area_interval=engineering_interval(polygon.area,polygon.length*(cell_m+.03),'m2'),
                            evidence_ids=sorted(group['evidence']),method='2 cm surface occupancy union'))
    return regions


def inspection_scope(regions):
    flags=[]; scope=[]
    for region in regions:
        moisture=region['class_name']=='water_stain_candidate'
        rule='visual_discoloration_requires_moisture_check_v1' if moisture else 'linear_mark_requires_crack_review_v1'
        if moisture:
            flags.append(dict(id=f"flag:{region['id']}",surface_id=region['surface_id'],
                              rule_id=rule,source_region_id=region['id'],
                              conclusion='possible concealed moisture; inspect before remediation',
                              concealed_damage_observed=False,review_required=True))
        scope.append(dict(id=f"scope:{region['id']}",surface_id=region['surface_id'],
                          action='inspect_moisture' if moisture else 'inspect_linear_mark',
                          quantity=region['area_m2'],unit='m2',interval=region['area_interval'],
                          source_region_id=region['id'],rule_id=rule,review_required=True))
    return flags,scope


def assess_rgbd_damage(plan,run_dir,assessment,max_frames=12):
    """Only pixels depth-consistent with a reconstructed wall enter segmentation."""
    import cv2
    root=Path(run_dir)
    sequence_path=root/'normalized_sequence.json'
    provenance=plan.get('provenance',{})
    if not sequence_path.exists() or provenance.get('floor_level_m') is None:
        return dict(status='not_evaluated',reason='metric RGB-D surface registration or floor datum unavailable',evidence=[])
    sequence=json.loads(sequence_path.read_text())
    frames=sequence['frames']
    trajectory_path=root/'artifacts'/'trajectory.json'
    poses={str(r['frame_id']):np.asarray(r['camera_to_first']) for r in json.loads(trajectory_path.read_text())} if trajectory_path.exists() else {}
    basis=np.asarray(provenance['basis_columns_in_input']); floor=provenance['floor_level_m']
    walls=[s for s in assessment['surfaces'] if s['kind']=='wall']
    observations=[]; evidence=[]
    directory=root/'damage_evidence'; directory.mkdir(exist_ok=True)
    for index in np.unique(np.linspace(0,len(frames)-1,min(max_frames,len(frames))).astype(int)):
        frame=frames[index]
        # Frames rejected by tracking must never be resurrected with a raw pose.
        if poses and str(frame['id']) not in poses: continue
        rgb=cv2.imread(str(sequence_path.parent/frame['rgb']))
        depth_path=sequence_path.parent/frame['depth']
        raw=np.load(depth_path) if depth_path.suffix=='.npy' else cv2.imread(str(depth_path),cv2.IMREAD_UNCHANGED)
        if rgb is None or raw is None: continue
        depth=raw.astype(float)/sequence['depth_scale']
        valid=np.isfinite(depth)&(depth>.2)&(depth<8)
        if frame.get('confidence'):
            confidence=cv2.imread(str(sequence_path.parent/frame['confidence']),cv2.IMREAD_UNCHANGED)
            valid &= confidence>=sequence.get('minimum_confidence',1)
        camera=frame.get('intrinsics',sequence['intrinsics'])
        yy,xx=np.indices(depth.shape)
        xyz=np.stack([(xx-camera['cx'])/camera['fx']*depth,(yy-camera['cy'])/camera['fy']*depth,depth],axis=-1)
        pose=poses[str(frame['id'])] if str(frame['id']) in poses else np.asarray(frame['camera_to_world'])
        aligned=(xyz@pose[:3,:3].T+pose[:3,3])@basis
        overlay=rgb.copy(); frame_regions=0
        for surface in walls:
            a,b=np.asarray(surface['endpoints']); direction=b-a; length=np.linalg.norm(direction); direction/=length
            delta=aligned[:,:,[0,2]]-a
            u=delta@direction; h=floor-aligned[:,:,1]
            distance=np.abs(delta@np.array([-direction[1],direction[0]]))
            top=surface.get('height_m') or 5.
            wall=valid&(distance<.06)&(u>=0)&(u<=length)&(h>=.05)&(h<=top)
            for candidate in segment_wall_candidates(cv2.cvtColor(rgb,cv2.COLOR_BGR2RGB),wall):
                region=candidate['mask']
                eid=f"frame:{frame['id']}"
                observations.append(dict(surface_id=surface['id'],class_name=candidate['class_name'],
                                         uv_m=np.column_stack([u[region],h[region]]).tolist(),evidence_ids=[eid]))
                color=np.array([20,80,240]) if candidate['class_name']=='water_stain_candidate' else np.array([240,160,20])
                overlay[region]=(.5*overlay[region]+.5*color).astype(np.uint8)
                frame_regions+=1
        name=f"frame_{frame['id']}.png"
        cv2.imwrite(str(directory/name),overlay)
        evidence.append(dict(id=f"frame:{frame['id']}",image=f'damage_evidence/{name}',candidate_count=frame_regions))
    regions=merge_surface_regions(observations)
    flags,scope=inspection_scope(regions)
    assessment['damage_regions']=regions; assessment['concealed_flags']=flags; assessment['scope_items']=scope
    for region in regions:
        for kind,value,unit,interval in [('area',region['area_m2'],'m2',region['area_interval']),
                                         ('width',region['width_m'],'m',engineering_interval(region['width_m'],.10,'m')),
                                         ('height',region['height_m'],'m',engineering_interval(region['height_m'],.10,'m'))]:
            assessment['measurements'].append(dict(id=f"{region['id']}:{kind}",entity_id=region['id'],kind=kind,
                                                  value=value,unit=unit,status='estimated',interval=interval))
    return dict(status='experimental_candidates_require_review',frames_evaluated=len(evidence),evidence=evidence,
                limitations=['Color and morphology are not a trained damage classifier',
                             'Paint, shadows, trim and furniture can trigger false positives',
                             'Only inspection actions are generated; no remediation or insurance decision'])
