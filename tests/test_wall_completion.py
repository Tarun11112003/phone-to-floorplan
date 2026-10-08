import numpy as np
from shapely.geometry import Polygon
from floorplan.layout import extract_layout, _supported_wall_proposals


def capture(missing=False):
    rng=np.random.default_rng(7); surfaces=[]
    for axis,location,end in [(0,0,3),(0,4,3),(2,0,4),(2,3,4)]:
        if missing and axis==0 and location==4: continue
        points=np.empty((2400,3))
        points[:,axis]=location+rng.normal(0,.002,len(points))
        points[:,2-axis]=rng.uniform(0,end,len(points))
        points[:,1]=rng.uniform(-.8,1.2,len(points))
        surfaces.append(points)
    surfaces.append(np.column_stack([rng.uniform(0,4,4000),np.full(4000,1.5),rng.uniform(0,3,4000)]))
    # Deliberately incomplete global plane selection; raw capture includes walls.
    planes=[dict(normal=[0,1,0],offset=-1.5,support=4000,centroid=[2,1.5,1.5],rms_m=0),
            dict(normal=[1,0,0],offset=0,support=2400,centroid=[0,.2,1.5],rms_m=.002)]
    return np.concatenate(surfaces),planes,np.array([[1,0,1],[2,0,2]])


def test_observed_cross_walls_survive_incomplete_global_plane_selection():
    points,planes,path=capture()
    rooms,metadata=extract_layout(points,planes,path)
    assert len(rooms)==1 and not metadata['unclosed_geometry']
    assert metadata['camera_center_coverage_fraction']==1
    assert len(metadata['wall_plane_proposals'])>=3
    assert abs(Polygon(rooms[0]['corners']).area-12)<.06
    assert rooms[0]['ceiling_height_m'] is None
    stages=metadata['boundary_stages']
    assert stages['accepted_observed_polygons']==1
    assert stages['inferred_fallback_cells']==0
    assert stages['invalid_rings']==0


def test_wall_completion_never_invents_an_unobserved_boundary():
    points,planes,path=capture(missing=True)
    rooms,metadata=extract_layout(points,planes,path)
    assert not rooms and metadata['unclosed_geometry']
    assert metadata['boundary_stages']['accepted_observed_polygons']==0
    assert metadata['boundary_stages']['dangles']>0


def test_projection_modes_reject_a_table_and_a_single_column():
    rng=np.random.default_rng(4)
    table=np.column_stack([np.ones(1500),rng.uniform(.7,1.1,1500),rng.uniform(0,3,1500)])
    column=np.column_stack([np.ones(1500)*2,rng.uniform(-.8,1.2,1500),np.ones(1500)])
    assert not _supported_wall_proposals(np.vstack([table,column]),[],np.eye(3),1.5)


def test_floor_dominated_plane_budget_can_recover_only_observed_wall_directions():
    points,planes,path=capture()
    rooms,metadata=extract_layout(points,planes[:1],path)
    assert len(rooms)==1 and metadata['wall_seed_planes']
    assert not metadata['unclosed_geometry']
    # Floor-only points cannot become vertical structure just to produce a plan.
    import pytest
    with pytest.raises(ValueError,match='vertical walls'):
        extract_layout(points[np.isclose(points[:,1],1.5)],planes[:1],path)


def test_unrelated_property_surfaces_cannot_suppress_the_same_observed_room_walls():
    points,planes,path=capture()
    rng=np.random.default_rng(18)
    # Extra observed horizontal geometry belongs to another part of a property.
    # It changes the global sample fraction, but adds no local wall evidence.
    distant=np.column_stack([rng.uniform(30,40,250000),np.full(250000,1.5),rng.uniform(30,40,250000)])
    proposals=_supported_wall_proposals(np.vstack([points,distant]),planes,np.eye(3),1.5)
    assert len(proposals)>=3
    rooms,metadata=extract_layout(np.vstack([points,distant]),planes,path)
    assert len(rooms)==1 and not metadata['unclosed_geometry']
    assert abs(Polygon(rooms[0]['corners']).area-12)<.06


def test_repeated_corner_clusters_do_not_count_as_observed_wall_surface():
    corners=np.array([[1,h,z] for h in [-.8,1.2] for z in [0,3]])
    points=np.repeat(corners,400,axis=0)
    assert not _supported_wall_proposals(points,[],np.eye(3),1.5)


def test_legacy_support_policy_is_retained_for_controlled_comparison():
    import pytest
    points,planes,_=capture()
    assert _supported_wall_proposals(points,planes,np.eye(3),1.5,support_policy='global_equivalent')
    with pytest.raises(ValueError,match='support policy'):
        _supported_wall_proposals(points,planes,np.eye(3),1.5,support_policy='unknown')


def test_rejected_furniture_peaks_do_not_spend_the_accepted_wall_proposal_budget():
    points,planes,_=capture()
    rng=np.random.default_rng(22)
    furniture=[np.column_stack([np.full(3000,10+i),rng.uniform(.8,1.,3000),rng.uniform(0,3,3000)]) for i in range(16)]
    proposals=_supported_wall_proposals(np.vstack([points,*furniture]),planes,np.eye(3),1.5)
    assert any(abs(abs(p['normal'][0])-1)<.01 and abs(4*p['normal'][0]+p['offset'])<.03 for p in proposals)


def mixed_capture(missing=False):
    """One closed room and a separate room with a measured occluded wall."""
    rng=np.random.default_rng(73); surfaces=[]
    for x0,partial in [(0,False),(6,True)]:
        for axis,location,intervals in [
            (0,x0,[(0,3)]),(0,x0+4,[(0,1),(2,3)] if partial else [(0,3)]),
            (2,0,[(x0,x0+4)]),(2,3,[(x0,x0+4)])]:
            if missing and partial and axis==0 and location==x0+4: continue
            for lo,hi in intervals:
                p=np.empty((2400,3)); p[:,axis]=location+rng.normal(0,.002,len(p))
                p[:,2-axis]=rng.uniform(lo,hi,len(p)); p[:,1]=rng.uniform(-.8,1.2,len(p))
                surfaces.append(p)
        surfaces.append(np.column_stack([rng.uniform(x0,x0+4,4000),np.full(4000,1.5),rng.uniform(0,3,4000)]))
    planes=[dict(normal=[0,1,0],offset=-1.5,support=8000,centroid=[5,1.5,1.5],rms_m=0),
            dict(normal=[1,0,0],offset=0,support=2400,centroid=[0,.2,1.5],rms_m=.002)]
    return np.concatenate(surfaces),planes,np.array([[1,0,1],[2,0,2],[7,0,1],[8,0,2]])


def test_closed_room_does_not_hide_a_separate_supported_partial_cell():
    points,planes,path=mixed_capture()
    rooms,metadata=extract_layout(points,planes,path)
    assert len(rooms)==2
    assert metadata['boundary_stages']['accepted_observed_polygons']==1
    assert metadata['boundary_stages']['inferred_fallback_cells']==1
    assert metadata['camera_center_coverage_fraction']==1
    observed,inferred=rooms
    assert not observed.get('requires_boundary_review',False)
    assert 'boundary_evidence' not in observed
    assert inferred['requires_boundary_review']
    assert inferred['boundary_evidence']['accuracy_validated'] is False
    assert Polygon(observed['corners']).intersection(Polygon(inferred['corners'])).area<=.01
    assert metadata['unclosed_geometry']  # Coverage cannot promote inferred walls.
    assert not metadata['connections'] and not inferred['openings']


def test_mixed_capture_still_rejects_a_wholly_missing_boundary():
    points,planes,path=mixed_capture(missing=True)
    rooms,metadata=extract_layout(points,planes,path)
    assert len(rooms)==1 and not rooms[0].get('requires_boundary_review',False)
    assert metadata['boundary_stages']['inferred_fallback_cells']==0
    assert metadata['camera_center_coverage_fraction']==.5
    assert metadata['unclosed_geometry']


def test_fixed_accepted_plane_quota_cannot_drop_valid_property_wall_modes():
    rng=np.random.default_rng(103)
    walls=[np.column_stack([np.full(1800,float(x))+rng.normal(0,.001,1800),
                            rng.uniform(-.8,1.2,1800),rng.uniform(0,3,1800)])
           for x in range(15)]
    proposals=_supported_wall_proposals(np.vstack(walls),[],np.eye(3),1.5)
    initial=_supported_wall_proposals(np.vstack(walls),[],np.eye(3),1.5,residual_search=False)
    assert proposals[:len(initial)]==initial
    locations=[p['centroid'][0] for p in proposals if abs(p['normal'][0])>.98]
    assert all(any(abs(location-x)<.02 for location in locations) for x in range(15))
    assert all(p['raw_support_points']>=250 and p['occupied_10cm_cells']>=40
               for p in proposals)


def test_residual_search_keeps_short_furniture_rejected_after_initial_quota():
    rng=np.random.default_rng(104)
    walls=[np.column_stack([np.full(900,float(x)),rng.uniform(-.8,1.2,900),rng.uniform(0,3,900)])
           for x in range(10,22)]
    table=np.column_stack([np.full(1800,3.),rng.uniform(.8,1.,1800),rng.uniform(0,3,1800)])
    points=np.vstack([*walls,table])
    proposals=_supported_wall_proposals(points,[],np.eye(3),1.5)
    assert not any(abs(p['centroid'][0]-3)<.02 and abs(p['normal'][0])>.98 for p in proposals)


def masked_sparse_wall(location=-2.73):
    """Synthetic supported mode whose residual consensus spans several bins."""
    rng=np.random.default_rng(109)
    walls=[np.column_stack([np.full(1800,float(x))+rng.normal(0,.001,1800),
                           rng.uniform(-.8,1.2,1800),rng.uniform(0,3,1800)])
           for x in range(12)]
    sparse=np.column_stack([location+rng.normal(0,.012,1200),
                            rng.uniform(-.8,1.2,1200),rng.uniform(0,3,1200)])
    levels=np.linspace(-.6,1.,21)
    planes=[dict(normal=[0,1,0],offset=-float(y),centroid=[5,float(y),1.5],
                 support=500,rms_m=.01) for y in levels]
    return np.vstack([*walls,sparse]),planes


def test_original_supported_exterior_seed_survives_residual_bin_dilution():
    points,planes=masked_sparse_wall()
    proposals=_supported_wall_proposals(points,planes,np.eye(3),1.5)
    recovered=[p for p in proposals if abs(p['centroid'][0]+2.73)<.04]
    assert recovered, 'A supported original mode must not disappear only because residual bins are diluted'
    assert recovered[0]['raw_support_points']>=250
    assert recovered[0]['occupied_10cm_cells']>=40
    assert recovered[0]['rms_m']<=.025


def test_original_seed_replay_retains_prior_proposals_and_does_not_reseed_interior():
    for location in (-2.73,5.5):
        points,planes=masked_sparse_wall(location)
        old=_supported_wall_proposals(points,planes,np.eye(3),1.5,original_seed_search=False)
        new=_supported_wall_proposals(points,planes,np.eye(3),1.5)
        assert new[:len(old)]==old
        if location==5.5:assert new==old


def test_original_seed_cannot_recover_a_plane_without_unexplained_support():
    points,_=masked_sparse_wall()
    # Overlapping known support bands explain the entire height range. The
    # original histogram remains strong, but carries no new residual evidence.
    planes=[dict(normal=[0,1,0],offset=-float(y),centroid=[5,float(y),1.5],
                 support=500,rms_m=.01) for y in np.linspace(-.8,1.2,30)]
    proposals=_supported_wall_proposals(points,planes,np.eye(3),1.5)
    assert not any(abs(p['centroid'][0]+2.73)<.04 for p in proposals)
