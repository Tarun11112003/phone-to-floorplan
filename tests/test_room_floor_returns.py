import json
import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from floorplan import layout
from scripts.audit_room_floor_returns import (aggregate_into, cell_keys, clipped_coverage,
    finish_aggregate, fusion_lineage, pixel_masks, raw_calibration, summarize_frame, support_mask)


POLY = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
NORMAL = np.array([0., 1., 0.])


def test_original_depth_confidence_and_stride_are_separate():
    depth = np.full((9, 9), 1000, dtype=np.uint16)
    depth[0, 0] = 0; depth[0, 8] = 199; depth[8, 0] = 8001
    confidence = np.full(depth.shape, 2, dtype=np.uint8); confidence[8, 8] = 0
    z, valid, accepted, lattice = pixel_masks(depth, confidence, 1000)
    assert valid.sum() == 78 and accepted.sum() == 77
    assert lattice.sum() == 4 and (accepted & lattice).sum() == 0
    assert z[1, 1] == 1. and (accepted & ~lattice).sum() == 77


def test_inclusive_range_and_nonfinite_rejection():
    depth = np.array([[.2, 8., .199, 8.001, np.nan, np.inf]])
    _, valid, accepted, _ = pixel_masks(depth, np.ones_like(depth), 1)
    assert valid.tolist() == [[True, True, False, False, False, False]]
    assert np.array_equal(valid, accepted)


@pytest.mark.parametrize('scale', [0, -1, np.nan])
def test_invalid_scale_rejected(scale):
    with pytest.raises(ValueError): pixel_masks(np.ones((2, 2)), np.ones((2, 2)), scale)


def test_depth_confidence_shape_must_match():
    with pytest.raises(ValueError): pixel_masks(np.ones((2, 2)), np.ones((2, 1)), 1)


def test_strict_plane_band_and_native_room_buffer():
    points = np.array([[.5, .034, .5], [.5, .035, .5], [-.04, 0, .5], [-.06, 0, .5]])
    expected = [abs(p @ NORMAL) < .035 and POLY.buffer(.05).covers(Point(p[0], p[2])) for p in points]
    assert support_mask(points, NORMAL, 0, POLY).tolist() == expected == [True, False, True, False]


def test_cell_clipping_preserves_concavity_and_negative_cells():
    poly = Polygon([(0, 0), (1, 0), (1, .4), (.4, .4), (.4, 1), (0, 1)])
    cells = {(-1, 0), (0, 0), (3, 3)}
    result = clipped_coverage(poly, cells)
    assert result['occupied_cells'] == 3
    assert result['clipped_area_m2'] == pytest.approx(.04)
    assert result['coverage_fraction'] == pytest.approx(.04 / poly.area)


def test_confidence_exclusions_and_heldout_pixels_have_distinct_counts():
    points = np.array([[.1, 0, .1], [.3, 0, .3], [.5, 0, .5], [.7, .1, .7]])
    stats, _, _ = summarize_frame(points, np.array([0, 1, 2, 2]),
        np.array([True, True, False, False]), NORMAL, 0, POLY)
    assert {key: value['points'] for key, value in stats.items()} == dict(
        in_range=3, accepted=2, confidence2=1, stride8=1, off_lattice=1, confidence_rejected=1)
    assert stats['accepted']['cells'] == {(1, 1), (2, 2)}


def test_aggregate_counts_repeats_but_unions_cells_without_inventing_coverage():
    aggregate = {}
    frame = dict(accepted=dict(points=2, cells={(0, 0)}))
    aggregate_into(aggregate, frame); aggregate_into(aggregate, frame)
    result = finish_aggregate(aggregate, POLY)['accepted']
    assert result['points'] == 4 and result['frames_with_support'] == 2
    assert result['occupied_cells'] == 1 and result['coverage_fraction'] == pytest.approx(.04)


def test_cell_evidence_is_json_serializable():
    cells = cell_keys(np.array([[.1, 0., .1], [-.1, 0., .1]]))
    record = clipped_coverage(POLY, cells)
    assert json.loads(json.dumps(record)) == record


def test_occupancy_agrees_with_native_helper_when_point_minimum_passes():
    points = np.tile([[.1, 0, .1], [.3, 0, .3]], (60, 1))
    support = support_mask(points, NORMAL, 0, POLY)
    result = clipped_coverage(POLY, cell_keys(points[support]))
    assert layout._horizontal_support(POLY, points, NORMAL, 0) == (120, result['coverage_fraction'])


def test_native_minimum_points_is_not_replaced_by_dense_cell_inventory():
    points = np.array([[.1, 0, .1]])
    assert clipped_coverage(POLY, cell_keys(points))['coverage_fraction'] > 0
    assert layout._horizontal_support(POLY, points, NORMAL, 0) == (1, 0.)


def test_global_voxel_averaging_support_loss_is_attributed_without_refitting():
    samples = np.array([[.1, .034, .1], [.1, .039, .1]])
    weights = np.ones(2); frozen, _, total = layout.weighted_voxels(samples, weights=weights)
    report, contributors = fusion_lineage(samples, weights, np.array([True, False]),
        frozen, total, np.eye(3), NORMAL, 0, POLY)
    assert report['checks'] == dict(points_bit_identical=True, weights_bit_identical=True)
    assert report['floor_voxels_lost'] == 1 and report['floor_voxels_gained'] == 0
    assert report['lost_voxel_witnesses'][0]['fused_signed_residual_m'] == pytest.approx(.0365)
    assert not contributors.any()


def test_fusion_replay_requires_exact_points_and_weights():
    samples = np.array([[.1, 0, .1]])
    with pytest.raises(ValueError, match='replay failed'):
        fusion_lineage(samples, np.ones(1), np.array([True]), samples, np.array([2.]),
                       np.eye(3), NORMAL, 0, POLY)


def test_per_frame_intrinsics_scaled_from_rgb_and_optical_pose_used_directly():
    row = dict(fx='1500', fy='1400', cx='960', cy='720', qx='0', qy='0', qz='0', qw='1',
               x='1', y='2', z='3')
    camera, k, pose = raw_calibration(row, (192, 256), (1920, 1440))
    assert camera == dict(fx=200., fy=1400*192/1440, cx=128., cy=96.)
    assert np.array_equal(k[2], [0, 0, 1])
    assert np.array_equal(pose[:3, :3], np.eye(3))
    assert np.array_equal(pose[:3, 3], [1, 2, 3])
