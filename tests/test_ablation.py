import json

import pytest

from floorplan.ablation import compare_pose_correction


def test_ablation_rejects_different_inputs_and_code(tmp_path):
    for mode in ('off','on'):
        path=tmp_path/mode; path.mkdir()
        ledger=dict(inputs={'rgb':'hash'},configuration={'optimize_poses':mode=='on'},
                    code_sha256={'module':'hash'},code_changed_during_run=False,runtime_s=1,
                    result={'status':'partial'})
        (path/'run.json').write_text(json.dumps(ledger))
    result=compare_pose_correction(tmp_path/'off',tmp_path/'on')
    assert result['accuracy_improvement'] is None
    assert result['runs'][0]['footprint_area_m2'] is None
    path=tmp_path/'on'/'run.json'; ledger=json.loads(path.read_text())
    ledger['inputs']['rgb']='different'; path.write_text(json.dumps(ledger))
    with pytest.raises(ValueError,match='identical hashed'): compare_pose_correction(tmp_path/'off',tmp_path/'on')
    ledger['inputs']['rgb']='hash'; ledger['code_sha256']['module']='changed'; path.write_text(json.dumps(ledger))
    with pytest.raises(ValueError,match='identical reconstruction'): compare_pose_correction(tmp_path/'off',tmp_path/'on')


def test_ablation_rejects_mode_that_was_not_applied_to_the_normalized_sequence(tmp_path):
    for mode in ('off','on'):
        path=tmp_path/mode; path.mkdir()
        ledger=dict(inputs={'rgb':'hash'},configuration={'optimize_poses':mode=='on'},
                    code_sha256={'module':'hash'},code_changed_during_run=False,runtime_s=1,tier='video',
                    result={'status':'partial','mapping':{'enabled':mode=='on','verified_loops':0}})
        (path/'run.json').write_text(json.dumps(ledger))
        (path/'normalized_sequence.json').write_text(json.dumps({'optimize_poses':True}))
    with pytest.raises(ValueError,match='honor'):
        compare_pose_correction(tmp_path/'off',tmp_path/'on')
    (tmp_path/'off/normalized_sequence.json').write_text(json.dumps({'optimize_poses':False}))
    result=compare_pose_correction(tmp_path/'off',tmp_path/'on')
    assert not result['verified_drift_correction_demonstrated']


def test_changed_pose_graph_can_be_verified_without_loop_and_raw_priors_do_not_count(tmp_path):
    import numpy as np
    edge=dict(loop=False,icp_accepted=True,constraint_source='verified_icp',
              fitness=.8,rmse_m=.01,icp_rotation_correction_deg=.2)
    for mode in ['off','on']:
        directory=tmp_path/mode; (directory/'artifacts').mkdir(parents=True)
        pose=np.eye(4); pose[0,3]=.02 if mode=='on' else 0
        (directory/'artifacts/trajectory.json').write_text(json.dumps([dict(frame_id=1,camera_to_first=pose.tolist())]))
        mapping=dict(enabled=mode=='on',verified_loops=0,segments=[dict(edges=[edge])] if mode=='on' else [])
        ledger=dict(inputs={'rgb':'hash'},configuration={'optimize_poses':mode=='on'},
                    code_sha256={'module':'hash'},code_changed_during_run=False,runtime_s=1,
                    result=dict(status='partial',mapping=mapping))
        (directory/'run.json').write_text(json.dumps(ledger))
    result=compare_pose_correction(tmp_path/'off',tmp_path/'on')
    assert result['verified_drift_correction_demonstrated']
    assert result['runs'][1]['verified_constraints']==dict(sequential_icp=1,loop_icp=0,total=1)
    assert result['accuracy_improvement'] is None
    path=tmp_path/'on/run.json'; ledger=json.loads(path.read_text())
    ledger['result']['mapping']['segments'][0]['edges'][0]['constraint_source']='raw_pose_prior'
    ledger['result']['mapping']['verified_loops']=99  # An unbacked counter is insufficient.
    path.write_text(json.dumps(ledger))
    assert not compare_pose_correction(tmp_path/'off',tmp_path/'on')['verified_drift_correction_demonstrated']
