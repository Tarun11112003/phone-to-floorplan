"""Compare historical/global and local/spatial wall support on one frozen cloud.

Replays geometry only, not RGB/depth ingestion, mapping, damage or calibration.
Coverage/cells are development completeness proxies, never surveyed accuracy.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.layout import extract_layout,export_layout
from floorplan.provenance import sha256


def compare(run,output):
    run,output=Path(run).resolve(),Path(output).resolve(); output.mkdir(parents=True,exist_ok=False)
    artifact=run/'artifacts'
    points=np.load(artifact/'cloud.npz')['points'].astype(float)
    planes=json.loads((artifact/'rgbd_summary.json').read_text())['planes']
    trajectory=json.loads((artifact/'trajectory.json').read_text())
    matrices=np.asarray([p['camera_to_first'] for p in trajectory]); centers=matrices[:,:3,3]
    frozen=json.loads((artifact/'layout_evidence.json').read_text())
    down=json.loads((run/'run.json').read_text())['configuration'].get('down_direction')
    if down is None: down=matrices[0,:3,1]
    rows=[]
    for policy in ['global_equivalent','local_spatial']:
        start=time.perf_counter()
        rooms,metadata=extract_layout(points,planes,centers,down,path_breaks=frozen.get('path_breaks',()),wall_support_policy=policy)
        directory=output/policy; directory.mkdir()
        (directory/'layout_evidence.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        if rooms: export_layout(rooms,metadata,directory,complete_capture=False)
        rows.append(dict(policy=policy,rooms=len(rooms),coverage=metadata['camera_center_coverage_fraction'],
            connections=len(metadata['connections']),stages=metadata['boundary_stages'],unclosed=metadata['unclosed_geometry'],
            runtime_s=time.perf_counter()-start))
    result=dict(experiment='local_wall_support_correctness',source_run=str(run),
        input_sha256={str(p):sha256(p) for p in [run/'run.json',artifact/'cloud.npz',artifact/'trajectory.json',artifact/'rgbd_summary.json']},
        script_sha256=sha256(Path(__file__)),layout_sha256=sha256(Path(__file__).parents[1]/'floorplan/layout.py'),
        comparisons=rows,accuracy_validated=False,
        limitations=['Saved float32 cloud reloaded; tiny polygon slivers can differ from original float64 fusion',
                    'No independent room labels or surveyed dimensions; no physical accuracy delta',
                    'Geometry-only replay; raw end-to-end replay required after any production change'])
    (output/'comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='input_sha256'},indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path)
    parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();compare(args.run,args.out)
