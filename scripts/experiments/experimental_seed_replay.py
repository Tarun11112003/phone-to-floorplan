"""Frozen-cloud original-seed/residual-consensus trial; no production edits."""
import argparse
import inspect
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from shapely.geometry import Polygon
import floorplan.layout as layout
from floorplan.provenance import sha256


def seed_replay_callable(unvisited_only=False,exterior_only=False):
    original=layout._supported_wall_proposals
    source=inspect.getsource(layout._projection_wall_proposals)
    if 'seed_points=None' in source:
        raise ValueError('Preload the retained pre-fix source package for this baseline experiment')
    source=source.replace('accepted_limit=12):', 'accepted_limit=12, seed_points=None):')
    source=source.replace('lo,hi=float(values.min()),float(values.max())',
        'seed_aligned=seed_points@basis\n'
        '        seed_band=seed_points[(seed_aligned[:,1]<floor-.25)&(seed_aligned[:,1]>floor-3.)]\n'
        '        seed_values=seed_band@direction\n'
        '        lo,hi=float(seed_values.min()),float(seed_values.max())')
    source=source.replace('np.histogram(values,edges)', 'np.histogram(seed_values,edges)')
    def candidate(points,planes,basis,floor,*,support_policy='local_spatial'):
        visited={0:[],2:[]}
        function=layout._projection_wall_proposals
        lines,start=inspect.getsourcelines(function)
        seed_line=start+next(i for i,line in enumerate(lines) if 'location=float((edges[index]' in line)
        def trace(frame,event,arg):
            if frame.f_code is function.__code__ and event=='line' and frame.f_lineno==seed_line and frame.f_locals['accepted_limit']==12:
                local=frame.f_locals
                visited[local['axis']].append(float((local['edges'][local['index']]+local['edges'][local['index']+1])/2))
            return trace
        previous=sys.gettrace();sys.settrace(trace)
        try:current=original(points,planes,basis,floor,support_policy=support_policy)
        finally:sys.settrace(previous)
        if support_policy!='local_spatial':return current
        initial=layout._projection_wall_proposals(points,planes,basis,floor,support_policy=support_policy)
        if not any(sum(abs(np.asarray(p['normal'])@basis[:,axis])>=np.cos(np.deg2rad(8)) for p in initial)>=12 for axis in (0,2)):return current
        remaining=np.ones(len(points),bool)
        for p in planes+initial:
            remaining &=np.abs(points@np.asarray(p['normal'])+p['offset'])>=.035
        extras=[]
        for axis in (0,2):
            count=sum(abs(np.asarray(p['normal'])@basis[:,axis])>=np.cos(np.deg2rad(8))
                      for p in current[len(initial):])
            quota=8-count
            if quota<=0:continue
            represented=[float(np.asarray(p['centroid'])@basis[:,axis]) for p in planes+current
                         if abs(np.asarray(p['normal'])@basis[:,axis])>=np.cos(np.deg2rad(8))]
            namespace=dict(vars(layout),visited=visited,represented=represented)
            axis_source=source.replace('for axis in (0,2):', f'for axis in ({axis},):')
            if unvisited_only:
                needle='location=float((edges[index]+edges[index+1])/2)'
                axis_source=axis_source.replace(needle,needle+'\n            if any(abs(location-p)<.05 for p in visited[axis]): continue')
            if exterior_only:
                needle='location=float((edges[index]+edges[index+1])/2)'
                axis_source=axis_source.replace(needle,needle+'\n            if represented and min(represented)-.05<=location<=max(represented)+.05: continue')
            exec(compile(axis_source,'<original-seed-residual-consensus>','exec'),namespace)
            extra=namespace['_projection_wall_proposals'](points[remaining],planes+current+extras,basis,floor,
                support_policy=support_policy,accepted_limit=quota,seed_points=points)
            fraction=min(18000,len(points))/len(points)
            for p in extra:
                p['support']=int(p['raw_support_points']*fraction)
                p['proposal_source']='wall projection mode; original seed with unexplained raw 3D plane consensus'
            extras.extend(extra)
        return current+extras
    return candidate


def trial(run,out,unvisited_only=False,exterior_only=False):
    run,out=Path(run).resolve(),Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    read=lambda n:json.loads((run/n).read_text(encoding='utf-8'))
    ledger=read('run.json');source=read('artifacts/layout_evidence.json');old=read('plan.json')
    cloud=np.load(run/'artifacts/cloud.npz')['points'];summary=read('artifacts/rgbd_summary.json')
    poses=np.asarray([p['camera_to_first'] for p in read('artifacts/trajectory.json')])
    code=sha256(Path(layout.__file__));original=layout._supported_wall_proposals
    layout._supported_wall_proposals=seed_replay_callable(unvisited_only,exterior_only)
    try:
        rooms,meta=layout.extract_layout(cloud,summary['planes'],poses[:,:3,3],
            ledger['configuration'].get('down_direction',poses[0,:3,1]),path_breaks=source.get('path_breaks',()))
    finally:layout._supported_wall_proposals=original
    rooms,meta=json.loads(json.dumps([rooms,meta]))
    checks=dict(production_unchanged=code==sha256(Path(layout.__file__)),
        prior_proposal_prefix_exact=meta['wall_plane_proposals'][:len(source['wall_plane_proposals'])]==source['wall_plane_proposals'])
    changes=[]
    for room in old['rooms']:
        if room.get('requires_boundary_review'):continue
        p=Polygon(room['corners']);best=max(rooms,key=lambda r:p.intersection(Polygon(r['corners'])).area);q=Polygon(best['corners'])
        changes.append(dict(room_id=room['id'],candidate_id=best['id'],exact=room['corners']==best['corners'],
            retained_area_fraction=p.intersection(q).area/p.area,boundary_hausdorff_change_m=p.hausdorff_distance(q)))
    def metrics(m):return dict(stages=m['boundary_stages'],coverage=m['camera_center_coverage_fraction'],connections=len(m['connections']),partial=m['unclosed_geometry'])
    result=dict(experiment='original_seed_residual_consensus',unvisited_only=unvisited_only,exterior_only=exterior_only,checks=checks,before=metrics(source),after=metrics(meta),
                observed_shape_changes=changes,additional_proposals=meta['wall_plane_proposals'][len(source['wall_plane_proposals']):],
                source_layout_sha256=code,script_sha256=sha256(Path(__file__)),accuracy_improvement=None,
                input_sha256={n:sha256(run/n) for n in ['run.json','plan.json','artifacts/cloud.npz','artifacts/layout_evidence.json']})
    (out/'trial.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (out/'layout_evidence.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    (out/'rooms.json').write_text(json.dumps(rooms,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--unvisited-only',action='store_true');parser.add_argument('--exterior-only',action='store_true');args=parser.parse_args()
    r=trial(args.run,args.out,args.unvisited_only,args.exterior_only);print(json.dumps({k:v for k,v in r.items() if k not in ('input_sha256','additional_proposals')},indent=2))
