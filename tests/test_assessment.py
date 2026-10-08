import numpy as np
import pytest
import json

from floorplan.assessment import build_assessment, write_assessment
from floorplan.damage import segment_wall_candidates,merge_surface_regions,inspection_scope
from floorplan.uncertainty import fit_calibration,calibrated_interval


def test_missing_height_stays_unavailable_and_all_walls_have_intervals():
    ledger=dict(configuration={},manifest_sha256='a'*64,run_id='one',tier='lidar',result={'status':'partial'})
    plan=dict(rooms=[dict(id='r',corners=[[0,0],[4,0],[4,3],[0,3]],ceiling_height_m=None)])
    result=build_assessment(plan,ledger)
    walls=[m for m in result['measurements'] if m['kind']=='length']
    assert len(walls)==4 and all(m['interval'] is not None for m in walls)
    height=next(m for m in result['measurements'] if m['kind']=='ceiling_height')
    assert height['value'] is None and height['interval'] is None
    assert result['damage_assessment_status']=='not_evaluated'


def test_capture_report_exposes_photo_matching_guidance(tmp_path):
    diagnostics={
        'candidate_image_pairs':1,
        'geometrically_verified_pair_count':0,
        'max_verified_inliers':0,
        'median_verified_inliers':0.0,
        'images_without_verified_pairs':['room__00.png','room__01.png'],
        'strongest_verified_pairs':[],
    }
    ledger=dict(configuration={},manifest_sha256='a'*64,run_id='one',tier='photos',result={
        'status':'no_model',
        'matching_diagnostics':diagnostics,
        'reconstruction_guidance':'No image pair passed geometric verification.',
    })
    output=tmp_path/'result'; output.mkdir()

    write_assessment(output,ledger,assessment=build_assessment(None,ledger))

    report=(output/'report.html').read_text(encoding='utf-8')
    assert 'Photo-matching diagnostics' in report
    assert 'No image pair passed geometric verification.' in report
    assert '0 of 1' in report
    assert 'room__00.png' in report
    assert 'Assignment output coverage' in report
    assert 'contract_coverage.json' in report
    coverage=json.loads((output/'contract_coverage.json').read_text(encoding='utf-8'))
    states={item['key']:item['status'] for item in coverage['items']}
    assert states['dimensioned_room_plans']=='not_produced'
    assert states['published_json_schema']=='pending_external_spec'
    assert states['measurement_intervals']=='incomplete'
    assert coverage['accuracy_validated'] is False


def test_experimental_detector_staged_marks_and_clean_control():
    image=np.full((200,240,3),220,np.uint8)
    mask=np.ones((200,240),bool)
    assert segment_wall_candidates(image,mask)==[]
    image[30:70,30:80]=[160,115,55]
    image[100:175,150:153]=[35,35,35]
    labels={r['class_name'] for r in segment_wall_candidates(image,mask)}
    assert labels=={'water_stain_candidate','crack_candidate'}
    # Color marks outside observed wall geometry cannot become surface damage.
    assert segment_wall_candidates(image,np.zeros_like(mask))==[]


def test_duplicate_views_do_not_double_count_damage_scope():
    points=[[.1,.1],[.12,.1],[.1,.12],[.12,.12]]
    observation=dict(surface_id='wall',class_name='water_stain_candidate',uv_m=points,evidence_ids=['frame:1'])
    once=merge_surface_regions([observation]); twice=merge_surface_regions([observation,observation])
    assert once[0]['area_m2']==twice[0]['area_m2']
    flags,scope=inspection_scope(twice)
    assert len(scope)==1 and scope[0]['surface_id']=='wall'
    assert flags[0]['concealed_damage_observed'] is False


def test_calibration_respects_independent_properties_and_rejects_leakage():
    records=[dict(property_id=f'p{i}',tier='lidar',kind='length',unit='m',estimate=3+.001*i,reference=3)
             for i in range(20)]
    calibration=fit_calibration(records)
    interval=calibrated_interval(4,'lidar','length','m','held_out',calibration)
    assert interval['calibrated'] and interval['lower']<4<interval['upper']
    with pytest.raises(ValueError,match='development property'):
        calibrated_interval(4,'lidar','length','m','p0',calibration)
    # Twenty walls of the same room are not twenty independent properties.
    for record in records: record['property_id']='one'
    assert fit_calibration(records)['groups']['lidar:length:m']['radius'] is None
