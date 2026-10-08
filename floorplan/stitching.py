"""Join independently reconstructed RGB-D captures using verified visual overlap."""
from __future__ import annotations
import json
import time
from pathlib import Path
import numpy as np


def stitch_runs(run_paths,output: Path,*,optimize_poses=True):
    started=time.perf_counter()
    import cv2
    import open3d as o3d
    from .rgbd import _features,_relative_pose,_fit_planes
    from .layout import weighted_voxels,extract_layout,export_layout
    if output.exists() and any(output.iterdir()): raise FileExistsError('Stitch output must be fresh')
    output.mkdir(parents=True,exist_ok=True)
    if len(run_paths)<2: raise ValueError('At least two RGB-D run directories required')
    records=[]; sift=cv2.SIFT_create(nfeatures=2000)
    for folder in map(Path,run_paths):
        plan=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
        scale_status='model_scaled' if any(r.get('metric_status')=='model_scaled' for r in plan['rooms']) else 'sensor_scaled'
        sequence=json.loads((folder/'normalized_sequence.json').read_text(encoding='utf-8'))
        trajectory=json.loads((folder/'artifacts'/'trajectory.json').read_text(encoding='utf-8'))
        poses={str(p['frame_id']):np.asarray(p['camera_to_first']) for p in trajectory}
        frames=[f for f in sequence['frames'] if str(f['id']) in poses]
        selected=[]
        for i in np.unique(np.linspace(0,len(frames)-1,min(12,len(frames))).astype(int)):
            frame=frames[i]; camera=frame.get('intrinsics',sequence['intrinsics'])
            k=np.array([[camera['fx'],0,camera['cx']],[0,camera['fy'],camera['cy']],[0,0,1.]])
            gray=cv2.imread(frame['rgb'],cv2.IMREAD_GRAYSCALE)
            depth_path=Path(frame['depth'])
            depth=np.load(depth_path) if depth_path.suffix=='.npy' else cv2.imread(str(depth_path),-1)
            depth=depth.astype(float)/sequence['depth_scale']
            depth[(depth<.2)|(depth>8)|~np.isfinite(depth)]=0
            try: features=_features(gray,depth,sift,cv2)
            except ValueError: continue
            selected.append((features,k,poses[str(frame['id'])],frame['id']))
        cloud=np.load(folder/'artifacts'/'cloud.npz')
        pc=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(cloud['points'].astype(float)))
        pc=pc.voxel_down_sample(.04)
        pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=.15,max_nn=30))
        records.append({'frames':selected,'pc':pc,'points':cloud['points'],'rgb':cloud['rgb'],
                        'poses':list(poses.values()),'source':str(folder),'metric_status':scale_status,
                        'sequence':sequence,'trajectory':poses,'plan':plan})
    reg=o3d.pipelines.registration; edges=[]
    for a in range(len(records)):
        for b in range(a):
            candidates=[]
            for af,ak,ap,aid in records[a]['frames']:
                for bf,bk,bp,bid in records[b]['frames']:
                    try:
                        relative,quality=_relative_pose(af,bf,bk,cv2,ak,ordered_motion=False)
                        if quality['metric_inliers']>=40:
                            candidates.append((quality['metric_inliers'],bp@relative@np.linalg.inv(ap),aid,bid))
                    except ValueError: pass
            for inliers,initial,aid,bid in sorted(candidates,key=lambda c:-c[0])[:3]:
                fit=reg.registration_icp(records[a]['pc'],records[b]['pc'],.08,initial,
                    reg.TransformationEstimationPointToPlane(reg.TukeyLoss(k=.03)),reg.ICPConvergenceCriteria(max_iteration=40))
                delta=np.linalg.inv(initial)@fit.transformation
                angle=float(np.degrees(np.arccos(np.clip((np.trace(delta[:3,:3])-1)/2,-1,1))))
                if fit.fitness>.25 and fit.inlier_rmse<.035 and np.linalg.norm(delta[:3,3])<.10 and angle<5.:
                    edges.append({'a':a,'b':b,'transform':fit.transformation,'fitness':fit.fitness,'rmse_m':fit.inlier_rmse,
                                  'visual_inliers':inliers,'frame_pair':[aid,bid]})
                    break
    from .pose_graph import consistent_edges,map_room_identities
    edges,rejected_cycles=consistent_edges(len(records),edges)
    components=[]; pending=set(range(len(records)))
    while pending:
        component={min(pending)}
        while True:
            expanded=component|{e['a'] for e in edges if e['b'] in component}|{e['b'] for e in edges if e['a'] in component}
            if expanded==component: break
            component=expanded
        pending-=component; components.append(sorted(component))
    reports=[]
    for index,component in enumerate(components):
        transforms={component[0]:np.eye(4)}
        while len(transforms)<len(component):
            for e in edges:
                a,b=e['a'],e['b']
                if b in transforms and a not in transforms: transforms[a]=transforms[b]@e['transform']
                if a in transforms and b not in transforms: transforms[b]=transforms[a]@np.linalg.inv(e['transform'])
        graph=reg.PoseGraph()
        for i in component: graph.nodes.append(reg.PoseGraphNode(transforms[i]))
        local={value:i for i,value in enumerate(component)}
        for e in edges:
            if e['a'] in local and e['b'] in local:
                info=reg.get_information_matrix_from_point_clouds(records[e['a']]['pc'],records[e['b']]['pc'],.08,e['transform'])
                graph.edges.append(reg.PoseGraphEdge(local[e['a']],local[e['b']],e['transform'],info,uncertain=e['cycle']))
        if optimize_poses and len(component)>1:
            reg.global_optimization(graph,reg.GlobalOptimizationLevenbergMarquardt(),reg.GlobalOptimizationConvergenceCriteria(),reg.GlobalOptimizationOption(reference_node=0,max_correspondence_distance=.08))
        clouds=[]; colors=[]; centers=[]; breaks=[]
        for i,node in zip(component,graph.nodes):
            p=node.pose; record=records[i]
            clouds.append(record['points']@p[:3,:3].T+p[:3,3]); colors.append(record['rgb'])
            offset=sum(len(c) for c in centers)
            if centers: breaks.append(offset)
            from .rgbd import retained_path_breaks
            retained=[j for j,f in enumerate(record['sequence']['frames']) if str(f['id']) in record['trajectory']]
            breaks.extend(offset+b for b in retained_path_breaks(retained,record['sequence'].get('path_breaks',())))
            centers.append(np.asarray(record['poses'])[:,:3,3]@p[:3,:3].T+p[:3,3])
        points,rgb,_=weighted_voxels(np.concatenate(clouds),np.concatenate(colors))
        target=output/f'component_{index}'; target.mkdir()
        merged_frames=[]; merged_poses=[]; views=[]
        for i,node in zip(component,graph.nodes):
            record=records[i]; sequence=record['sequence']
            for frame in sequence['frames']:
                if str(frame['id']) not in record['trajectory']: continue
                merged=dict(frame); merged['id']=f"capture_{i}_{frame['id']}"
                pose=node.pose@record['trajectory'][str(frame['id'])]
                for key in ('rgb','depth','confidence'):
                    if key in merged:
                        merged[key]=str((Path(record['source'])/merged[key]).resolve())
                raw_path=Path(merged['depth'])
                raw=np.load(raw_path,allow_pickle=False) if raw_path.suffix=='.npy' else cv2.imread(str(raw_path),-1)
                depth=raw.astype(float)/sequence['depth_scale']
                depth[(depth<.2)|(depth>8)|~np.isfinite(depth)]=0
                if merged.get('confidence'):
                    confidence=cv2.imread(merged['confidence'],-1)
                    depth[confidence<sequence.get('minimum_confidence',1)]=0
                depth_path=target/f"depth_{merged['id']}.npy"; np.save(depth_path,depth.astype(np.float32))
                merged['depth']=str(depth_path.resolve()); merged.pop('timestamp_s',None)
                merged['camera_to_world']=pose.tolist()
                merged['intrinsics']=frame.get('intrinsics',sequence['intrinsics'])
                merged['source_capture']=record['source']; merged['source_frame_id']=frame['id']
                merged_frames.append(merged)
                merged_poses.append(dict(frame_id=merged['id'],camera_to_first=pose.tolist()))
                camera=merged['intrinsics']; yy,xx=np.mgrid[:depth.shape[0]:8,:depth.shape[1]:8]
                z=depth[yy,xx]; valid=z>0
                xyz=np.column_stack(((xx[valid]-camera['cx'])/camera['fx']*z[valid],
                                     (yy[valid]-camera['cy'])/camera['fy']*z[valid],z[valid]))
                views.append(dict(points=xyz@pose[:3,:3].T+pose[:3,3],camera=pose[:3,3]))
        merged_sequence=dict(schema_version=1,frames=merged_frames,depth_scale=1.,
                             pose_source='rgb_reconstruction',intrinsics=merged_frames[0]['intrinsics'],
                             optimize_poses=bool(optimize_poses),
                             ordered_capture=False,path_breaks=list(range(1,len(merged_frames))))
        (target/'normalized_sequence.json').write_text(json.dumps(merged_sequence,indent=2),encoding='utf-8')
        (target/'trajectory.json').write_text(json.dumps(merged_poses,indent=2),encoding='utf-8')
        np.savez_compressed(target/'cloud.npz',points=points,rgb=rgb)
        report={'captures':component,'status':'incomplete_geometry'}
        try:
            rooms,metadata=extract_layout(points,_fit_planes(points),np.concatenate(centers),
                np.asarray(records[component[0]]['poses'][0])[:3,1],path_breaks=breaks)
            metadata['capture_sources']=[records[i]['source'] for i in component]
            metric_status='model_scaled' if any(records[i]['metric_status']=='model_scaled' for i in component) else 'sensor_scaled'
            metadata['depth_provenance']='RGB-derived metric proposal' if metric_status=='model_scaled' else 'declared metric sensor depth'
            from .openings import augment_room_openings
            augment_room_openings(rooms,metadata,views)
            source_polygons={}; basis=np.asarray(metadata['basis_columns_in_input'])
            for i,node in zip(component,graph.nodes):
                original=records[i]['plan']; prior=original.get('provenance',{})
                if prior.get('floor_level_m') is None or 'basis_columns_in_input' not in prior: continue
                original_basis=np.asarray(prior['basis_columns_in_input'])
                for room in original['rooms']:
                    corners=np.asarray(room['corners'])
                    xyz=np.column_stack((corners[:,0],np.full(len(corners),prior['floor_level_m']),corners[:,1]))@original_basis.T
                    moved=(xyz@node.pose[:3,:3].T+node.pose[:3,3])@basis
                    source_polygons[f"capture_{i}:{room['id']}"]=moved[:,[0,2]].tolist()
            identities=map_room_identities(source_polygons,rooms)
            metadata['source_room_identity']=identities
            metadata['capture_transforms']={str(i):node.pose.tolist() for i,node in zip(component,graph.nodes)}
            export_layout(rooms,metadata,target,metric_status,not metadata['unclosed_geometry'])
            report.update(status='partial' if metadata['unclosed_geometry'] else 'proposal_requires_review',rooms=len(rooms))
        except ValueError as exc: report['reason']=str(exc)
        reports.append(report)
    from .workflow import file_hash
    result={'components':reports,'connected':len(components)==1,'accuracy_validated':False,
            'runtime_s':time.perf_counter()-started,
            'source_runs':{str(p):file_hash(Path(p)/'run.json') for p in run_paths},
            'code_sha256':{p.name:file_hash(p) for p in Path(__file__).parent.glob('*.py')},
            'verified_edges':[{**e,'transform':e['transform'].tolist()} for e in edges],
            'rejected_edges':[{**e,'transform':np.asarray(e['transform']).tolist()} for e in rejected_cycles],
            'pose_correction_enabled':bool(optimize_poses),
            'limitations':'Independent sensor or explicitly RGB-derived point-map captures; learned scale remains unvalidated.'}
    (output/'stitch_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
