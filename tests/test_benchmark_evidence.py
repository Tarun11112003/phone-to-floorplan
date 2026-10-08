from copy import deepcopy
import json

import pytest

from floorplan.assessment import build_assessment
from floorplan.benchmark_manifest import audit_manifest
from floorplan.consumer_comparison import compare_consumer
from floorplan.provenance import sha256


def test_template_has_three_rooms_plus_separate_connector_but_is_not_evidence(tmp_path):
    from pathlib import Path
    template=json.loads((Path(__file__).parents[1]/'docs/benchmark/benchmark_manifest.template.json').read_text())
    result=audit_manifest(template,tmp_path)
    assert not result['metadata_ready']
    assert not result['accuracy_validated']
    assert 'REQ-19' not in {r['requirement'] for r in result['issues']}
    assert {'REQ-23','REQ-38','REQ-22'}<={r['requirement'] for r in result['issues']}


def test_benchmark_split_leakage_and_escaped_assets_are_rejected(tmp_path):
    result=audit_manifest(dict(split={'development_property_ids':['same'],'held_out_property_ids':['same']},properties=[]),tmp_path)
    assert any('overlap' in r['message'] for r in result['issues'])
    doc=dict(properties=[dict(property_id='p',rooms=[],captures=[dict(capture_id='one',tier='video',raw_files_sha256={'../outside':'hash'})])])
    with pytest.raises(ValueError,match='escapes'): audit_manifest(doc,tmp_path)


def comparison_fixture(tmp_path):
    plan=dict(rooms=[dict(id='a',corners=[[0,0],[4,0],[4,3],[0,3]],ceiling_height_m=2.5),
                    dict(id='b',corners=[[4,0],[7,0],[7,3],[4,3]],ceiling_height_m=2.5)])
    ledger=dict(configuration={'property_id':'p'},manifest_sha256='a'*64,run_id='one',tier='lidar',result={'status':'partial'})
    assessment=build_assessment(plan,ledger)
    export=tmp_path/'actual_export.pdf'; export.write_bytes(b'test fixture, not a real consumer export')
    mapping=dict(property_id='p',app_name='test app',app_version='test',device_model='test Pro',
                 export_sha256=sha256(export),room_ids=['a','b'],dimensions=[
                     dict(room_id='a',dimension_id='wall1',measurement_id='room:a:wall:0:length',reference_m=4),
                     dict(room_id='b',dimension_id='wall1',measurement_id='room:b:wall:0:length',reference_m=3)])
    dimensions={('a','wall1'):4.02,('b','wall1'):3.02}
    return assessment,dimensions,mapping,export


def test_consumer_requires_lidar_two_rooms_and_original_export(tmp_path):
    assessment,dimensions,mapping,export=comparison_fixture(tmp_path)
    result=compare_consumer(assessment,dimensions,mapping,export)
    assert result['gate']=='pass' and result['fraction_beat_or_tie']==1
    del dimensions[('b','wall1')]
    assert compare_consumer(assessment,dimensions,mapping,export)['gate']=='fail'
    assessment['tier']='photos'
    with pytest.raises(ValueError,match='LiDAR'): compare_consumer(assessment,dimensions,mapping,export)
    assessment['tier']='lidar'; mapping['export_sha256']='wrong'
    with pytest.raises(ValueError,match='checksum'): compare_consumer(assessment,dimensions,mapping,export)


def test_unmapped_consumer_dimensions_cannot_be_cherry_picked(tmp_path):
    assessment,dimensions,mapping,export=comparison_fixture(tmp_path)
    dimensions[('a','other_wall')]=3.1
    result=compare_consumer(assessment,dimensions,mapping,export)
    assert result['gate']=='fail'
    assert result['unmapped_consumer_dimensions']==[('a','other_wall')]


def test_unverified_capture_and_consumer_hashes_cannot_count_as_evidence(tmp_path):
    (tmp_path/'raw').write_bytes(b'capture')
    (tmp_path/'app.pdf').write_bytes(b'export')
    doc={'properties':[dict(property_id='p',rooms=[],captures=[dict(capture_id='one',tier='video',
        raw_files_sha256={'raw':'wrong','absent':'missing'})],consumer_comparison={'raw_files_sha256':{'app.pdf':'wrong'}})]}
    result=audit_manifest(doc,tmp_path)
    assert not result['verified_capture_ids']
    assert any('consumer export' in row['message'] for row in result['issues'])
