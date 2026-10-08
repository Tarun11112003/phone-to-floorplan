"""Measure precision-grid sensitivity without adding wall support or gap closure."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from shapely import union_all
import floorplan.layout as layout
from floorplan.provenance import sha256


def compare(run,out,canonical_segments=False,canonical_junctions=False):
    run,out=Path(run).resolve(),Path(out).resolve(); out.mkdir(parents=True,exist_ok=False)
    artifact=run/'artifacts'; points=np.load(artifact/'cloud.npz')['points'].astype(float)
    planes=json.loads((artifact/'rgbd_summary.json').read_text())['planes']
    trajectory=json.loads((artifact/'trajectory.json').read_text()); matrices=np.asarray([p['camera_to_first'] for p in trajectory])
    metadata=json.loads((artifact/'layout_evidence.json').read_text())
    down=json.loads((run/'run.json').read_text())['configuration'].get('down_direction')
    if down is None: down=matrices[0,:3,1]
    original=layout.union_all; original_segments=layout._segments;original_junctions=layout._bounded_corner_network;rows=[]
    def rounded(segments):
        for segment in segments:
            for key in ['location','lo','hi']: segment[key]=round(segment[key],4)
            if segment.get('plane_line') is not None:
                segment['plane_line']=[round(v,7 if i<2 else 4) for i,v in enumerate(segment['plane_line'])]
        return segments
    if canonical_segments:
        def canonical(*args,**kwargs):
            segments=original_segments(*args,**kwargs)
            return rounded(segments)
        layout._segments=canonical
    if canonical_junctions:
        layout._bounded_corner_network=lambda network:original_junctions(rounded(network))
    try:
        for grid in [None,1e-6,1e-4]:
            layout.union_all=lambda lines,**kwargs: original(lines,grid_size=grid)
            start=time.perf_counter()
            rooms,evidence=layout.extract_layout(points,planes,matrices[:,:3,3],down,path_breaks=metadata.get('path_breaks',()))
            directory=out/('floating' if grid is None else str(grid)); directory.mkdir()
            (directory/'layout_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
            if rooms: layout.export_layout(rooms,evidence,directory,complete_capture=False)
            rows.append(dict(grid_m=grid,rooms=len(rooms),coverage=evidence['camera_center_coverage_fraction'],
                unclosed=evidence['unclosed_geometry'],stages=evidence['boundary_stages'],runtime_s=time.perf_counter()-start))
    finally:
        layout.union_all=original;layout._segments=original_segments;layout._bounded_corner_network=original_junctions
    result=dict(experiment='finite_network_precision',canonical_segments=canonical_segments,canonical_junctions=canonical_junctions,comparisons=rows,accuracy_validated=False,production_adopted=False,
        input_sha256={str(p):sha256(p) for p in [run/'run.json',artifact/'cloud.npz',artifact/'trajectory.json']},
        script_sha256=sha256(Path(__file__)),layout_sha256=sha256(Path(layout.__file__)),
        limitations=['Numerical topology/internal consistency only; no independent surveyed room identity',
                     'The existing <=15cm corner rule is unchanged; no new observed support'])
    (out/'comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='input_sha256'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path)
    parser.add_argument('--out',required=True,type=Path);parser.add_argument('--canonical-segments',action='store_true')
    parser.add_argument('--canonical-junctions',action='store_true')
    args=parser.parse_args();compare(args.run,args.out,args.canonical_segments,args.canonical_junctions)
