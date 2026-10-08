import numpy as np
import pytest

from scripts.diagnostics.audit_transition_tracks import spatial_support, track_audit, triangle_audit


def test_graph_connectivity_does_not_imply_endpoint_feature_track():
    edges = [('a', 'b', np.array([[0, 0]])), ('b', 'c', np.array([[1, 0]]))]
    report = track_audit(edges, ('a', 'c'))
    assert report['tracks'] == 2
    assert report['endpoint_spanning_tracks'] == 0


def test_transitive_conflicting_track_is_not_counted_as_clean():
    edges = [('a', 'b', np.array([[0, 0]])), ('b', 'c', np.array([[0, 0]])),
             ('a', 'c', np.array([[1, 0]]))]
    report = track_audit(edges, ('a', 'c'))
    assert report['conflicting_tracks'] == 1
    assert report['endpoint_spanning_tracks'] == 1
    assert report['clean_endpoint_spanning_tracks'] == 0


def test_conflict_pixel_spread_distinguishes_near_duplicate_features():
    edges = [('a', 'b', np.array([[0, 0]])), ('b', 'c', np.array([[0, 0]])),
             ('a', 'c', np.array([[1, 0]]))]
    coordinates = dict(a=np.array([[0.,0.],[500.,10.]]), b=np.zeros((1,2)), c=np.zeros((1,2)))
    report = track_audit(edges, ('a','c'), coordinates)
    assert report['conflicting_tracks_separated_over_12px'] == 1
    assert report['endpoint_track_conflict_details'][0]['same_image_separation_lower_bound_px'] == 500
    coordinates['a'][1] = [1.,1.]
    assert track_audit(edges, ('a','c'), coordinates)['conflicting_tracks_separated_over_4px'] == 0


def test_triangle_detects_exact_keypoint_identity_contradiction():
    edges = [('a', 'b', np.array([[0, 0], [1, 1]])),
             ('b', 'c', np.array([[0, 0], [1, 1]])), ('a', 'c', np.array([[0, 0], [1, 2]]))]
    report = triangle_audit(edges)
    assert report['directly_testable'] == 2
    assert report['agreeing'] == 1
    assert report['conflicting'] == 1


def test_non_unique_pair_indices_fail_closed():
    with pytest.raises(ValueError, match='one-to-one'):
        triangle_audit([('a', 'b', np.array([[0, 0], [0, 1]]))])


def test_spatial_support_uses_original_image_dimensions():
    report = spatial_support([[0, 0], [50, 0], [0, 50]], (100, 100))
    assert report['hull_image_fraction'] == pytest.approx(.125)
    assert report['occupied_8x8_cells'] == 3
    with pytest.raises(ValueError, match='pixel coordinates'):
        spatial_support([[100, 10]], (100, 100))
