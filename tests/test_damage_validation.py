from copy import deepcopy

import numpy as np
import pytest
from shapely.geometry import box,mapping

from floorplan.damage import camera_faces_surface
from floorplan.damage_evaluation import evaluate_damage


def test_shared_wall_face_is_visible_only_from_its_own_room():
    left=[[0,0],[4,0],[4,3],[0,3]]; right=[[4,0],[7,0],[7,3],[4,3]]
    a=dict(endpoints=[[4,0],[4,3]]); b=dict(endpoints=[[4,3],[4,0]])
    assert camera_faces_surface(a,left,np.array([2,0,1.5]))
    assert not camera_faces_surface(b,right,np.array([2,0,1.5]))
    assert camera_faces_surface(b,right,np.array([5,0,1.5]))
    assert not camera_faces_surface(a,left,np.array([5,0,1.5]))


def fixture():
    region=dict(id='p',surface_id='wall',class_name='water_stain_candidate',surface_geometry=mapping(box(0,0,1,1)))
    reference={**region,'id':'truth','class_name':'water_staining'}
    return dict(property_id='a',damage_regions=[region],damage_assessment_status='experimental_candidates_require_review'),dict(property_id='a',evaluated_surface_ids=['wall','clean'],regions=[reference])


def test_annotation_scoring_counts_misses_phantoms_and_clean_controls():
    assessment,truth=fixture()
    result=evaluate_damage(assessment,truth)
    assert result['matches'][0]['area_absolute_error_m2']==0
    assert result['clean_control_surfaces']==['clean']
    assessment['damage_regions'].append({**deepcopy(assessment['damage_regions'][0]),'id':'phantom','surface_id':'clean'})
    assessment['damage_regions'][0]['class_name']='crack_candidate'
    result=evaluate_damage(assessment,truth)
    assert result['missed_regions']==['truth']
    assert result['phantom_regions']==['p','phantom']
    assert result['classes']['water_staining']['false_negatives']==1
    assert not result['accuracy_validated']


def test_clean_annotation_is_distinct_from_missing_annotation_or_missing_inference():
    assessment,truth=fixture(); truth['regions']=[]; assessment['damage_regions']=[]
    assert evaluate_damage(assessment,truth)['status']=='scored'
    assessment['damage_assessment_status']='not_evaluated'
    assert evaluate_damage(assessment,truth)['status']=='inference_not_evaluated'
    del truth['regions']
    with pytest.raises(ValueError,match='Explicit'): evaluate_damage(assessment,truth)


def test_damage_area_preserves_independent_reading_separately_from_polygon():
    assessment,truth=fixture(); truth['regions'][0]['area_m2']=1.2
    match=evaluate_damage(assessment,truth)['matches'][0]
    assert match['reference_area_m2']==1.2
    assert match['annotation_polygon_area_m2']==1
    assert match['area_absolute_error_m2']==pytest.approx(.2)


def test_unmatched_invalid_damage_lengths_and_duplicate_ids_are_rejected():
    assessment,truth=fixture()
    truth['regions'][0].update(length_m=float('nan'),surface_geometry=mapping(box(3,3,4,4)))
    with pytest.raises(ValueError,match='finite'): evaluate_damage(assessment,truth)
    truth['regions'][0]['length_m']=1
    truth['regions'].append(deepcopy(truth['regions'][0]))
    with pytest.raises(ValueError,match='unique'): evaluate_damage(assessment,truth)


def test_damage_samples_registered_views_before_budget_and_never_raw_pose_fallback(tmp_path):
    import json
    import cv2
    from floorplan.damage import assess_rgbd_damage
    rgb=np.full((48,64,3),230,np.uint8)
    cv2.imwrite(str(tmp_path/'rgb.png'),rgb)
    np.save(tmp_path/'depth.npy',np.full((48,64),1.5))
    pose=np.eye(4); pose[:3,3]=[1,-1,1.5]
    sequence=dict(intrinsics=dict(width=64,height=48,fx=50,fy=50,cx=31.5,cy=23.5),depth_scale=1,
        frames=[dict(id=i,rgb='rgb.png',depth='depth.npy',camera_to_world=pose.tolist()) for i in range(100)])
    (tmp_path/'normalized_sequence.json').write_text(json.dumps(sequence))
    artifacts=tmp_path/'artifacts'; artifacts.mkdir()
    (artifacts/'trajectory.json').write_text(json.dumps([dict(frame_id=50,camera_to_first=pose.tolist())]))
    plan=dict(provenance=dict(floor_level_m=0,basis_columns_in_input=np.eye(3).tolist()))
    assessment=dict(rooms=[dict(id='a',corners=[[0,0],[3,0],[3,3],[0,3]])],
        surfaces=[dict(id='wall',kind='wall',room_id='a',endpoints=[[3,3],[0,3]],height_m=2.5)],measurements=[])
    result=assess_rgbd_damage(plan,tmp_path,assessment)
    assert result['surfaces_evaluated']==['wall']
    assert [e['id'] for e in result['evidence']]==['frame:50']
    (artifacts/'trajectory.json').write_text('[]')
    result=assess_rgbd_damage(plan,tmp_path,assessment)
    assert result['status']=='not_evaluated' and not result['surfaces_evaluated']
