"""Isolate a layout change on frozen geometry; retain strict raw-run failures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.layout import extract_layout
from floorplan.provenance import producer,sha256
from scripts.compare_boundary_runs import compare


def controlled_compare(baseline,candidate,out):
    baseline,candidate,out=map(lambda p:Path(p).resolve(),(baseline,candidate,out))
    out.mkdir(parents=True,exist_ok=False)
    raw=compare(baseline,candidate)
    read=lambda root,name:json.loads((root/name).read_text(encoding='utf-8'))
    before,after=read(baseline,'run.json'),read(candidate,'run.json')
    old=read(baseline,'plan.json'); metadata=old['provenance']
    source=read(baseline,'artifacts/layout_evidence.json')
    summary=read(baseline,'artifacts/rgbd_summary.json')
    cloud=np.load(baseline/'artifacts/cloud.npz')['points']
    poses=np.asarray([p['camera_to_first'] for p in read(baseline,'artifacts/trajectory.json')])
    down=before['configuration'].get('down_direction')
    if down is None: down=poses[0,:3,1]
    recipe=producer(after['configuration'],'measurement')['fingerprint']
    rooms,frozen=extract_layout(cloud,summary['planes'],poses[:,:3,3],down,
        path_breaks=source.get('path_breaks',()),
        wall_support_policy=source.get('wall_support_policy','local_spatial'))
    frozen=json.loads(json.dumps(frozen)); rooms=json.loads(json.dumps(rooms))
    observed=lambda rows:[(r['id'],r['corners']) for r in rows
                          if not r.get('requires_boundary_review',False)]
    # Keep the raw comparator's exact-equality failures visible. They are not
    # replaced by a numerical tolerance or relabelled as successful raw reruns.
    checks={key:raw['checks'][key] for key in (
        'identical_inputs','identical_manifest','identical_configuration',
        'frozen_baseline_producer','frozen_candidate_producer',
        'baseline_artifacts_intact','candidate_artifacts_intact','no_accuracy_promotion')}
    checks.update(
        controlled_candidate_producer=recipe==after['measurement_producer_fingerprint'],
        producer_unchanged_during_control=recipe==producer(after['configuration'],'measurement')['fingerprint'],
        frozen_camera_path_exact=frozen['camera_path_2d']==metadata['camera_path_2d'],
        frozen_observed_walls_exact=frozen['wall_segments']==metadata['wall_segments'],
        frozen_observed_cells_exact=observed(rooms)==observed(old['rooms']),
        frozen_observed_connections_exact=frozen['connections']==metadata['connections'],
        inferred_cells_remain_review_only=all(r.get('requires_boundary_review')
            and r['boundary_evidence'].get('accuracy_validated') is False
            for r in rooms if 'boundary_evidence' in r),
        inferred_geometry_still_partial=not frozen['inferred_room_boundaries'] or frozen['unclosed_geometry'])
    candidate_meta=read(candidate,'artifacts/layout_evidence.json')
    def max_delta(a,b):
        a,b=np.asarray(a,float),np.asarray(b,float)
        return float(np.max(np.abs(a-b))) if a.shape==b.shape and a.size else None
    result=dict(experiment='controlled_partial_cell_layout_comparison',checks=checks,
        controlled_invariants_preserved=all(checks.values()),
        raw_exact_comparison=raw,
        raw_camera_path_max_absolute_change_m=max_delta(metadata['camera_path_2d'],candidate_meta['camera_path_2d']),
        raw_wall_location_max_absolute_change_m=max_delta(
            [s['location'] for s in metadata['wall_segments']],
            [s['location'] for s in candidate_meta['wall_segments']]),
        before=raw['before'],after_raw=raw['after'],
        after_frozen=dict(observed_cells=frozen['boundary_stages']['accepted_observed_polygons'],
            inferred_cells=frozen['boundary_stages']['inferred_fallback_cells'],
            camera_center_coverage_fraction=frozen['camera_center_coverage_fraction'],
            connections=len(frozen['connections']),unclosed_geometry=frozen['unclosed_geometry']),
        accuracy_improvement=None,script_sha256=sha256(Path(__file__)),
        limitations=['Layout comparison holds baseline cloud, planes and poses fixed',
                     'Exact native raw-run equality is separately reported and can still fail',
                     'Inferred cells and camera coverage do not prove semantic rooms or metric accuracy'])
    (out/'layout_evidence.json').write_text(json.dumps(frozen,indent=2),encoding='utf-8')
    (out/'comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline',type=Path);parser.add_argument('candidate',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();result=controlled_compare(args.baseline,args.candidate,args.out)
    print(json.dumps({k:v for k,v in result.items() if k!='raw_exact_comparison'},indent=2))
    if not result['controlled_invariants_preserved']: raise SystemExit(1)
