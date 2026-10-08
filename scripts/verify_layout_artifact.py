"""Replay frozen geometry artifacts; this verifies reproducibility, not accuracy."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import floorplan.layout as layout
from floorplan.provenance import producer,sha256

GEOMETRY_FILES=('cloud.npz','trajectory.json','rgbd_summary.json','layout_evidence.json')


def verify(run,out):
    run,out=Path(run).resolve(),Path(out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    artifact=run/'artifacts'
    ledger=json.loads((run/'run.json').read_text(encoding='utf-8'))
    source=json.loads((artifact/'layout_evidence.json').read_text(encoding='utf-8'))
    summary=json.loads((artifact/'rgbd_summary.json').read_text(encoding='utf-8'))
    points=np.load(artifact/'cloud.npz')['points']
    trajectory=json.loads((artifact/'trajectory.json').read_text(encoding='utf-8'))
    matrices=np.asarray([p['camera_to_first'] for p in trajectory])
    down=ledger['configuration'].get('down_direction')
    if down is None: down=matrices[0,:3,1]
    code_before=sha256(Path(layout.__file__))
    dependencies={name:sha256(Path(layout.__file__).parent/name)
                  for name in ('layout.py','rgbd.py','supported_cells.py')}
    rooms,replayed=layout.extract_layout(points,summary['planes'],matrices[:,:3,3],down,
        path_breaks=source.get('path_breaks',()),
        wall_support_policy=source.get('wall_support_policy','local_spatial'))
    # Compare the published JSON representations. Shapely coordinate sequences
    # are tuples in memory and lists after serialization; retain exact numbers.
    replayed=json.loads(json.dumps(replayed))
    keys=['basis_columns_in_input','floor_level_m','wall_segments','connections',
          'boundary_stages','camera_center_coverage_fraction','inferred_room_boundaries',
          'polygonization_diagnostics']
    checks={key:bool(source.get(key)==replayed.get(key)) for key in keys}
    checks['identical_layout_producer']=ledger.get('code_sha256',{}).get('layout.py')==code_before
    checks['identical_geometry_dependencies']=all(
        ledger.get('code_sha256',{}).get(name)==digest for name,digest in dependencies.items())
    checks['identical_measurement_producer']=(ledger.get('measurement_producer_fingerprint')
        ==producer(ledger['configuration'],'measurement')['fingerprint'])
    recorded=ledger.get('geometry_artifact_sha256',{})
    checks['geometry_artifacts_unchanged']=all(
        recorded.get('artifacts/'+name)==sha256(artifact/name) for name in GEOMETRY_FILES)
    checks['original_run_code_unchanged']=ledger.get('code_changed_during_run') is False
    checks['unchanged_layout_during_replay']=code_before==sha256(Path(layout.__file__))
    plan_path=run/'plan.json'
    expected=json.loads(plan_path.read_text(encoding='utf-8')).get('rooms',[]) if plan_path.exists() else []
    # JSON round-trip is an exact comparison of the coordinates actually used
    # for the original output. No rounded acceptance tolerance hides a change.
    replayed_corners=json.loads(json.dumps([r['corners'] for r in rooms]))
    checks['identical_room_corners']=replayed_corners==[r['corners'] for r in expected]
    result=dict(experiment='frozen_layout_artifact_replay',points_dtype=str(points.dtype),
        point_count=len(points),checks=checks,reproducible=all(checks.values()),
        source_coverage=source['camera_center_coverage_fraction'],
        replayed_coverage=replayed['camera_center_coverage_fraction'],
        source_stages=source['boundary_stages'],replayed_stages=replayed['boundary_stages'],
        accuracy_validated=False,input_sha256={str(p):sha256(p) for p in
            [run/'run.json',artifact/'cloud.npz',artifact/'trajectory.json',
             artifact/'rgbd_summary.json',artifact/'layout_evidence.json']},
        script_sha256=sha256(Path(__file__)),layout_sha256=code_before,
        artifact_integrity='verified' if checks['geometry_artifacts_unchanged'] else 'missing or mismatched source hashes',
        limitations=['Internal artifact reproducibility only; no independent measured truth',
                     'Exact artifact replay is not repeatability of independent captures'])
    (out/'layout_evidence.json').write_text(json.dumps(replayed,indent=2),encoding='utf-8')
    (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();result=verify(args.run,args.out)
    print(json.dumps({k:v for k,v in result.items() if k!='input_sha256'},indent=2))
    if not result['reproducible']:raise SystemExit(1)
