"""Read-only sensor audit of the footprint notch in the supplied ceiling scan.

No geometry, matching, pose estimation, mapping or acceptance guards are changed.
Ray/support evidence is conditional on supplied calibration and raw/refined poses;
it is not independently surveyed geometry or a ceiling-height error measurement.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import cv2
import numpy as np
from scipy.spatial.transform import Rotation
from shapely.geometry import LineString, Polygon

from floorplan.layout import _line, weighted_voxels
from floorplan.provenance import sha256
from floorplan.rgbd import _backproject

HEIGHT_BINS=np.array([.25,.5,.75,1.,1.25,1.5,1.75,2.,2.25,2.5,2.75,3.])
NUMERIC_EDGE_BAND=1e-8  # Source-line association only; not sensor/acceptance tolerance.


def parts(geometry):
    if geometry.is_empty:return []
    return list(geometry.geoms) if hasattr(geometry,'geoms') else [geometry]


def changed_edges(before,after):
    removed=before.difference(after)
    polygons=[p for p in parts(removed) if isinstance(p,Polygon)]
    if not polygons:raise ValueError('No removed footprint region exists')
    region=max(polygons,key=lambda p:p.area)
    rows=[]
    for kind,poly,other in (('original',before,after),('shifted',after,before)):
        coords=np.asarray(poly.exterior.coords)
        for i,(a,b) in enumerate(zip(coords[:-1],coords[1:])):
            changed=LineString([a,b]).difference(other.boundary.buffer(NUMERIC_EDGE_BAND))
            for line in parts(changed.intersection(region.buffer(NUMERIC_EDGE_BAND))):
                # Discard numerical slivers, not observations or physical walls.
                if isinstance(line,LineString) and line.length>=.25:
                    rows.append(dict(kind=kind,polygon_edge=i,endpoints=np.asarray(line.coords)[[0,-1]].tolist()))
    return region,rows


def finite_mask(points,normal,offset,edge,floor,band=.035):
    points=np.asarray(points,float);edge=np.asarray(edge,float)
    direction=edge[1]-edge[0];length=np.linalg.norm(direction)
    if length<=0:raise ValueError('Finite edge must have positive length')
    along=(points[:,[0,2]]-edge[0])@(direction/length)
    heights=floor-points[:,1]
    return ((along>=0)&(along<=length)&(heights>.25)&(heights<3.)
            &(np.abs(points@normal+offset)<band))


def crossing_rays(camera,endpoints,normal,offset,edge,floor,clearance=.10):
    camera=np.asarray(camera,float);endpoints=np.asarray(endpoints,float);edge=np.asarray(edge,float)
    direction=endpoints-camera
    denominator=direction@normal
    t=np.divide(-(camera@normal+offset),denominator,
        out=np.full(len(endpoints),np.nan),where=np.abs(denominator)>1e-12)
    intersections=camera+t[:,None]*direction
    lengths=np.linalg.norm(direction,axis=1)
    tangent=edge[1]-edge[0];length=np.linalg.norm(tangent)
    if length<=0:raise ValueError('Finite edge must have positive length')
    along=(intersections[:,[0,2]]-edge[0])@(tangent/length)
    heights=floor-intersections[:,1]
    mask=(np.isfinite(t)&(t>0)&(t<1)&(t*lengths>clearance)&((1-t)*lengths>clearance)
          &(along>=0)&(along<=length)&(heights>.25)&(heights<3.))
    return mask,intersections[mask]


def support_profile(points,normal,offset,edge,floor):
    mask=finite_mask(points,normal,offset,edge,floor)
    q=points[mask];heights=floor-q[:,1]
    return dict(points=len(q),height_histogram=np.histogram(heights,HEIGHT_BINS)[0].tolist(),
        height_span_m=float(np.ptp(heights)) if len(q) else None,
        robust_height_span_m=float(np.ptp(np.quantile(heights,[.05,.95]))) if len(q) else None,
        height_range_m=[float(heights.min()),float(heights.max())] if len(q) else None,
        rms_m=float(np.sqrt(np.mean((q@normal+offset)**2))) if len(q) else None)


def associate(edge,meta,planes,basis,floor):
    query=LineString(edge)
    scored=[(query.intersection(_line(s).buffer(NUMERIC_EDGE_BAND)).length,i,s)
            for i,s in enumerate(meta['boundary_network'])]
    score,index,segment=max(scored,key=lambda row:row[0])
    if score/query.length<.999999 or segment['source_kind']!='observed_wall':
        raise ValueError('Query does not have an observed finite-network association')
    matches=[]
    for i,plane in enumerate(planes):
        normal=np.asarray(plane['normal'])@basis
        coefficients=[normal[0],normal[2],plane['offset']+normal[1]*floor]
        if np.array_equal(coefficients,segment['plane_line']):matches.append((i,plane,normal))
    if len(matches)!=1:raise ValueError('Source fitted-plane identity is not unique/exact')
    i,plane,normal=matches[0]
    return dict(network_index=index,segment=segment,plane_index=i,plane=plane,
        aligned_plane_normal=normal.tolist(),aligned_plane_offset=plane['offset'],
        footprint_line_uses_fitted_inclination=bool(segment['plane_line_resolved']))


def run(original,controlled,current,source,out):
    original,controlled,current,source,out=map(lambda p:Path(p).resolve(),
        (original,controlled,current,source,out))
    if out.exists() or any(out==p or p in out.parents or out in p.parents
                            for p in (original,controlled,current,source)):
        raise ValueError('Use a fresh output separate from source artifacts')
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    old_plan=read(original/'plan.json');current_plan=read(current/'plan.json')
    old_meta=read(original/'artifacts/layout_evidence.json')
    new_meta=read(controlled/'layout_evidence.json')
    comparison=read(controlled/'comparison.json')
    if not comparison['controls_verified']:raise ValueError('Prior frozen control did not pass')
    changed=[r for r in comparison['observed_cell_shape_changes'] if not r['exact_corners_retained']]
    if len(changed)!=1:raise ValueError('Expected the single historical changed polygon')
    change=changed[0]
    before=next(r for r in old_plan['rooms'] if r['id']==change['source_room_id'])
    after=next(r for r in current_plan['rooms'] if r['id']==change['candidate_cell_id'])
    p,q=Polygon(before['corners']),Polygon(after['corners'])
    if p.area!=change['before_area_m2'] or q.area!=change['after_area_m2']:
        raise ValueError('Current output does not match historical frozen polygon')
    if old_meta['basis_columns_in_input']!=new_meta['basis_columns_in_input']:
        raise ValueError('Historical comparison used different floor bases')
    if old_meta['wall_sampling_slab_bound_m']!=new_meta['wall_sampling_slab_bound_m']:
        raise ValueError('Historical comparison used different floor data')
    basis=np.asarray(old_meta['basis_columns_in_input']);floor=old_meta['wall_sampling_slab_bound_m']
    ledger=read(original/'run.json');summary=read(original/'artifacts/rgbd_summary.json')
    sequence=read(original/'normalized_sequence.json');trajectory=read(original/'artifacts/trajectory.json')
    matrices={r['frame_id']:np.asarray(r['camera_to_first']) for r in trajectory}
    paths=[original/'run.json',original/'plan.json',original/'normalized_sequence.json',
        controlled/'comparison.json',controlled/'layout_evidence.json',current/'plan.json']
    paths += [original/n for n in ledger['geometry_artifact_sha256']]
    paths += [Path('floorplan')/n for n in ledger['code_sha256'] if (Path('floorplan')/n).is_file()]
    frozen={str(path):sha256(path) for path in paths}
    if any(sha256(original/n)!=h for n,h in ledger['geometry_artifact_sha256'].items()):
        raise ValueError('Historical cloud/trajectory artifacts changed')
    with (source/'odometry.csv').open(newline='',encoding='utf-8') as stream:
        odometry=list(csv.DictReader(stream,skipinitialspace=True))
    video=cv2.VideoCapture(str(source/'rgb.mp4'))
    rgb_width,rgb_height=video.get(cv2.CAP_PROP_FRAME_WIDTH),video.get(cv2.CAP_PROP_FRAME_HEIGHT)
    video.release()
    if min(rgb_width,rgb_height)<=0:raise ValueError('Missing original RGB calibration dimensions')
    region,edges=changed_edges(p,q)
    for index,edge in enumerate(edges):
        edge['id']=f"{edge['kind']}_{index}"
        meta=old_meta if edge['kind']=='original' else new_meta
        planes=summary['planes']+meta.get('wall_seed_planes',[])+meta['wall_plane_proposals']
        edge['provenance']=associate(edge['endpoints'],meta,planes,basis,floor)
    cloud=np.load(original/'artifacts/cloud.npz')['points'];aligned=cloud@basis
    for edge in edges:
        ev=edge['provenance'];n=np.asarray(ev['aligned_plane_normal']);d=ev['aligned_plane_offset']
        edge['fused_local_support']=support_profile(aligned,n,d,edge['endpoints'],floor)
    rows=[];sampled=[];weights=[];colors=[];sensor_hashes={}
    for frame in sequence['frames']:
        fid=frame['id']
        if fid not in matrices:raise ValueError('Missing retained refined pose')
        raw_dp=source/'depth'/f'{fid:06d}.png';raw_cp=source/'confidence'/f'{fid:06d}.png'
        for src,copy in ((raw_dp,Path(frame['depth'])),(raw_cp,Path(frame['confidence']))):
            if sha256(src)!=sha256(copy):raise ValueError('Sensor extraction differs from original')
            sensor_hashes[str(src)]=sha256(src)
        raw=cv2.imread(str(raw_dp),cv2.IMREAD_UNCHANGED)
        confidence=cv2.imread(str(raw_cp),cv2.IMREAD_UNCHANGED)
        camera=frame['intrinsics'];sensor=odometry[fid]
        sx,sy=raw.shape[1]/rgb_width,raw.shape[0]/rgb_height
        expected=dict(fx=float(sensor['fx'])*sx,fy=float(sensor['fy'])*sy,
                      cx=float(sensor['cx'])*sx,cy=float(sensor['cy'])*sy)
        if any(camera[k]!=v for k,v in expected.items()):raise ValueError('Original per-frame calibration differs')
        quaternion=np.array([float(sensor[k]) for k in ('qx','qy','qz','qw')])
        raw_pose=np.eye(4);raw_pose[:3,:3]=Rotation.from_quat(quaternion/np.linalg.norm(quaternion)).as_matrix()
        raw_pose[:3,3]=[float(sensor[k]) for k in ('x','y','z')]
        if not np.array_equal(raw_pose,frame['camera_to_world']):raise ValueError('Original sensor pose differs')
        depth=raw.astype(float)/sequence['depth_scale']
        yy,xx=np.indices(raw.shape);pixels=np.column_stack((xx.ravel(),yy.ravel()));z=depth.ravel()
        valid=np.isfinite(z)&(z>=.2)&(z<=sequence.get('depth_max_m',8.))
        accepted=valid&(confidence.ravel()>=sequence.get('minimum_confidence',1))
        pose=matrices[fid]
        k=np.array([[camera['fx'],0,camera['cx']],[0,camera['fy'],camera['cy']],[0,0,1.]])
        xyz=_backproject(pixels[accepted],z[accepted],k);conf=confidence.ravel()[accepted]
        stride=(pixels[accepted,0]%8==0)&(pixels[accepted,1]%8==0)
        world=xyz@pose[:3,:3].T+pose[:3,3]
        sampled.append(world[stride]);weights.append((conf[stride].astype(float)+1)/np.maximum(z[accepted][stride],.5)**2)
        rgb=cv2.imread(str(frame['rgb']));uv=pixels[accepted][stride]
        colors.append(rgb[uv[:,1],uv[:,0],::-1])
        row=dict(frame_id=fid,depth_shape=list(raw.shape),accepted_depth_pixels=len(xyz),edges={})
        for mode,transform in (('refined',pose),('raw',raw_pose)):
            points=(xyz@transform[:3,:3].T+transform[:3,3])@basis
            center=transform[:3,3]@basis
            for edge in edges:
                ev=edge['provenance'];n=np.asarray(ev['aligned_plane_normal']);d=ev['aligned_plane_offset']
                local=finite_mask(points,n,d,edge['endpoints'],floor)
                crossed,hits=crossing_rays(center,points,n,d,edge['endpoints'],floor)
                value=dict(support_pixels=int(local.sum()),confidence2_support_pixels=int((local&(conf==2)).sum()),
                    stride8_support_pixels=int((local&stride).sum()),heldout_support_pixels=int((local&~stride).sum()),
                    support_height_histogram=np.histogram(floor-points[local,1],HEIGHT_BINS)[0].tolist(),
                    crossing_rays=int(crossed.sum()),confidence2_crossing_rays=int((crossed&(conf==2)).sum()),
                    crossing_height_histogram=np.histogram(floor-hits[:,1],HEIGHT_BINS)[0].tolist(),
                    confidence2_crossing_height_histogram=np.histogram(floor-hits[conf[crossed]==2,1],HEIGHT_BINS)[0].tolist())
                row['edges'].setdefault(edge['id'],{})[mode]=value
        rows.append(row)
    replay,_,_=weighted_voxels(np.concatenate(sampled),np.concatenate(colors),np.concatenate(weights))
    if not np.array_equal(replay,cloud):raise ValueError('Original sensor fusion does not reproduce frozen cloud')
    aggregates={}
    for edge in edges:
        aggregates[edge['id']]={}
        for mode in ('refined','raw'):
            values=[r['edges'][edge['id']][mode] for r in rows]
            scalar=('support_pixels','confidence2_support_pixels','stride8_support_pixels','heldout_support_pixels',
                    'crossing_rays','confidence2_crossing_rays')
            result={k:sum(v[k] for v in values) for k in scalar}
            for name in ('support_height_histogram','crossing_height_histogram','confidence2_crossing_height_histogram'):
                result[name]=np.sum([v[name] for v in values],axis=0).tolist()
            result['support_frame_ids']=[r['frame_id'] for r in rows if r['edges'][edge['id']][mode]['support_pixels']]
            result['crossing_frame_ids']=[r['frame_id'] for r in rows if r['edges'][edge['id']][mode]['crossing_rays']]
            aggregates[edge['id']][mode]=result
    out.mkdir(parents=True)
    sensor_hashes[str(source/'odometry.csv')]=sha256(source/'odometry.csv')
    sensor_hashes[str(source/'rgb.mp4')]=sha256(source/'rgb.mp4')
    if any(sha256(path)!=h for path,h in {**frozen,**sensor_hashes}.items()):raise ValueError('Evidence changed during audit')
    result=dict(experiment='ceiling_scan_footprint_notch_sensor_audit',original=str(original),controlled=str(controlled),
        current=str(current),source=str(source),frames=len(rows),height_bins_m=HEIGHT_BINS.tolist(),
        before_area_m2=p.area,after_area_m2=q.area,removed_area_m2=region.area,
        reported_historical_hausdorff_m=change['boundary_hausdorff_change_m'],
        recomputed_polygon_hausdorff_m=p.hausdorff_distance(q),boundary_hausdorff_m=p.boundary.hausdorff_distance(q.boundary),
        ceiling_height_before=before['ceiling_height_m'],ceiling_height_after=after['ceiling_height_m'],
        footprint_change_not_ceiling_height_change=True,edges=edges,aggregate_sensor_evidence=aggregates,
        per_frame_evidence=rows,input_sha256=frozen,sensor_sha256=sensor_hashes,script_sha256=sha256(__file__),
        original_pngs_byte_identical=True,original_per_frame_calibration_exact=True,original_sensor_poses_exact=True,
        original_stride8_cloud_reproduced_exact=True,common_frozen_basis_and_floor_exact=True,
        pose_estimation_optimization_rerun=False,production_changed=False,accuracy_validated=False,acceptance_claimed=False,
        limitations=['Ray evidence conditional on supplied raw/refined poses and intrinsics',
            'Held-out pixels share the supplied sensor and poses; not independent survey truth',
            'Counts are repeated unfused observations, not independent measurements',
            '35mm support band and 10cm ray clearance are diagnostics, not accuracy tolerances'])
    (out/'audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('frames','before_area_m2','after_area_m2','removed_area_m2',
        'recomputed_polygon_hausdorff_m','boundary_hausdorff_m','ceiling_height_before','ceiling_height_after',
        'original_stride8_cloud_reproduced_exact','aggregate_sensor_evidence')},indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original',default='demo/phase3_partial_cells/current/ceiling')
    parser.add_argument('--controlled',default='demo/phase3_floor_audit/current_residual/ceiling_controlled/comparison')
    parser.add_argument('--current',default='demo/phase3_strip_trace/current_exterior/ceiling')
    parser.add_argument('--source',default='datasets/Given_dataset/single_scan_with_ceiling/c7d28f72c6')
    parser.add_argument('--out',required=True)
    args=parser.parse_args();run(args.original,args.controlled,args.current,args.source,args.out)
