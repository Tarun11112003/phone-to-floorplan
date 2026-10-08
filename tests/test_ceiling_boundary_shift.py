import numpy as np
import pytest
from shapely.geometry import Polygon

from scripts.audit_ceiling_boundary_shift import (associate,changed_edges,
    crossing_rays,finite_mask,support_profile)


def test_notch_is_footprint_area_change_with_four_changed_edges():
    before=Polygon([(0,0),(4,0),(4,4),(0,4)])
    after=Polygon([(0,0),(3,0),(3,1),(4,1),(4,4),(0,4)])
    region,rows=changed_edges(before,after)
    assert region.area==1.
    assert len(rows)==4
    assert [r['kind'] for r in rows].count('original')==2
    assert [r['kind'] for r in rows].count('shifted')==2
    assert before.hausdorff_distance(after)==1.


@pytest.mark.parametrize('after',[Polygon([(0,0),(4,0),(4,4),(0,4)]),
    Polygon([(-1,-1),(5,-1),(5,5),(-1,5)])])
def test_no_removed_region_cannot_be_audited_as_the_notch(after):
    with pytest.raises(ValueError):changed_edges(Polygon([(0,0),(4,0),(4,4),(0,4)]),after)


def test_subnanometre_shared_edge_sliver_does_not_enter_the_notch_query():
    before=Polygon([(0,0),(4,0),(4,4),(0,4)])
    after=Polygon([(0,0),(3,0),(3,1),(4-1e-10,1),(4-1e-10,4),(0,4)])
    _,rows=changed_edges(before,after)
    assert len(rows)==4
    assert all(np.linalg.norm(np.diff(row['endpoints'],axis=0))<1.01 for row in rows)


def test_local_support_does_not_borrow_points_from_distant_plane_extent():
    points=np.array([[1,1,1],[1,1.8,1],[1,1,4],[1.1,1,1],[1,1.9,1]])
    mask=finite_mask(points,np.array([1.,0,0]),-1.,[[1,0],[1,2]],2.)
    assert mask.tolist()==[True,False,False,False,False]
    profile=support_profile(points,np.array([1.,0,0]),-1.,[[1,0],[1,2]],2.)
    assert profile['points']==1 and sum(profile['height_histogram'])==1


def test_crossing_rays_need_confident_endpoints_beyond_finite_plane_with_clearance():
    camera=[0,1,1]
    endpoints=np.array([[2,1,1],[.95,1,1],[1.04,1,1],[2,1,7],[0,1,2]])
    mask,hits=crossing_rays(camera,endpoints,np.array([1.,0,0]),-1.,[[1,0],[1,2]],2.)
    assert mask.tolist()==[True,False,False,False,False]
    assert hits.tolist()==[[1.,1.,1.]]


@pytest.mark.parametrize('height',[.1,.25,3.,3.5])
def test_crossings_outside_existing_wall_height_slab_are_excluded(height):
    camera=[0,2-height,1]
    mask,_=crossing_rays(camera,np.array([[2,2-height,1]]),np.array([1.,0,0]),-1.,[[1,0],[1,2]],2.)
    assert not mask.any()


def test_tilted_fitted_plane_does_not_use_an_incorrect_vertical_extrusion():
    normal=np.array([1.,.3,0]);length=np.linalg.norm(normal)
    # At y=1 the true plane is x=.7. A floor-datum vertical x=.4
    # extrusion would falsely count this ray ending at x=.5 as a crossing.
    mask,_=crossing_rays([0,1,1],np.array([[.5,1,1]]),normal/length,-1./length,[[.4,0],[.4,2]],2.)
    assert not mask.any()


@pytest.mark.parametrize('function',[finite_mask,crossing_rays])
def test_degenerate_edge_cannot_supply_support_or_ray_evidence(function):
    args=(np.ones((2,3)),np.array([1.,0,0]),-1.,[[1,0],[1,0]],2.)
    with pytest.raises(ValueError):
        function(*(([0,1,1],)+args if function is crossing_rays else args))


def provenance():
    segment=dict(axis=0,location=1.,lo=0.,hi=4.,plane_line=[1.,0.,-1.],
        plane_line_resolved=True,source_kind='observed_wall')
    plane=dict(normal=[1.,0.,0.],offset=-1.,proposal_source='original measured plane')
    return dict(boundary_network=[segment]),[plane]


def test_network_plane_association_is_exact_and_reports_original_identity():
    meta,planes=provenance()
    result=associate([[1,1],[1,2]],meta,planes,np.eye(3),2.)
    assert result['plane_index']==0 and result['network_index']==0
    assert result['plane']['proposal_source']=='original measured plane'


@pytest.mark.parametrize('failure',['duplicate','coefficient','gap'])
def test_ambiguous_plane_or_unobserved_gap_cannot_supply_wall_provenance(failure):
    meta,planes=provenance()
    if failure=='duplicate':planes=planes*2
    if failure=='coefficient':planes[0]['offset']+=1e-6
    if failure=='gap':meta['boundary_network'][0]['source_kind']='traversed_gap'
    with pytest.raises(ValueError):associate([[1,1],[1,2]],meta,planes,np.eye(3),2.)
