import json
from pathlib import Path

import numpy as np

import floorplan.layout as layout
from floorplan.provenance import producer,sha256
from scripts.verify_layout_artifact import GEOMETRY_FILES,verify


def recorded_run(tmp_path,monkeypatch):
    run=tmp_path/'run';artifact=run/'artifacts';artifact.mkdir(parents=True)
    metadata=dict(basis_columns_in_input=np.eye(3).tolist(),floor_level_m=np.float64(0),
        wall_segments=[],connections=[],boundary_stages={'accepted_observed_polygons':1},
        camera_center_coverage_fraction=1.,inferred_room_boundaries=[],
        polygonization_diagnostics=dict(dangles=[[(0.,0.),(1.,0.)]]))
    room=dict(corners=[[0,0],[4,0],[4,3],[0,3]])
    np.savez_compressed(artifact/'cloud.npz',points=np.array([[.1,.2,.3]],dtype=np.float64))
    (artifact/'trajectory.json').write_text(json.dumps([dict(camera_to_first=np.eye(4).tolist())]))
    (artifact/'rgbd_summary.json').write_text(json.dumps(dict(planes=[])))
    (artifact/'layout_evidence.json').write_text(json.dumps(metadata))
    (run/'plan.json').write_text(json.dumps(dict(rooms=[room])))
    ledger=dict(configuration={'down_direction':[0,1,0]},code_changed_during_run=False,
        code_sha256={name:sha256(Path(layout.__file__).parent/name)
                     for name in ('layout.py','rgbd.py','supported_cells.py')},
        geometry_artifact_sha256={'artifacts/'+name:sha256(artifact/name) for name in GEOMETRY_FILES})
    ledger['measurement_producer_fingerprint']=producer(ledger['configuration'],'measurement')['fingerprint']
    (run/'run.json').write_text(json.dumps(ledger))
    monkeypatch.setattr(layout,'extract_layout',lambda *args,**kwargs:([room],metadata))
    return run,room


def test_exact_replay_writes_serializable_checks_without_accuracy_claim(tmp_path,monkeypatch):
    run,_=recorded_run(tmp_path,monkeypatch)
    result=verify(run,tmp_path/'out')
    assert result['reproducible'] and result['artifact_integrity']=='verified'
    assert not result['accuracy_validated']
    assert json.loads((tmp_path/'out/verification.json').read_text())['reproducible']


def test_modified_cloud_is_rejected_even_if_plausible_geometry_is_unchanged(tmp_path,monkeypatch):
    run,_=recorded_run(tmp_path,monkeypatch)
    np.savez_compressed(run/'artifacts/cloud.npz',points=np.array([[9.,9.,9.]]))
    result=verify(run,tmp_path/'out')
    assert not result['reproducible']
    assert not result['checks']['geometry_artifacts_unchanged']


def test_equal_room_count_and_coverage_do_not_hide_changed_dimensions(tmp_path,monkeypatch):
    run,room=recorded_run(tmp_path,monkeypatch)
    room['corners'][1][0]=4.001
    result=verify(run,tmp_path/'out')
    assert result['checks']['camera_center_coverage_fraction']
    assert not result['checks']['identical_room_corners']
    assert not result['reproducible']


def test_unversioned_source_is_not_verified_as_same_producer(tmp_path,monkeypatch):
    run,_=recorded_run(tmp_path,monkeypatch)
    ledger=json.loads((run/'run.json').read_text());ledger['code_sha256']={}
    (run/'run.json').write_text(json.dumps(ledger))
    result=verify(run,tmp_path/'out')
    assert not result['checks']['identical_geometry_dependencies']
    assert not result['reproducible']


def test_changed_dependency_recipe_is_rejected_even_with_matching_geometry(tmp_path,monkeypatch):
    run,_=recorded_run(tmp_path,monkeypatch)
    ledger=json.loads((run/'run.json').read_text())
    ledger['measurement_producer_fingerprint']='different dependency version or recipe'
    (run/'run.json').write_text(json.dumps(ledger))
    result=verify(run,tmp_path/'out')
    assert result['checks']['identical_room_corners']
    assert not result['checks']['identical_measurement_producer']
    assert not result['reproducible']
