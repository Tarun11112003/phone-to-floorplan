"""Evaluate the saved density control without refitting or changing production."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shapely.geometry import Polygon
from floorplan.provenance import sha256
from scripts.experimental_lidar_sampling import compare_rooms, rooms_in_source_frame


def evaluate(run, trial, out):
    run, trial, out = map(Path, (run, trial, out))
    if out.exists() or not out.parent.is_dir():
        raise ValueError('Use a fresh evaluation JSON in an existing directory')
    record = json.loads((trial/'experiment.json').read_text(encoding='utf-8'))
    for key in ('input_sha256','sensor_sha256','production_code_sha256'):
        if any(sha256(p) != h for p,h in record[key].items()):
            raise ValueError('Retained inputs or production code changed')
    before = json.loads((run/'plan.json').read_text(encoding='utf-8'))['rooms']
    meta = json.loads((run/'artifacts/layout_evidence.json').read_text(encoding='utf-8'))
    candidate = json.loads((trial/'stride4_layout.json').read_text(encoding='utf-8'))
    rooms = rooms_in_source_frame(candidate['rooms'],meta,candidate['metadata'])
    comparisons = compare_rooms(before,rooms)
    observed = [r for r in comparisons if not r['source_inferred']]
    preserved = bool(observed) and all(r.get('corners_exact',False)
        and not r.get('candidate_inferred',True) for r in observed)
    overlaps = [dict(a=i,b=j,area_m2=float(Polygon(a['corners']).intersection(Polygon(b['corners'])).area))
        for i,a in enumerate(rooms) for j,b in enumerate(rooms) if j>i]
    counts = dict(baseline_covered_samples=round(record['baseline_coverage_fraction']*record['frames']),
        candidate_covered_samples=round(record['candidate_coverage_fraction']*record['frames']),
        camera_samples=record['frames'], baseline_cloud_points=record['baseline_point_count'],
        candidate_cloud_points=record['candidate_point_count'])
    result = dict(experiment='saved_lidar_sampling_common_frame_evaluation',metrics=counts,
        comparison_frame='baseline floor basis via known sensor-world bases; no fitted alignment or scale',
        room_comparison=comparisons,candidate_polygon_overlaps=overlaps,
        observed_baseline_preserved=preserved,
        candidate_remains_partial=candidate['metadata']['unclosed_geometry'],
        production_adoption=False,accuracy_validated=False,acceptance_claimed=False,
        decision='REJECT_DEFAULT_CHANGE' if not preserved else 'REQUIRES_INDEPENDENT_SENSOR_SUPPORT_VALIDATION',
        explanation=('Denser fusion replaces the accepted baseline polygon and adds inferred cells; '
                     'coverage gain does not justify changed boundaries' if not preserved else
                     'Preserved geometry alone does not prove the new cells are accurate'),
        prior_unframed_comparison_superseded=True, reconstruction_rerun=False,
        input_sha256={str(p.resolve()):sha256(p) for p in
            (run/'plan.json',run/'artifacts/layout_evidence.json',trial/'experiment.json',trial/'stride4_layout.json')},
        script_sha256=sha256(__file__))
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',default='demo/phase3_strip_trace/current_exterior/floor')
    parser.add_argument('--trial',default='demo/phase3_lidar_sampling/stride4_trial')
    parser.add_argument('--out',required=True)
    args=parser.parse_args();evaluate(args.run,args.trial,args.out)
