"""Compare identical-input boundary runs; camera coverage is not metric truth."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from floorplan.provenance import sha256


def compare(baseline,candidate):
    baseline,candidate=Path(baseline).resolve(),Path(candidate).resolve()
    def read(root,name):
        return json.loads((root/name).read_text(encoding='utf-8'))
    before,after=read(baseline,'run.json'),read(candidate,'run.json')
    old,new=read(baseline,'plan.json'),read(candidate,'plan.json')
    a,b=old['provenance'],new['provenance']
    observed=lambda plan:[(r['id'],r['corners']) for r in plan['rooms']
                          if not r.get('requires_boundary_review',False)]
    def intact(root,ledger):
        hashes=ledger.get('geometry_artifact_sha256',{})
        required=['artifacts/'+name for name in
                  ('cloud.npz','trajectory.json','rgbd_summary.json','layout_evidence.json')]
        return all(name in hashes and (root/name).is_file()
                   and sha256(root/name)==hashes[name] for name in required)
    checks=dict(
        identical_inputs=bool(before.get('inputs')) and before['inputs']==after.get('inputs'),
        identical_manifest=before.get('manifest_sha256')==after.get('manifest_sha256'),
        identical_configuration=before['configuration']==after['configuration'],
        frozen_baseline_producer=before.get('code_changed_during_run') is False,
        frozen_candidate_producer=after.get('code_changed_during_run') is False,
        baseline_artifacts_intact=intact(baseline,before),
        candidate_artifacts_intact=intact(candidate,after),
        identical_camera_path=a['camera_path_2d']==b['camera_path_2d'],
        identical_observed_walls=a['wall_segments']==b['wall_segments'],
        identical_observed_cells=observed(old)==observed(new),
        identical_observed_connections=a['connections']==b['connections'],
        no_accuracy_promotion=old.get('accuracy_validated') is False
                              and new.get('accuracy_validated') is False,
        inferred_cells_remain_partial=(not b['inferred_room_boundaries']
                                       or (b['unclosed_geometry'] and new['status']=='partial'
                                           and after.get('contract_complete') is False)))
    def metrics(plan,ledger):
        m=plan['provenance']
        return dict(observed_cells=m['boundary_stages']['accepted_observed_polygons'],
                    inferred_cells=m['boundary_stages']['inferred_fallback_cells'],
                    camera_samples=len(m['camera_path_2d']),
                    camera_center_coverage_fraction=m['camera_center_coverage_fraction'],
                    connections=len(m['connections']),status=plan['status'],
                    contract_complete=ledger.get('contract_complete'),
                    reconstruction_runtime_s=ledger.get('runtime_s'))
    return dict(experiment='identical_input_partial_boundary_comparison',
                baseline=str(baseline),candidate=str(candidate),checks=checks,
                software_invariants_preserved=all(checks.values()),
                before=metrics(old,before),after=metrics(new,after),
                camera_coverage_change_percentage_points=100*(
                    b['camera_center_coverage_fraction']-a['camera_center_coverage_fraction']),
                accuracy_improvement=None,
                baseline_measurement_producer=before.get('measurement_producer_fingerprint'),
                candidate_measurement_producer=after.get('measurement_producer_fingerprint'),
                evidence_sha256={str(root/name):sha256(root/name)
                    for root in (baseline,candidate) for name in ('run.json','plan.json')},
                script_sha256=sha256(Path(__file__)),
                limitations=['Camera-in-cell coverage is internal consistency, not footprint accuracy',
                             'Inferred cells are hypotheses, not verified semantic rooms',
                             'No independent survey, physical repeat or qualified assessment Fix Loop'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline',type=Path);parser.add_argument('candidate',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists(): raise FileExistsError('Use a fresh comparison output')
    result=compare(args.baseline,args.candidate)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='evidence_sha256'},indent=2))
    if not result['software_invariants_preserved']: raise SystemExit(1)
