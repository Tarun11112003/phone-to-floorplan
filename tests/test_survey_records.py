import csv
import json
from pathlib import Path

import pytest

from floorplan.assessment import build_assessment
from floorplan.calibration_records import build_records
from floorplan.survey import load_survey
from floorplan.uncertainty import fit_calibration


def write_table(path,records,fields=None):
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields or list(records[0]))
        writer.writeheader(); writer.writerows(records)


def test_blank_survey_template_is_not_accepted_as_measured_evidence():
    directory=Path(__file__).parents[1]/'docs/benchmark/truth'
    with pytest.raises(ValueError,match='populated'): load_survey(directory,'p')


def populate_survey(tmp_path):
    (tmp_path/'evidence.txt').write_text('synthetic test fixture; not physical survey proof')
    metadata=dict(property_id='p',room_id='a',measurement_method='test tape',truth_evidence_path='evidence.txt')
    corners=[[0,0],[4,0],[4,3],[0,3]]
    write_table(tmp_path/'rooms.csv',[dict(**metadata,label='A',corners_xz_json=json.dumps(corners),ceiling_height_m=2.5,floor_area_m2=12)])
    walls=[]
    for index,(start,end) in enumerate(zip(corners,corners[1:]+corners[:1])):
        length=4 if index%2==0 else 3
        walls.append(dict(**metadata,wall_id=f'w{index}',wall_index=index,surface_id=f's{index}',
            start_xyz_m_json=json.dumps([start[0],0,start[1]]),end_xyz_m_json=json.dumps([end[0],0,end[1]]),length_m=length+.01,height_m=2.5))
    write_table(tmp_path/'walls.csv',walls)
    write_table(tmp_path/'openings.csv',[],['property_id'])
    write_table(tmp_path/'damage_regions.csv',[],['property_id'])
    write_table(tmp_path/'raw_measurements.csv',[dict(property_id='p',evidence_path='evidence.txt',raw_reading=4.01,unit='m',
        tool_name='test tape',tool_model='fixture',operator_id='test',measured_at_utc='2026-10-07T00:00:00Z')])
    return walls


def test_independent_survey_loader_preserves_raw_wall_readings_and_unavailable_annotations(tmp_path):
    walls=populate_survey(tmp_path)
    result=load_survey(tmp_path,'p')
    assert result['reference']['rooms'][0]['wall_lengths_m']==[4.01,3.01,4.01,3.01]
    assert result['damage_annotations'] is None
    assert not result['reference']['provenance']['physical_identity_verified']
    walls.pop(); write_table(tmp_path/'walls.csv',walls)
    with pytest.raises(ValueError,match='every room wall'): load_survey(tmp_path,'p')


@pytest.mark.parametrize('length',[-1,float('nan')])
def test_survey_rejects_invalid_damage_readings_even_before_matching(tmp_path,length):
    populate_survey(tmp_path)
    region=dict(property_id='p',region_id='d',surface_id='s0',class_name='cracking',
        surface_polygon_uv_m_json=json.dumps([[0,0],[.1,0],[.1,1],[0,1]]),area_m2=.1,
        length_m=length,truth_evidence_path='evidence.txt')
    write_table(tmp_path/'damage_regions.csv',[region])
    with pytest.raises(ValueError,match='length_m'): load_survey(tmp_path,'p')


def test_survey_rejects_duplicate_damage_ids_and_all_excluded_raw_readings(tmp_path):
    populate_survey(tmp_path)
    region=dict(property_id='p',region_id='d',surface_id='s0',class_name='cracking',
        surface_polygon_uv_m_json=json.dumps([[0,0],[.1,0],[.1,1],[0,1]]),area_m2=.1,
        length_m=1,truth_evidence_path='evidence.txt')
    write_table(tmp_path/'damage_regions.csv',[region,region])
    with pytest.raises(ValueError,match='unique'): load_survey(tmp_path,'p')
    write_table(tmp_path/'damage_regions.csv',[],['property_id'])
    write_table(tmp_path/'raw_measurements.csv',[dict(property_id='p',exclusion_reason='test exclusion')])
    with pytest.raises(ValueError,match='nonexcluded'): load_survey(tmp_path,'p')


def test_calibration_records_use_frozen_artifacts_and_do_not_hide_missing_measurements(tmp_path):
    ledger=dict(configuration={'property_id':'p'},manifest_sha256='a'*64,run_id='one',tier='photos',
        result={'status':'partial'},measurement_producer_fingerprint='producer',code_changed_during_run=False)
    assessment=build_assessment(dict(rooms=[dict(id='a',corners=[[0,0],[4,0],[4,3],[0,3]],ceiling_height_m=2.5)]),ledger)
    run=tmp_path/'run'; run.mkdir()
    (run/'run.json').write_text(json.dumps(ledger)); (run/'assessment.json').write_text(json.dumps(assessment))
    reference=dict(property_id='p',measurements=[{**m,'value':m['value']+.01} for m in assessment['measurements']])
    path=tmp_path/'truth.json'; path.write_text(json.dumps(reference))
    result=build_records([dict(run='run',reference='truth.json')],tmp_path)
    assert result['complete']
    assert len(result['records'])==len(assessment['measurements'])
    assert result['sources'][0]['reference_sha256']
    with pytest.raises(ValueError,match='fingerprint'):
        fit_calibration(result['records'],.9,producer_fingerprint='different')
    reference['measurements'].pop(); path.write_text(json.dumps(reference))
    result=build_records([dict(run='run',reference='truth.json')],tmp_path)
    assert not result['complete'] and len(result['issues'])==1
    ledger['code_changed_during_run']=True; (run/'run.json').write_text(json.dumps(ledger))
    with pytest.raises(ValueError,match='unchanged-source'): build_records([dict(run='run',reference='truth.json')],tmp_path)


def test_gate_uses_direct_surveyed_lengths_and_repeatability_preserves_physical_walls():
    from copy import deepcopy
    from floorplan.assignment_gates import evaluate_assignment
    from floorplan.repeatability import evaluate_repeatability
    room=dict(id='a',corners=[[0,0],[4,0],[4,3],[0,3]],ceiling_height_m=2.5,metric_status='sensor_scaled')
    prediction=dict(rooms=[room],connections=[])
    truth=deepcopy(prediction); truth['rooms'][0]['wall_lengths_m']=[4.5,3,4,3]
    gates=evaluate_assignment(prediction,truth,'photos')
    assert gates['walls']['gate']=='fail'
    assert gates['walls']['measurements'][0]['reference_m']==4.5
    other=deepcopy(prediction); other['rooms'][0]['corners'].insert(1,[2,0])
    repeat=evaluate_repeatability(prediction,other,truth)
    assert repeat['wall_repeatability']['gate']=='pass'
