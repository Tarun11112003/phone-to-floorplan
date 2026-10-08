import json

import pytest

from floorplan.provenance import sha256
from scripts.compare_boundary_runs import compare


def runs(tmp_path):
    metadata=dict(wall_segments=[dict(location=0.)],camera_path_2d=[[1.,1.]],
        connections=[],inferred_room_boundaries=[],unclosed_geometry=False,
        boundary_stages=dict(accepted_observed_polygons=1,inferred_fallback_cells=0),
        camera_center_coverage_fraction=1.)
    plan=dict(rooms=[dict(id='room_0',corners=[[0,0],[2,0],[2,2],[0,2]])],
              provenance=metadata,accuracy_validated=False,status='proposal_requires_review')
    roots=[tmp_path/'before',tmp_path/'after']
    for root in roots:
        root.mkdir();(root/'artifacts').mkdir()
        hashes={}
        for name in ('cloud.npz','trajectory.json','rgbd_summary.json','layout_evidence.json'):
            path=root/'artifacts'/name;path.write_bytes(b'test artifact')
            hashes['artifacts/'+name]=sha256(path)
        ledger=dict(inputs={'capture':'same-input-hash'},manifest_sha256='same-manifest',
            configuration={'tier':'lidar'},code_changed_during_run=False,
            geometry_artifact_sha256=hashes,contract_complete=False)
        (root/'run.json').write_text(json.dumps(ledger))
        (root/'plan.json').write_text(json.dumps(plan))
    return roots


def update(root,name,edit):
    path=root/name;data=json.loads(path.read_text());edit(data)
    path.write_text(json.dumps(data))


def test_identical_boundary_comparison_keeps_accuracy_unavailable(tmp_path):
    result=compare(*runs(tmp_path))
    assert result['software_invariants_preserved']
    assert result['accuracy_improvement'] is None


def test_native_roundoff_remains_an_exact_comparison_failure(tmp_path):
    before,after=runs(tmp_path)
    def change(plan):
        plan['provenance']['wall_segments'][0]['location']=1e-14
        plan['provenance']['camera_path_2d'][0][0]+=1e-14
    update(after,'plan.json',change)
    result=compare(before,after)
    assert not result['software_invariants_preserved']
    assert not result['checks']['identical_observed_walls']
    assert not result['checks']['identical_camera_path']
    assert result['checks']['identical_observed_cells']


@pytest.mark.parametrize('failure',['input','artifact','promotion'])
def test_boundary_comparison_rejects_invalid_evidence(tmp_path,failure):
    before,after=runs(tmp_path)
    if failure=='input':
        update(after,'run.json',lambda d:d['inputs'].update(capture='different-hash'))
    elif failure=='artifact':
        (after/'artifacts/cloud.npz').write_bytes(b'tampered')
    else:
        def promote(plan):
            plan['provenance']['inferred_room_boundaries']=[{}]
            plan['provenance']['unclosed_geometry']=False
        update(after,'plan.json',promote)
        update(after,'run.json',lambda d:d.update(contract_complete=True))
    assert not compare(before,after)['software_invariants_preserved']
