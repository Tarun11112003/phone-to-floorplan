from types import SimpleNamespace

import numpy as np
import pytest
from scripts.diagnostics.audit_late_landmarks import (acute_triangulation_angle,directed_matches,
    fundamental,local_triangles,native_status,pose_condition,sampson_residuals,shape_diagnostics)


def test_triangulation_angle_is_scale_rotation_and_translation_invariant():
    point=np.array([0.,0.,10.]); a=np.array([-1.,0.,0.]); b=np.array([1.,0.,0.])
    expected=np.degrees(2*np.arctan(.1))
    assert acute_triangulation_angle(point,a,b)==pytest.approx(expected)
    rotation=np.array([[0.,-1,0],[1,0,0],[0,0,1]])
    transform=lambda p: 7*rotation@p+np.array([3,4,5])
    assert acute_triangulation_angle(*(transform(p) for p in (point,a,b)))==pytest.approx(expected)
    assert acute_triangulation_angle(a,a,b) is None


def test_reversed_camera_order_transposes_fundamental_and_preserves_residuals():
    K=np.array([[1000.,0,500],[0,1000,400],[0,0,1.]])
    a=dict(center=np.zeros(3),rotation=np.eye(3))
    b=dict(center=np.array([1.,0,0]),rotation=np.eye(3))
    F=fundamental(a,b,K,K)
    np.testing.assert_allclose(fundamental(b,a,K,K),F.T)
    x=np.array([[500.,400],[600,420]]);y=np.array([[400.,400],[500,423]])
    result=sampson_residuals(F,x,y)
    assert result[0]==pytest.approx(0.)
    assert result[1]==pytest.approx(3/np.sqrt(2))
    assert sampson_residuals(F.T,y,x)==pytest.approx(result)
    assert sampson_residuals(np.zeros((3,3)),x,y)==[None,None]


def test_pair_direction_preserves_original_feature_indices_and_zero_rows():
    rows=[(2*2147483647+7,2,2,np.array([[4,9],[5,11]],np.uint32).tobytes()),
          (2*2147483647+8,0,2,b'')]
    pairs=directed_matches(rows,{2:'a',7:'b',8:'c'})
    np.testing.assert_array_equal(pairs['b','a'],[[9,4],[11,5]])
    assert pairs['a','c'].shape==pairs['c','a'].shape==(0,2)


def test_triangle_conflict_names_the_composed_feature_without_labeling_ground_truth():
    verified={('a','c'):{1:3},('c','b'):{3:8},('a','d'):{1:4},('d','b'):{4:9}}
    result=local_triangles('a','b',1,8,verified)
    assert result['agreeing']==[dict(via='c',feature_via=3,feature_b_composed=8)]
    assert result['conflicting']==[dict(via='d',feature_via=4,feature_b_composed=9)]
    assert local_triangles('a','b',999,8,verified)==dict(agreeing=[],conflicting=[])


def test_raw_identity_conflict_is_not_the_same_as_saved_point_membership():
    class Point:
        def __init__(self,pid): self.point3D_id=pid
        def has_point3D(self): return self.point3D_id is not None
    a=SimpleNamespace(points2D=[Point(12),Point(None)])
    b=SimpleNamespace(points2D=[Point(12),Point(13),Point(None)])
    assert native_status(a,0,b,0)=='shared_saved_point'
    assert native_status(a,0,b,1)=='different_saved_points'
    assert native_status(a,0,b,2)=='only_a_saved'
    assert native_status(a,1,b,0)=='only_b_saved'
    assert native_status(a,1,b,2)=='neither_saved'


def test_shape_diagnostic_distinguishes_plane_from_volume_without_threshold():
    plane=np.array([[0.,0,0],[1,0,0],[0,1,0],[1,1,0]])
    assert shape_diagnostics(plane)['smallest_over_middle']==pytest.approx(0)
    volume=np.vstack([plane,[0,0,1]])
    before=shape_diagnostics(volume)
    after=shape_diagnostics(7*volume+np.array([3,4,5]))
    assert before['smallest_over_middle']==pytest.approx(after['smallest_over_middle'])
    assert before['smallest_over_middle']>0
    assert 'unavailable_reason' in shape_diagnostics([[0,0,0]])


def test_projection_condition_normalizes_model_scale_and_rejects_invalid_depth():
    points=np.array([[-1.,-1,5],[1,-1,6],[-1,1,7],[1,1,8],[0,0,9]])
    K=np.diag([1000.,1000.,1.])
    before=pose_condition(points,K);after=pose_condition(points*10,K)
    assert before['condition_number']==pytest.approx(after['condition_number'])
    np.testing.assert_allclose(before['singular_values_px'],after['singular_values_px'])
    assert 'unavailable_reason' in pose_condition([[1.,1,0]],K)
