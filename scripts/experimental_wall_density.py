"""Frozen-cloud comparison of height-band line proposals with raw 3D validation.

Evaluates density/Hough proposals; never exports raster-filled room dimensions.
All development thresholds are disclosed and are not assessment accuracy gates.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from floorplan.layout import floor_basis,extract_layout,export_layout
from floorplan.provenance import sha256


def wall_proposals(points,basis,floor, *, seed_mode='density'):
    aligned=points@basis
    band=aligned[(floor-aligned[:,1]>.4)&(floor-aligned[:,1]<1.9)]
    if len(band)<250: return [],{'reason':'insufficient_band'}
    cell=.02
    origin=band[:,[0,2]].min(axis=0)-.04
    indices=np.floor((band[:,[0,2]]-origin)/cell).astype(int)
    size=indices.max(axis=0)+3
    if np.prod(size)>4000000: return [],{'reason':'bounded_raster_size'}
    grid=np.bincount(indices[:,1]*size[0]+indices[:,0],minlength=int(np.prod(size))).reshape(size[::-1])
    threshold=max(3.,float(np.percentile(grid[grid>0],92)))
    mask=(grid>=threshold).astype(np.uint8)
    # Unlike a room fill, these lines merely propose where raw points are checked.
    lines=cv2.HoughLinesP(mask*255,1,np.pi/360,threshold=25,
                         minLineLength=30,maxLineGap=5)
    lines=[] if lines is None else np.asarray(lines).reshape(-1,4)
    if seed_mode=='projection':
        lines=[]
        for component in (0,2):
            values=band[:,component]
            edges=np.arange(np.floor(values.min()/.025)*.025-.05,values.max()+.075,.025)
            counts,_=np.histogram(values,edges)
            peaks=[i for i in range(1,len(counts)-1) if counts[i]>=250 and counts[i]>=counts[i-1] and counts[i]>=counts[i+1]]
            chosen=[]
            for i in sorted(peaks,key=lambda i:-counts[i])[:24]:
                location=(edges[i]+edges[i+1])/2
                if any(abs(location-old)<.05 for old in chosen): continue
                chosen.append(location)
                seed=band[np.abs(values-location)<.035]
                lo,hi=np.quantile(seed[:,2-component],[.002,.998])
                pair=np.array([[location,lo],[location,hi]]) if component==0 else np.array([[lo,location],[hi,location]])
                lines.append(((pair-origin)/cell-.5).ravel())
    scale=min(18000,len(points))/len(points)
    proposals=[]; reasons={}
    for line in sorted(lines,key=lambda l:-float(np.linalg.norm(l[2:]-l[:2])))[:100]:
        a,b=(line.reshape(2,2)+.5)*cell+origin
        tangent=b-a; length=np.linalg.norm(tangent); tangent/=length
        normal=np.array([tangent[1],-tangent[0]])
        local=band[:,[0,2]]-a
        seed=band[(np.abs(local@normal)<.05)&(local@tangent>-.1)&(local@tangent<length+.1)]
        reason=None
        if len(seed)<250: reason='insufficient_raw_support'
        else:
            center=seed.mean(axis=0); _,_,vt=np.linalg.svd(seed-center,full_matrices=False)
            n=vt[-1]; offset=-float(n@center)
            support=seed[np.abs(seed@n+offset)<.025]
            if len(support)<250: reason='insufficient_consensus'
            else:
                center=support.mean(axis=0); _,s,vt=np.linalg.svd(support-center,full_matrices=False)
                n=vt[-1]; offset=-float(n@center)
                horizontal=np.cross([0,1,0],n); norm=np.linalg.norm(horizontal)
                if norm<1e-8 or abs(n[1])>.15: reason='not_vertical'
                elif max(abs(n[0]),abs(n[2]))<np.cos(np.deg2rad(8)): reason='unsupported_orientation'
                else:
                    horizontal/=norm
                    span=float(np.ptp(np.quantile(support@horizontal,[.05,.95])))
                    height=float(np.ptp(np.quantile(support[:,1],[.05,.95])))
                    rms=float(np.sqrt(np.mean((support@n+offset)**2)))
                    occupied=len(np.unique(np.floor(np.column_stack([support@horizontal,support[:,1]])/.1).astype(int),axis=0))
                    world_normal=basis@n; world_center=basis@center
                    if height<.9 or span<.6 or occupied<40 or s[1]<1e-8: reason='insufficient_spatial_extent'
                    elif rms>.025: reason='residual'
                    elif any(abs(world_normal@p['normal'])>.998 and abs(world_center@p['normal']+p['offset'])<.03 for p in proposals):
                        reason='duplicate_local_proposal'
                    else:
                        proposals.append(dict(normal=world_normal.tolist(),offset=offset,
                            support=int(len(support)*scale),raw_support_points=len(support),
                            centroid=world_center.tolist(),rms_m=rms,
                            occupied_10cm_cells=occupied,observed_height_span_m=height,
                            observed_length_span_m=span,proposal_source='height-band density line; local raw 3D consensus'))
        if reason: reasons[reason]=reasons.get(reason,0)+1
    return proposals,dict(proposed=len(lines),bounded_fit_budget=100,accepted=len(proposals),
        rejected=reasons,density_threshold=threshold,cell_m=cell,band_m=[.4,1.9],
        minimum_raw_points=250,minimum_10cm_cells=40,minimum_span_m=[.6,.9],
        maximum_residual_m=.025,maximum_line_gap_m=.1,seed_mode=seed_mode)


def compare(run,out,seed_mode='density'):
    run,out=Path(run).resolve(),Path(out).resolve(); out.mkdir(parents=True,exist_ok=False)
    artifacts=run/'artifacts'; points=np.load(artifacts/'cloud.npz')['points'].astype(float)
    planes=json.loads((artifacts/'rgbd_summary.json').read_text())['planes']
    trajectory=json.loads((artifacts/'trajectory.json').read_text())
    centers=np.asarray([p['camera_to_first'] for p in trajectory])[:,:3,3]
    metadata=json.loads((artifacts/'layout_evidence.json').read_text())
    down=json.loads((run/'run.json').read_text())['configuration'].get('down_direction')
    if down is None: down=np.asarray(trajectory[0]['camera_to_first'])[:3,1]
    begun=time.perf_counter(); _,_,basis,floor,_=floor_basis(points,planes,centers,down)
    additions,diagnostics=wall_proposals(points,basis,floor,seed_mode=seed_mode); rows=[]
    for name,candidates in [('baseline',planes),(seed_mode+'_proposals',planes+additions)]:
        started=time.perf_counter(); rooms,evidence=extract_layout(points,candidates,centers,down,path_breaks=metadata.get('path_breaks',()))
        directory=out/name; directory.mkdir()
        (directory/'layout_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        if rooms: export_layout(rooms,evidence,directory,complete_capture=False)
        rows.append(dict(method=name,rooms=len(rooms),coverage=evidence['camera_center_coverage_fraction'],
                         unclosed=evidence['unclosed_geometry'],stages=evidence['boundary_stages'],runtime_s=time.perf_counter()-started))
    result=dict(experiment='height_band_'+seed_mode+'_wall_proposals',diagnostics=diagnostics,added_planes=additions,
        comparisons=rows,runtime_s=time.perf_counter()-begun,accuracy_validated=False,production_adopted=False,
        input_sha256={str(p):sha256(p) for p in [run/'run.json',artifacts/'cloud.npz',artifacts/'trajectory.json']},
        script_sha256=sha256(Path(__file__)),layout_source_sha256=sha256(Path(__file__).parents[1]/'floorplan/layout.py'))
    (out/'comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'added_planes','input_sha256'}},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--seed-mode',choices=['density','projection'],default='density')
    args=parser.parse_args();compare(args.run,args.out,args.seed_mode)
