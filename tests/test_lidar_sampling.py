import numpy as np
import pytest

from scripts.experiments.experimental_lidar_sampling import compare_rooms, rooms_in_source_frame, sample_depth


def test_stride4_adds_valid_pixels_without_removing_stride8_evidence():
    raw = np.full((24,32),2000,dtype=np.uint16)
    confidence = np.full(raw.shape,2,dtype=np.uint8)
    k = np.array([[200.,0,16.],[0,180.,12.],[0,0,1.]])
    a,wa,pa = sample_depth(raw,confidence,k,1000.,1,8.,8)
    b,wb,pb = sample_depth(raw,confidence,k,1000.,1,8.,4)
    rows = {tuple(p):i for i,p in enumerate(pb)}
    ids = [rows[tuple(p)] for p in pa]
    assert len(b) == 4*len(a)
    assert np.array_equal(a,b[ids]) and np.array_equal(wa,wb[ids])


def test_sampling_preserves_confidence_range_units_and_per_frame_calibration():
    raw = np.zeros((16,16),dtype=np.uint16)
    confidence = np.ones(raw.shape,dtype=np.uint8)
    raw[0,0]=2000;confidence[0,0]=0
    raw[0,4]=100;raw[0,8]=9000;raw[4,4]=2000;confidence[4,4]=2
    camera = np.array([[100.,0,8.],[0,200.,8.],[0,0,1.]])
    points,weights,pixels = sample_depth(raw,confidence,camera,1000.,1,8.,4)
    assert pixels.tolist() == [[4,4]]
    assert points.tolist() == [[-.08,-.04,2.]]
    assert weights.tolist() == [.75]


@pytest.mark.parametrize('stride',[0,1,2,3,True])
def test_unplanned_stride_policy_is_rejected(stride):
    with pytest.raises(ValueError):
        sample_depth(np.ones((8,8)),np.ones((8,8)),np.eye(3),1000.,1,8.,stride)


@pytest.mark.parametrize('scale',[0.,-1.,np.inf,np.nan])
def test_invalid_depth_units_are_rejected(scale):
    with pytest.raises(ValueError):
        sample_depth(np.ones((8,8)),np.ones((8,8)),np.eye(3),scale,1,8.,4)


def test_confidence_dimension_mismatch_is_rejected():
    with pytest.raises(ValueError):
        sample_depth(np.ones((8,8)),np.ones((4,4)),np.eye(3),1000.,1,8.,4)


def test_room_comparison_discloses_boundary_motion_without_an_accuracy_pass():
    before = [dict(id='old',corners=[[0,0],[2,0],[2,2],[0,2]])]
    after = [dict(id='new',corners=[[0,0],[3,0],[3,2],[0,2]],requires_boundary_review=True)]
    row = compare_rooms(before,after)[0]
    assert not row['corners_exact'] and row['boundary_hausdorff_m'] == 1.
    assert row['candidate_inferred'] and row['source_area_retained_fraction'] == 1.
    assert 'accuracy_pass' not in row


def test_disappearing_room_is_not_marked_retained():
    assert compare_rooms([dict(id='old',corners=[[0,0],[2,0],[2,2],[0,2]])],[]) == [
        dict(source_room='old',retained=False)]


def test_known_axis_sign_change_is_removed_without_fitting_scale_or_pose():
    before=[dict(id='old',corners=[[1,2],[3,2],[3,4],[1,4]])]
    flipped=[dict(id='new',corners=[[-1,-2],[-3,-2],[-3,-4],[-1,-4]])]
    meta=dict(basis_columns_in_input=np.eye(3).tolist(),wall_sampling_slab_bound_m=1.5)
    new_meta={**meta,'basis_columns_in_input':np.diag([-1.,1.,-1.]).tolist()}
    common=rooms_in_source_frame(flipped,meta,new_meta)
    comparison=compare_rooms(before,common)[0]
    assert comparison['corners_exact'] and comparison['boundary_hausdorff_m']==0.
    assert comparison['intersection_over_union']==1.


def test_known_transform_preserves_actual_dimension_change():
    before=[dict(id='old',corners=[[1,2],[3,2],[3,4],[1,4]])]
    larger=[dict(id='new',corners=[[-1,-2],[-4,-2],[-4,-4],[-1,-4]])]
    meta=dict(basis_columns_in_input=np.eye(3).tolist(),wall_sampling_slab_bound_m=1.5)
    candidate={**meta,'basis_columns_in_input':np.diag([-1.,1.,-1.]).tolist()}
    comparison=compare_rooms(before,rooms_in_source_frame(larger,meta,candidate))[0]
    assert not comparison['corners_exact'] and comparison['boundary_hausdorff_m']==1.


def test_invalid_transform_blocks_boundary_comparison():
    meta=dict(basis_columns_in_input=np.eye(3).tolist(),wall_sampling_slab_bound_m=np.nan)
    with pytest.raises(ValueError):
        rooms_in_source_frame([],meta,meta)
