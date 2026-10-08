from datetime import datetime,timezone,timedelta
import json

import pytest

from floorplan.provenance import sha256
from scripts.fix_evidence import declare,verify


def baseline_fixture(tmp_path):
    source=tmp_path/'source'; source.mkdir()
    (source/'geometry.py').write_text('measurement_setting = 1\n')
    baseline=tmp_path/'baseline'; baseline.mkdir()
    ledger=dict(code_changed_during_run=False,code_sha256={'geometry.py':sha256(source/'geometry.py')},
                inputs={'image.png':'raw_hash'},configuration={'tier':'photos'},measurement_producer_fingerprint='before')
    (baseline/'run.json').write_text(json.dumps(ledger))
    metrics=tmp_path/'metrics.json'; metrics.write_text(json.dumps({'evaluator_version':'test-v1','walls':{'gate':'fail','error_m':.1}}))
    reference=tmp_path/'reference.json'; reference.write_text('{}')
    return source,baseline,metrics,reference,ledger


def test_declaration_rejects_a_retrospective_source_change(tmp_path):
    source,baseline,metrics,reference,ledger=baseline_fixture(tmp_path)
    (source/'geometry.py').write_text('measurement_setting = 2\n')
    with pytest.raises(ValueError,match='retrospective'):
        declare(baseline,metrics,reference,source,tmp_path/'declaration',gate='walls',field=['walls','error_m'],
                prediction=.02,root_cause='fixture cause',intended_change='fixture change',evidence=[metrics])


def test_declared_fix_preserves_diff_prediction_and_identical_input_check(tmp_path):
    source,baseline,metrics,reference,ledger=baseline_fixture(tmp_path)
    folder=tmp_path/'declaration'
    declaration=declare(baseline,metrics,reference,source,folder,gate='walls',field=['walls','error_m'],
        prediction=.02,root_cause='fixture cause',intended_change='fixture change',evidence=[metrics])
    (source/'geometry.py').write_text('measurement_setting = 2\n')
    after=tmp_path/'after'; after.mkdir()
    ledger.update(started_utc=(datetime.fromisoformat(declaration['declared_utc'])+timedelta(seconds=1)).isoformat(),
                  code_sha256={'geometry.py':sha256(source/'geometry.py')})
    (after/'run.json').write_text(json.dumps(ledger))
    metrics.write_text(json.dumps({'evaluator_version':'test-v1','walls':{'gate':'pass','error_m':.025}}))
    review=verify(folder,after,metrics,reference,source,tmp_path/'review')
    assert review['prediction_error']==pytest.approx(.005)
    assert review['source_or_configuration_changed']
    assert '-measurement_setting = 1' in (tmp_path/'review/source_config.diff').read_text()
    ledger['inputs']['image.png']='different'; (after/'run.json').write_text(json.dumps(ledger))
    with pytest.raises(ValueError,match='inputs differ'):
        verify(folder,after,metrics,reference,source,tmp_path/'invalid')


def test_unchanged_version_label_cannot_hide_changed_evaluation_rules(tmp_path):
    source,baseline,metrics,reference,ledger=baseline_fixture(tmp_path)
    rules=source/'acceptance.py'; rules.write_text('threshold = 1\n')
    ledger['code_sha256']['acceptance.py']=sha256(rules)
    (baseline/'run.json').write_text(json.dumps(ledger))
    folder=tmp_path/'declaration'
    declaration=declare(baseline,metrics,reference,source,folder,gate='walls',field=['walls','error_m'],
        prediction=.02,root_cause='fixture cause',intended_change='fixture change',evidence=[metrics])
    rules.write_text('threshold = 2\n')
    ledger['code_sha256']['acceptance.py']=sha256(rules)
    ledger['started_utc']=(datetime.fromisoformat(declaration['declared_utc'])+timedelta(seconds=1)).isoformat()
    after=tmp_path/'after'; after.mkdir(); (after/'run.json').write_text(json.dumps(ledger))
    with pytest.raises(ValueError,match='Evaluator source changed'):
        verify(folder,after,metrics,reference,source,tmp_path/'review')
