"""Audit frozen uncovered samples and omitted wall support; no reconstruction edits."""
from __future__ import annotations

import argparse
from collections import Counter
import inspect
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from shapely.geometry import LineString,Point,Polygon
import floorplan.layout as layout
from floorplan.provenance import sha256


def enclosure(lines):
    """Four directional hits are not necessarily four incident finite walls."""
    corners=[]; missing=[]
    for i,j in ((0,2),(0,3),(1,3),(1,2)):
        a,b=map(lambda line:np.asarray(line.coords,float),(lines[i],lines[j]))
        da,db=a[1]-a[0],b[1]-b[0];la,lb=np.linalg.norm(da),np.linalg.norm(db)
        if min(la,lb)<1e-8: return dict(classification='degenerate_directional_hits')
        ua,ub=da/la,db/lb
        if abs(np.linalg.det(np.column_stack([ua,ub])))<.2:
            return dict(classification='degenerate_directional_hits')
        t,s=np.linalg.solve(np.column_stack([ua,-ub]),b[0]-a[0])
        missing.append(float(max(0,-t,t-la,-s,s-lb)))
        corners.append((a[0]+t*ua).tolist())
    poly=Polygon(corners)
    if max(missing)>.15:
        classification='finite_extents_do_not_support_bounded_enclosure'
    elif poly.area<1:
        classification='bounded_enclosure_below_existing_area_guard'
    else:
        classification='bounded_enclosure_needs_junction_investigation'
    return dict(classification=classification,corner_missing_extent_m=missing,
                infinite_line_enclosure_area_m2=float(poly.area),corners=corners)


def fit_omitted_seed(band,direction,vertical,location,known_planes):
    """Check the production support guards, without emitting walls or rooms."""
    subset=band[np.abs(band@direction-location)<.035]
    for _ in range(3):
        center=subset.mean(axis=0);_,_,vt=np.linalg.svd(subset-center,full_matrices=False)
        normal=vt[-1];offset=-float(normal@center)
        subset=band[np.abs(band@normal+offset)<.025]
        if len(subset)<250: return dict(passes_existing_guards=False,reason='raw_points')
    center=subset.mean(axis=0);_,singular,vt=np.linalg.svd(subset-center,full_matrices=False)
    normal=vt[-1];offset=-float(normal@center)
    tangent=np.cross(vertical,normal);tangent/=np.linalg.norm(tangent)
    rms=float(np.sqrt(np.mean((subset@normal+offset)**2)))
    height=float(np.ptp(np.quantile(subset@vertical,[.05,.95])))
    length=float(np.ptp(np.quantile(subset@tangent,[.05,.95])))
    cells=len(np.unique(np.floor(np.column_stack([subset@tangent,subset@vertical])/.10).astype(np.int64),axis=0))
    duplicate=any(abs(np.asarray(p['normal'])@normal)>.998
                  and abs(np.asarray(p['centroid'])@normal+offset)<.02 for p in known_planes)
    guards=dict(raw_points=len(subset)>=250,two_dimensional=singular[1]>=1e-8,
        plane_residual=rms<=.025,vertical=abs(normal@vertical)<=.15,
        axis_alignment=abs(normal@direction)>=np.cos(np.deg2rad(8)),
        height_span=height>=.9,length_span=length>=.6,occupied_cells=cells>=40,
        novel_plane=not duplicate)
    guards={key:bool(value) for key,value in guards.items()}
    return dict(passes_existing_guards=all(guards.values()),guards=guards,
        raw_support_points=len(subset),rms_m=rms,height_span_m=height,
        length_span_m=length,occupied_10cm_cells=cells,normal=normal.tolist(),
        offset=offset,centroid=center.tolist(),supporting_plane_only=True)


def audit(run,out):
    run,out=Path(run).resolve(),Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    read=lambda name:json.loads((run/name).read_text(encoding='utf-8'))
    ledger=read('run.json');meta=read('artifacts/layout_evidence.json');plan=read('plan.json')
    artifact_paths=['artifacts/'+n for n in ('cloud.npz','trajectory.json','rgbd_summary.json','layout_evidence.json')]
    if not all(ledger['geometry_artifact_sha256'].get(n)==sha256(run/n) for n in artifact_paths):
        raise ValueError('Frozen source artifacts do not match their original hashes')
    code_before=sha256(Path(layout.__file__))
    if ledger['code_sha256']['layout.py']!=code_before:
        raise ValueError('Audit requires the unchanged baseline layout producer')
    cloud=np.load(run/'artifacts/cloud.npz')['points'];basis=np.asarray(meta['basis_columns_in_input'])
    aligned=cloud@basis;floor=meta['wall_sampling_slab_bound_m']
    path=np.asarray(meta['camera_path_2d']);trajectory=read('artifacts/trajectory.json')
    polygons=[Polygon(r['corners']) for r in plan['rooms']]
    observed=[Polygon(r['corners']) for r in plan['rooms'] if not r.get('requires_boundary_review')]
    lines=[layout._line(s) for s in meta['wall_segments']]
    covered=np.asarray([any(p.buffer(.10).covers(Point(c)) for p in polygons) for c in path])
    # Ray length encloses the actual observed network; it is an audit query,
    # never a proposed wall extent or a relaxed room-join bound.
    ends=np.asarray([p for line in lines for p in line.coords])
    ray_length=float(np.linalg.norm(np.ptp(np.vstack([ends,path]),axis=0))+1)
    rows=[]
    for i in np.flatnonzero(~covered):
        c=path[i];hits=[]
        for direction in ((1,0),(-1,0),(0,1),(0,-1)):
            ray=LineString([c,c+np.asarray(direction)*ray_length])
            intersections=[(Point(c).distance(ray.intersection(line)),j)
                           for j,line in enumerate(lines) if ray.intersects(line)]
            hits.append(min(intersections)[1] if intersections else None)
        detail=(enclosure([lines[j] for j in hits]) if None not in hits else
                dict(classification='incomplete_extracted_directional_support'))
        rows.append(dict(camera_sample_index=int(i),source_frame_id=trajectory[i]['frame_id'],
            camera_xz_m=c.tolist(),directional_wall_ids=hits,**detail))
    # Trace actual baseline seed visits, rather than guessing from histogram rank.
    attempted={0:[],2:[]};original=layout._supported_wall_proposals
    seed_function=getattr(layout,'_projection_wall_proposals',original)
    source,start=inspect.getsourcelines(seed_function)
    seed_line=start+next(i for i,s in enumerate(source) if 'location=float((edges[index]' in s)
    def trace(frame,event,arg):
        if (frame.f_code is seed_function.__code__ and event=='line' and frame.f_lineno==seed_line
                and frame.f_locals.get('accepted_limit',12)==12):
            attempted[frame.f_locals['axis']].append(int(frame.f_locals['index']))
        return trace
    planes=read('artifacts/rgbd_summary.json')['planes']+meta.get('wall_seed_planes',[])
    previous=sys.gettrace();sys.settrace(trace)
    try: proposals=original(cloud,planes,basis,floor)
    finally: sys.settrace(previous)
    if json.loads(json.dumps(proposals))!=meta['wall_plane_proposals']:
        raise ValueError('Baseline proposal replay differs from frozen evidence')
    band=cloud[(aligned[:,1]<floor-.25)&(aligned[:,1]>floor-3)]
    seeds=[];axes=[]
    for axis in (0,2):
        direction=basis[:,axis];values=band@direction
        edges=np.arange(np.floor(values.min()/.025)*.025-.05,values.max()+.075,.025)
        counts,_=np.histogram(values,edges)
        maxima=[i for i in range(1,len(counts)-1) if counts[i]>=250 and counts[i]>=counts[i-1] and counts[i]>=counts[i+1]]
        ranked=sorted(maxima,key=lambda i:(-int(counts[i]),i))[:48]
        axes.append(dict(axis=axis,eligible_seed_modes=len(maxima),attempted_seed_modes=len(attempted[axis]),
                         accepted_proposals=int(sum(abs(np.asarray(p['normal'])@direction)>=np.cos(np.deg2rad(8))
                            for p in proposals if p.get('proposal_source')=='wall projection mode; raw 3D plane consensus'))))
        for rank,index in enumerate(ranked,1):
            if index in attempted[axis]:continue
            location=float((edges[index]+edges[index+1])/2)
            fitted=fit_omitted_seed(band,direction,basis[:,1],location,planes+proposals)
            seeds.append(dict(axis=axis,rank=rank,bin_points=int(counts[index]),seed_location_m=location,
                              omitted_by_baseline_seed_visit=True,**fitted))
    summary=dict(experiment='frozen_floor_boundary_audit',run=str(run),
        input_sha256={n:sha256(run/n) for n in ['run.json','plan.json']+artifact_paths},
        script_sha256=sha256(Path(__file__)),layout_sha256=code_before,
        reconstruction_logic_unchanged=code_before==sha256(Path(layout.__file__)),
        camera_samples=len(path),covered_samples=int(covered.sum()),uncovered_samples=len(rows),
        sample_classifications=dict(Counter(r['classification'] for r in rows)),
        uncovered_camera_samples=rows,seed_search=axes,omitted_seed_audits=seeds,
        omitted_seeds_passing_all_existing_guards=sum(s['passes_existing_guards'] for s in seeds),
        accuracy_validated=False,limitations=[
            'No extracted directional wall hit does not prove the raw capture lacked observations',
            'Directional enclosures can cross different rooms and are diagnostic only',
            'Passing plane guards is observed surface support, not semantic wall or room ground truth',
            'No independent survey or centimetre-accuracy evidence'])
    (out/'audit.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,10))
    for line in lines:
        q=np.asarray(line.coords);ax.plot(q[:,0],q[:,1],color='gray',lw=1)
    ax.scatter(path[covered,0],path[covered,1],c='green',label='covered',s=15)
    ax.scatter(path[~covered,0],path[~covered,1],c='red',label='uncovered',s=15)
    for i,c in enumerate(path):
        if not covered[i] and i%5==0:ax.text(*c,str(i),fontsize=7)
    for poly in polygons:
        q=np.asarray(poly.exterior.coords);ax.plot(q[:,0],q[:,1],color='green',lw=2)
    ax.set_aspect('equal');ax.set(title='Frozen audit: 151 uncovered samples; no survey truth',xlabel='x (m)',ylabel='z (m)');ax.legend()
    fig.savefig(out/'uncovered_samples.png',dpi=140);plt.close(fig)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();result=audit(args.run,args.out)
    print(json.dumps({k:v for k,v in result.items() if k not in ('uncovered_camera_samples','omitted_seed_audits','input_sha256')},indent=2))
