from types import SimpleNamespace

import numpy as np
import pytest
from scripts.diagnostics.audit_registration_support import (accepted_associations,collect_candidates,
    fixed_sensor_motion_projection,projection,sensor_ray_point,track_identity_conflicts)


class Point:
    def __init__(self,pid=None): self.point3D_id=pid; self.xy=np.array([10.,20.])
    def has_point3D(self): return self.point3D_id is not None


def fixtures():
    images={1:SimpleNamespace(name='target',points2D=[Point(),Point()],has_pose=False,camera_id=1),
        2:SimpleNamespace(name='source_a',points2D=[Point(7),Point(8)],has_pose=True,camera_id=2),
        3:SimpleNamespace(name='source_b',points2D=[Point(7),Point()],has_pose=True,camera_id=3),
        4:SimpleNamespace(name='future',points2D=[Point(9)],has_pose=False,camera_id=4)}
    references={0:[(2,0),(3,0),(2,1),(4,0)],1:[(3,1)]}
    graph=SimpleNamespace(extract_correspondences=lambda _,k:[SimpleNamespace(image_id=i,point2D_idx=j) for i,j in references[k]])
    camera=SimpleNamespace(has_bogus_params=lambda *_:False)
    model=SimpleNamespace(images=images,cameras={i:camera for i in images})
    options=dict(min_focal_length_ratio=.1,max_focal_length_ratio=10,max_extra_param=1)
    return model,graph,options


def test_candidates_deduplicate_one_landmark_but_preserve_competing_identities():
    model,graph,options=fixtures(); rows,excluded=collect_candidates(model,graph,1,options)
    assert len(rows)==1 and rows[0]['multiple_landmark_identities']
    assert list(rows[0]['landmark_alternatives'])==[7,8]
    assert len(rows[0]['landmark_alternatives'][7])==2
    assert excluded==dict(unregistered_origin=1,origin_without_landmark=1)
    model.images[1].points2D[0]=Point(8)
    assert accepted_associations(model.images[1],rows)=={0:8}


def test_native_bogus_camera_guard_applies_to_candidate_origins():
    model,graph,options=fixtures()
    model.cameras[2]=SimpleNamespace(has_bogus_params=lambda *_:True)
    rows,excluded=collect_candidates(model,graph,1,options)
    assert list(rows[0]['landmark_alternatives'])==[7]
    assert excluded['bogus_origin_camera']==2


@pytest.mark.parametrize('feature,pid',[(0,99),(1,7)])
def test_accepted_identity_without_candidate_support_blocks_audit(feature,pid):
    model,graph,options=fixtures(); rows,_=collect_candidates(model,graph,1,options)
    model.images[1].points2D[feature]=Point(pid)
    with pytest.raises(ValueError,match='absent from native candidate'): accepted_associations(model.images[1],rows)


class Camera:
    def cam_from_img(self,pixel): return np.asarray(pixel,dtype=float)/1000
    def img_from_cam(self,xyz): return np.asarray(xyz)[:2]/xyz[2]*1000


def test_posthoc_ray_intersection_uses_prior_views_and_predicts_heldout_pixel():
    camera=Camera(); point=np.array([.3,.2,5.]); centers=[np.array([-1.,0,0]),np.array([1.,0,0])]
    inputs=[(camera,camera.img_from_cam(point-center),dict(rotation=np.eye(3),center=center)) for center in centers]
    result=sensor_ray_point(inputs)
    np.testing.assert_allclose(result['xyz_m'],point,rtol=1e-12,atol=1e-12)
    assert result['prior_observations']==2 and not result['target_observation_used']
    target_center=np.array([0.,1.,0.])
    value=projection(camera,np.array(result['xyz_m'])-target_center,camera.img_from_cam(point-target_center))
    assert value['positive_depth'] and value['residual_px']==pytest.approx(0,abs=1e-10)


@pytest.mark.parametrize('count',[0,1,2])
def test_unobservable_sensor_ray_geometry_is_reported_without_forcing_fit(count):
    c=Camera(); inputs=[(c,np.zeros(2),dict(rotation=np.eye(3),center=np.array([float(k),0,0]))) for k in range(count)]
    result=sensor_ray_point(inputs)
    assert 'unavailable_reason' in result and 'xyz_m' not in result


def test_sensor_intersection_rotates_rays_instead_of_fitting_camera_poses():
    c=Camera(); point=np.array([0.,0,5.]); rotation=np.array([[0.,-1,0],[1,0,0],[0,0,1]])
    centers=[np.array([-1.,0,0]),np.array([1.,0,0])]
    inputs=[(c,c.img_from_cam(rotation.T@(point-center)),dict(rotation=rotation,center=center)) for center in centers]
    np.testing.assert_allclose(sensor_ray_point(inputs)['xyz_m'],point,atol=1e-12)


@pytest.mark.parametrize('depth',[0,-1])
def test_nonpositive_depth_is_not_counted_as_a_valid_projection(depth):
    camera=SimpleNamespace(img_from_cam=lambda _:pytest.fail('Must not project behind camera'))
    result=projection(camera,np.array([1.,1,depth]),np.zeros(2))
    assert not result['positive_depth'] and result['residual_px'] is None


def test_posthoc_sensor_motion_uses_declared_scale_without_mutating_input():
    point=np.array([.3,.2,5.]); original=point.copy()
    first=dict(rotation=np.eye(3),center=np.zeros(3))
    last=dict(rotation=np.eye(3),center=np.array([1.,0,0]))
    np.testing.assert_allclose(fixed_sensor_motion_projection(point,first,last,2),[-1.7,.2,5])
    np.testing.assert_array_equal(point,original)


def test_conflicting_source_tracks_are_reported_without_discarding_observations():
    observations=[('a',23),('b',6),('a',5)]
    assert track_identity_conflicts(observations)=={'a':[23,5]}
    assert observations==[('a',23),('b',6),('a',5)]
    assert track_identity_conflicts([('a',23),('b',6)])=={}
