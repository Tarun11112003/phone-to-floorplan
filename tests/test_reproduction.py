import json

from scripts.evaluation.reproduce_artifacts import reproduce


def test_copied_or_unchecked_artifacts_are_not_regenerated(tmp_path):
    manifest={'artifacts':[dict(id='old',mode='historical',reason='original producer unavailable'),
                           dict(id='skipped',mode='skip',reason='raw captures missing')]}
    result=reproduce(manifest,tmp_path/'out')
    assert result['regenerated_verified']==0
    assert not result['all_claims_regenerated']


def test_reproduction_checks_regenerated_claim_and_detects_wrong_number(tmp_path):
    command=['python','-c',"import json,pathlib; pathlib.Path(r'{output}/metrics.json').write_text(json.dumps({'count':3}))"]
    artifact=dict(id='actual',command=command,claims=[dict(path='metrics.json',field=['count'],value=3)])
    result=reproduce({'artifacts':[artifact]},tmp_path/'good')
    assert result['all_claims_regenerated']
    artifact['claims'][0]['value']=4
    result=reproduce({'artifacts':[artifact]},tmp_path/'bad')
    assert result['artifacts'][0]['status']=='failed'


def test_failed_command_or_missing_field_is_recorded_without_false_success(tmp_path):
    result=reproduce({'artifacts':[dict(id='bad',command=['python','-c','raise SystemExit(1)'])]},tmp_path/'command')
    assert result['artifacts'][0]['status']=='failed'
    assert not result['all_claims_regenerated']
    command=['python','-c',"import pathlib; pathlib.Path(r'{output}/result.json').write_text('{}')"]
    result=reproduce({'artifacts':[dict(id='missing',command=command,claims=[dict(path='result.json',field=['count'],value=1)])]},tmp_path/'field')
    assert result['artifacts'][0]['status']=='failed'


def test_command_receives_empty_output_even_while_logging(tmp_path):
    command=['python','-c',"import pathlib,json; p=pathlib.Path(r'{output}'); assert not list(p.iterdir()); (p/'result.json').write_text(json.dumps({'empty_at_start':True}))"]
    result=reproduce({'artifacts':[dict(id='fresh',command=command,claims=[dict(path='result.json',field=['empty_at_start'],value=True)])]},tmp_path/'out')
    assert result['all_claims_regenerated']
    assert (tmp_path/'out/fresh.command.log').exists()
