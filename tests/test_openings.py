import numpy as np
import pytest

from floorplan.openings import detect_wall_openings
from floorplan.damage import merge_surface_regions,inspection_scope


def wall_views(through=True):
    u,h=np.meshgrid(np.arange(0,4,.02),np.arange(0,2.5,.02))
    hole=(u>1)&(u<2)&(h<2)
    wall=np.column_stack([u[~hole],-h[~hole],np.zeros((~hole).sum())])
    u,h=np.meshgrid(np.arange(1.04,1.96,.02),np.arange(.04,1.96,.02))
    intersections=np.column_stack([u.ravel(),-h.ravel(),np.zeros(u.size)])
    views=[]
    for camera in (np.array([1.6,-1.2,-1.]),np.array([2.4,-1.3,-1.])):
        behind=camera+2*(intersections-camera)
        views.append(dict(camera=camera,points=np.concatenate([wall,behind]) if through else wall))
    return views


def test_occupancy_gap_without_observed_through_rays_is_not_an_opening():
    assert detect_wall_openings([[0,0],[4,0]],2.5,0,wall_views(False))==[]


def test_observed_two_view_aperture_has_raw_refined_width_and_height():
    openings=detect_wall_openings([[0,0],[4,0]],2.5,0,wall_views())
    assert len(openings)==1
    assert openings[0]['kind']=='doorway'
    assert openings[0]['width_m']==pytest.approx(1,abs=.04)
    assert openings[0]['height_m']==pytest.approx(2,abs=.04)
    assert detect_wall_openings([[0,0],[4,0]],2.5,0,[wall_views()[0],wall_views()[0]])==[]


def test_crack_scope_uses_centerline_metres_and_views_do_not_duplicate_it():
    observation=dict(surface_id='wall',class_name='crack_candidate',uv_m=[[.1,.02*i] for i in range(30)],evidence_ids=['frame'])
    once=merge_surface_regions([observation]); twice=merge_surface_regions([observation,observation])
    assert twice[0]['length_m']==pytest.approx(once[0]['length_m'])
    assert twice[0]['length_m']==pytest.approx(.58,abs=.04)
    _,scope=inspection_scope(twice)
    assert scope[0]['unit']=='m'
    assert scope[0]['quantity']==twice[0]['length_m']


def test_observed_header_can_dimension_door_without_inventing_a_ceiling():
    from floorplan.openings import augment_room_openings
    room=dict(corners=[[0,0],[4,0],[4,3],[0,3]],ceiling_height_m=None,openings=[])
    metadata=dict(basis_columns_in_input=np.eye(3).tolist(),floor_level_m=0)
    augment_room_openings([room],metadata,wall_views())
    assert room['ceiling_height_m'] is None
    assert len(room['openings'])==1
    assert room['openings'][0]['width_m']==pytest.approx(1,abs=.04)
    assert room['openings'][0]['height_m']==pytest.approx(2,abs=.04)
