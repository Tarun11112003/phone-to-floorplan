"""Compare local observed-wall patches with the existing frozen plane proposals.

Development-only: camera coverage is not surveyed accuracy or room identity.
No survey dimensions, rectangles, depth bias or closing dilation are supplied.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.layout import floor_basis, extract_layout, export_layout
from floorplan.provenance import sha256


def patches(points, basis, floor, *, local_support=False):
    import open3d as o3d
    aligned=points@basis
    band=points[(aligned[:,1]<floor-.25)&(aligned[:,1]>floor-3)]
    cloud=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(band))
    cloud.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=.12,max_nn=30))
    boxes=cloud.detect_planar_patches(normal_variance_threshold_deg=30,
        coplanarity_deg=75,outlier_ratio=.25,min_plane_edge_length=.6,
        min_num_points=250,search_param=o3d.geometry.KDTreeSearchParamKNN(knn=30))
    scale=min(18000,len(points))/len(points)
    acceptance_scale=1. if local_support else scale
    accepted=[]; reasons={}
    for box in boxes:
        support=band[box.get_point_indices_within_bounding_box(cloud.points)]
        reason=None
        if len(support)*acceptance_scale<250: reason='insufficient_global_equivalent_support'
        else:
            center=support.mean(axis=0); _,_,vt=np.linalg.svd(support-center,full_matrices=False)
            normal=vt[-1]; offset=-float(normal@center)
            support=support[np.abs(support@normal+offset)<.025]
            if len(support)*acceptance_scale<250: reason='insufficient_plane_consensus'
            else:
                center=support.mean(axis=0); _,_,vt=np.linalg.svd(support-center,full_matrices=False)
                normal=vt[-1]; offset=-float(normal@center)
                rms=float(np.sqrt(np.mean((support@normal+offset)**2)))
                height=float(np.ptp(np.quantile(support@basis[:,1],[.05,.95])))
                tangent=np.cross(basis[:,1],normal)
                if np.linalg.norm(tangent)<1e-8: reason='horizontal'
                else:
                    tangent/=np.linalg.norm(tangent)
                    length=float(np.ptp(np.quantile(support@tangent,[.05,.95])))
                    if abs(normal@basis[:,1])>.15: reason='not_vertical'
                    elif max(abs(normal@basis[:,0]),abs(normal@basis[:,2]))<np.cos(np.deg2rad(8)): reason='outside_supported_axes'
                    elif rms>.025: reason='plane_residual'
                    elif height<.9 or length<.6: reason='insufficient_extent'
                    else:
                        cells=np.floor(np.column_stack([support@tangent,support@basis[:,1]])/.10).astype(int)
                        occupied=len(np.unique(cells,axis=0))
                        if local_support and occupied<40:
                            reasons['insufficient_spatial_support']=reasons.get('insufficient_spatial_support',0)+1
                            continue
                        accepted.append(dict(normal=normal.tolist(),offset=offset,
                            support=int(len(support)*scale),raw_support_points=len(support),
                            centroid=center.tolist(),rms_m=rms,
                            observed_height_span_m=height,observed_length_span_m=length,
                            support_basis='global sample equivalent; local spatial acceptance' if local_support else 'global sample equivalent',
                            occupied_10cm_cells=occupied,
                            proposal_source='Open3D local planar patch; observed raw consensus'))
        if reason: reasons[reason]=reasons.get(reason,0)+1
    return accepted,dict(proposed=len(boxes),accepted=len(accepted),rejected=reasons)


def compare(run, output):
    run,output=Path(run).resolve(),Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    artifacts=run/'artifacts'
    points=np.load(artifacts/'cloud.npz')['points'].astype(float)
    frozen=json.loads((artifacts/'rgbd_summary.json').read_text())
    ledger=json.loads((run/'run.json').read_text())
    trajectory=json.loads((artifacts/'trajectory.json').read_text())
    centers=np.asarray([p['camera_to_first'] for p in trajectory])[:,:3,3]
    metadata=json.loads((artifacts/'layout_evidence.json').read_text())
    down=ledger['configuration'].get('down_direction')
    if down is None: down=np.asarray(trajectory[0]['camera_to_first'])[:3,1]
    planes=frozen['planes']; start=time.perf_counter()
    _,_,basis,floor,_=floor_basis(points,planes,centers,down)
    additions,diagnostics=patches(points,basis,floor)
    local_additions,local_diagnostics=patches(points,basis,floor,local_support=True)
    rows=[]
    for name,candidates in [('baseline',planes),('local_patches',planes+additions),
                            ('local_spatial_support',planes+local_additions)]:
        begun=time.perf_counter()
        rooms,evidence=extract_layout(points,candidates,centers,down,path_breaks=metadata.get('path_breaks',()))
        directory=output/name; directory.mkdir()
        (directory/'layout_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        if rooms: export_layout(rooms,evidence,directory,complete_capture=False)
        rows.append(dict(method=name,rooms=len(rooms),coverage=evidence['camera_center_coverage_fraction'],
            unclosed=evidence['unclosed_geometry'],stages=evidence['boundary_stages'],
            runtime_s=time.perf_counter()-begun))
    result=dict(experiment='observed_local_plane_proposals',source_run=str(run),
        input_sha256={p.name:sha256(p) for p in [run/'run.json',artifacts/'cloud.npz',artifacts/'trajectory.json']},
        script_sha256=sha256(Path(__file__)),layout_source_sha256=sha256(Path(__file__).parents[1]/'floorplan/layout.py'),
        patch_diagnostics=diagnostics,local_support_diagnostics=local_diagnostics,
        added_planes=additions,local_support_planes=local_additions,comparisons=rows,
        runtime_s=time.perf_counter()-start,accuracy_validated=False,production_adopted=False,
        limitations=['No independent wall semantics, topology or physical dimensions',
                    'Both methods retain existing finite-boundary and partial-status guards'])
    (output/'comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'added_planes','local_support_planes','input_sha256'}},indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();compare(args.run,args.out)
