"""Frozen-cloud seed-budget alternative; production source remains unchanged."""
import argparse
import inspect
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import floorplan.layout as layout
from floorplan.provenance import sha256


def trial(run,out,accepted_cap=20,residual_search=False,residual_family=False):
    run,out=Path(run).resolve(),Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    read=lambda n:json.loads((run/n).read_text(encoding='utf-8'))
    old=read('plan.json');meta=old['provenance'];ledger=read('run.json')
    points=np.load(run/'artifacts/cloud.npz')['points'];summary=read('artifacts/rgbd_summary.json')
    poses=np.asarray([p['camera_to_first'] for p in read('artifacts/trajectory.json')])
    code=sha256(Path(layout.__file__));original=layout._supported_wall_proposals
    source=inspect.getsource(original)
    needle='if len(proposals)-axis_start>=12: break'
    if source.count(needle)!=1:raise ValueError('Baseline cap differs from the declared experiment')
    namespace=dict(vars(layout))
    if not 12<=accepted_cap<=48:raise ValueError('Experimental cap must remain within the existing search budget')
    stage_cap=accepted_cap-12 if residual_search else accepted_cap
    exec(compile(source.replace(needle,f'if len(proposals)-axis_start>={stage_cap}: break'),
                 '<bounded_seed_budget_trial>','exec'),namespace)
    extended=namespace['_supported_wall_proposals']
    residual_counts={}
    if residual_search:
        def extended(points,planes,basis,floor,*,support_policy='local_spatial'):
            initial=original(points,planes,basis,floor,support_policy=support_policy)
            if residual_family:
                additions=[]
                for axis in (0,2):
                    remaining=np.ones(len(points),dtype=bool)
                    for p in planes+initial:
                        n=np.asarray(p['normal'])
                        if abs(n@basis[:,1])<=.15 and abs(n@basis[:,axis])>=np.cos(np.deg2rad(8)):
                            remaining &= np.abs(points@n+p['offset'])>=.035
                    axis_namespace=dict(vars(layout))
                    axis_source=source.replace(needle,f'if len(proposals)-axis_start>={stage_cap}: break')
                    axis_source=axis_source.replace('for axis in (0,2):',f'for axis in ({axis},):')
                    exec(compile(axis_source,'<wall_family_residual_trial>','exec'),axis_namespace)
                    additions.extend(axis_namespace['_supported_wall_proposals'](points[remaining],planes+initial,basis,floor,support_policy=support_policy))
                    residual_counts[str(axis)]=int(remaining.sum())
                fraction=min(18000,len(points))/len(points)
                for p in additions:
                    p['support']=int(p['raw_support_points']*fraction)
                    p['proposal_source']='wall projection mode; unexplained raw 3D plane consensus'
                return initial+additions
            remaining=np.ones(len(points),dtype=bool)
            for p in planes+initial:
                remaining &= np.abs(points@np.asarray(p['normal'])+p['offset'])>=.035
            residual_counts.update(total_points=len(points),unexplained_points=int(remaining.sum()))
            additions=namespace['_supported_wall_proposals'](points[remaining],planes+initial,basis,floor,support_policy=support_policy)
            fraction=min(18000,len(points))/len(points)
            for p in additions:
                p['support']=int(p['raw_support_points']*fraction)
                p['proposal_source']='wall projection mode; unexplained raw 3D plane consensus'
            return initial+additions
    started=time.perf_counter()
    layout._supported_wall_proposals=extended
    try:
        rooms,new=layout.extract_layout(points,summary['planes'],poses[:,:3,3],
            ledger['configuration'].get('down_direction',poses[0,:3,1]),
            path_breaks=meta.get('path_breaks',()))
    finally:layout._supported_wall_proposals=original
    def metrics(m):
        return dict(stages=m['boundary_stages'],coverage=m['camera_center_coverage_fraction'],
                    connections=len(m['connections']),unclosed_geometry=m['unclosed_geometry'])
    result=dict(experiment='complete_existing_bounded_seed_search',source_layout_sha256=code,
        source_unchanged=code==sha256(Path(layout.__file__)),before=metrics(meta),after=metrics(new),
        experimental_candidate_cap=48,experimental_acceptance_cap=accepted_cap,elapsed_s=time.perf_counter()-started,
        residual_search=residual_search,residual_counts=residual_counts,
        residual_family=residual_family,
        accuracy_improvement=None,script_sha256=sha256(Path(__file__)),
        input_sha256={n:sha256(run/n) for n in ['run.json','plan.json','artifacts/cloud.npz',
                     'artifacts/trajectory.json','artifacts/rgbd_summary.json','artifacts/layout_evidence.json']},
        limitations=['Experimental callable only; reconstruction source not modified',
                     'All original plane-support and finite-join thresholds retained',
                     'Coverage/cell counts are internal consistency, not measured accuracy'])
    new['experimental_seed_budget_per_axis']=accepted_cap
    (out/'layout_evidence.json').write_text(json.dumps(new,indent=2),encoding='utf-8')
    (out/'rooms.json').write_text(json.dumps(rooms,indent=2),encoding='utf-8')
    (out/'trial.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--accepted-cap',type=int,default=20)
    parser.add_argument('--residual',action='store_true')
    parser.add_argument('--residual-family',action='store_true')
    args=parser.parse_args();trial(args.run,args.out,args.accepted_cap,args.residual,args.residual_family)
