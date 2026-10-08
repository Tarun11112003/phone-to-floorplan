"""Isolate residual discovery from native reconstruction variation and truth."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from shapely.geometry import Polygon
import floorplan.layout as layout
from floorplan.provenance import producer,sha256


def compare(baseline,candidate,out,baseline_mode='initial'):
    baseline,candidate,out=map(lambda p:Path(p).resolve(),(baseline,candidate,out))
    out.mkdir(parents=True,exist_ok=False)
    read=lambda root,n:json.loads((root/n).read_text(encoding='utf-8'))
    before,after=read(baseline,'run.json'),read(candidate,'run.json')
    old=read(baseline,'plan.json');source=read(baseline,'artifacts/layout_evidence.json')
    summary=read(baseline,'artifacts/rgbd_summary.json')
    cloud=np.load(baseline/'artifacts/cloud.npz')['points']
    poses=np.asarray([p['camera_to_first'] for p in read(baseline,'artifacts/trajectory.json')])
    down=before['configuration'].get('down_direction',poses[0,:3,1])
    code_before=sha256(Path(layout.__file__));original=layout._supported_wall_proposals
    def initial_only(*args,**kwargs):
        return original(*args,**kwargs,residual_search=baseline_mode=='residual',original_seed_search=False)
    layout._supported_wall_proposals=initial_only
    try:
        control_rooms,control=layout.extract_layout(cloud,summary['planes'],poses[:,:3,3],down,
            path_breaks=source.get('path_breaks',()),wall_support_policy=source.get('wall_support_policy','local_spatial'))
    finally:layout._supported_wall_proposals=original
    rooms,current=layout.extract_layout(cloud,summary['planes'],poses[:,:3,3],down,
        path_breaks=source.get('path_breaks',()),wall_support_policy=source.get('wall_support_policy','local_spatial'))
    control,current,rooms,control_rooms=json.loads(json.dumps([control,current,rooms,control_rooms]))
    keys=['wall_segments','wall_plane_proposals','camera_path_2d','connections',
          'boundary_stages','polygonization_diagnostics']
    checks={key:control[key]==source[key] for key in keys}
    checks['initial_only_corners_exact']=[r['corners'] for r in control_rooms]==[r['corners'] for r in old['rooms']]
    if baseline_mode=='residual':
        checks['all_prior_cell_corners_exact']=[r['corners'] for r in rooms]==[r['corners'] for r in old['rooms']]
        checks['prior_connections_exact']=current['connections']==source['connections']
    checks['initial_proposals_retained_exactly']=current['wall_plane_proposals'][:len(source['wall_plane_proposals'])]==source['wall_plane_proposals']
    additions=current['wall_plane_proposals'][len(source['wall_plane_proposals']):]
    checks['residual_support_guards_retained']=all(
        p['raw_support_points']>=250 and p['occupied_10cm_cells']>=40 and p['rms_m']<=.025
        and p['observed_height_span_m']>=.9 and p['observed_length_span_m']>=.6 for p in additions)
    def intact(root,ledger):
        names=['artifacts/'+n for n in ('cloud.npz','trajectory.json','rgbd_summary.json','layout_evidence.json')]
        return all(ledger.get('geometry_artifact_sha256',{}).get(n)==sha256(root/n) for n in names)
    checks.update(identical_inputs=bool(before['inputs']) and before['inputs']==after['inputs'],
        identical_configuration=before['configuration']==after['configuration'],
        source_artifacts_intact=intact(baseline,before),candidate_artifacts_intact=intact(candidate,after),
        original_producers_frozen=before['code_changed_during_run'] is False and after['code_changed_during_run'] is False,
        candidate_producer_matches=after['measurement_producer_fingerprint']==producer(after['configuration'],'measurement')['fingerprint'],
        layout_unchanged_during_comparison=code_before==sha256(Path(layout.__file__)),
        inference_remains_partial=not current['inferred_room_boundaries'] or current['unclosed_geometry'])
    def metrics(m):
        return dict(stages=m['boundary_stages'],camera_coverage_fraction=m['camera_center_coverage_fraction'],
                    connections=len(m['connections']),unclosed_geometry=m['unclosed_geometry'])
    changes=[]
    for room in old['rooms']:
        if room.get('requires_boundary_review'):continue
        p=Polygon(room['corners']);best=max(rooms,key=lambda r:p.intersection(Polygon(r['corners'])).area)
        q=Polygon(best['corners'])
        changes.append(dict(source_room_id=room['id'],candidate_cell_id=best['id'],
            exact_corners_retained=room['corners']==best['corners'],before_area_m2=p.area,after_area_m2=q.area,
            retained_area_fraction=p.intersection(q).area/p.area,
            boundary_hausdorff_change_m=p.hausdorff_distance(q),accuracy_change_unknown=True))
    raw=read(candidate,'artifacts/layout_evidence.json')
    result=dict(experiment='residual_wall_discovery_controlled_comparison',checks=checks,
        baseline_mode=baseline_mode,
        controls_verified=all(checks.values()),before=metrics(source),after_frozen=metrics(current),after_raw=metrics(raw),
        additional_plane_proposals=len(additions),observed_cell_shape_changes=changes,
        raw_camera_path_exact=raw['camera_path_2d']==source['camera_path_2d'],
        raw_camera_path_max_absolute_change_m=float(np.max(np.abs(np.asarray(raw['camera_path_2d'])-source['camera_path_2d']))),
        accuracy_improvement=None,script_sha256=sha256(Path(__file__)),
        evidence_sha256={str(root/n):sha256(root/n) for root in (baseline,candidate)
                         for n in ('run.json','plan.json','artifacts/cloud.npz','artifacts/layout_evidence.json')},
        limitations=['Selected baseline policy replay must match its saved geometry exactly; candidate may discover additional surfaces',
                     'Candidate cell shape changes are disclosed, not validated as more accurate',
                     'Coverage/cell counts and artifact replay do not establish semantic room identities or physical accuracy'])
    (out/'layout_evidence.json').write_text(json.dumps(current,indent=2),encoding='utf-8')
    (out/'comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline',type=Path);parser.add_argument('candidate',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--baseline-mode',choices=['initial','residual'],default='initial')
    args=parser.parse_args();result=compare(args.baseline,args.candidate,args.out,args.baseline_mode)
    print(json.dumps({k:v for k,v in result.items() if k!='evidence_sha256'},indent=2))
    if not result['controls_verified']:raise SystemExit(1)
