"""Join independently reconstructed RGB-D captures using verified visual overlap."""
from __future__ import annotations
import json
import time
from pathlib import Path
import numpy as np


def stitch_runs(run_paths,output: Path):
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
                        'poses':list(poses.values()),'source':str(folder)})
    reg=o3d.pipelines.registration; edges=[]
    for a in range(len(records)):
        for b in range(a):
            candidates=[]
            for af,ak,ap,aid in records[a]['frames']:
                for bf,bk,bp,bid in records[b]['frames']:
                    try:
                        relative,quality=_relative_pose(af,bf,bk,cv2,ak)
                        if quality['metric_inliers']>=40:
                            candidates.append((quality['metric_inliers'],bp@relative@np.linalg.inv(ap),aid,bid))
                    except ValueError: pass
            for inliers,initial,aid,bid in sorted(candidates,key=lambda c:-c[0])[:3]:
                fit=reg.registration_icp(records[a]['pc'],records[b]['pc'],.08,initial,
                    reg.TransformationEstimationPointToPlane(reg.TukeyLoss(k=.03)),reg.ICPConvergenceCriteria(max_iteration=40))
                delta=np.linalg.inv(initial)@fit.transformation
                if fit.fitness>.25 and fit.inlier_rmse<.035 and np.linalg.norm(delta[:3,3])<.10:
                    edges.append({'a':a,'b':b,'transform':fit.transformation,'fitness':fit.fitness,'rmse_m':fit.inlier_rmse,
                                  'visual_inliers':inliers,'frame_pair':[aid,bid]})
                    break
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
                graph.edges.append(reg.PoseGraphEdge(local[e['a']],local[e['b']],e['transform'],info,uncertain=False))
        if len(component)>1:
            reg.global_optimization(graph,reg.GlobalOptimizationLevenbergMarquardt(),reg.GlobalOptimizationConvergenceCriteria(),reg.GlobalOptimizationOption(reference_node=0,max_correspondence_distance=.08))
        clouds=[]; colors=[]; centers=[]; breaks=[]
        for i,node in zip(component,graph.nodes):
            p=node.pose; record=records[i]
            clouds.append(record['points']@p[:3,:3].T+p[:3,3]); colors.append(record['rgb'])
            if centers: breaks.append(sum(len(c) for c in centers))
            centers.append(np.asarray(record['poses'])[:,:3,3]@p[:3,:3].T+p[:3,3])
        points,rgb,_=weighted_voxels(np.concatenate(clouds),np.concatenate(colors))
        target=output/f'component_{index}'; target.mkdir()
        np.savez_compressed(target/'cloud.npz',points=points,rgb=rgb)
        report={'captures':component,'status':'incomplete_geometry'}
        try:
            rooms,metadata=extract_layout(points,_fit_planes(points),np.concatenate(centers),
                np.asarray(records[component[0]]['poses'][0])[:3,1],path_breaks=breaks)
            metadata['capture_sources']=[records[i]['source'] for i in component]
            export_layout(rooms,metadata,target)
            report.update(status='partial' if metadata['unclosed_geometry'] else 'proposal_requires_review',rooms=len(rooms))
        except ValueError as exc: report['reason']=str(exc)
        reports.append(report)
    from .workflow import file_hash
    result={'components':reports,'connected':len(components)==1,'accuracy_validated':False,
            'runtime_s':time.perf_counter()-started,
            'source_runs':{str(p):file_hash(Path(p)/'run.json') for p in run_paths},
            'code_sha256':{p.name:file_hash(p) for p in Path(__file__).parent.glob('*.py')},
            'verified_edges':[{**e,'transform':e['transform'].tolist()} for e in edges],
            'limitations':'RGB-D independent captures only; RGB photos/video use one common SfM reconstruction.'}
    (output/'stitch_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
