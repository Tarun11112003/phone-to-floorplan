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
