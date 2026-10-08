import numpy as np

from scripts.diagnostics.trace_adjoining_span import crossing_rays, span_mask, traversals, x_profile


def test_measured_ray_needs_clearance_and_wall_height_on_both_sides():
    camera = np.array([-1., 0., 4.])
    endpoints = np.array([[-1., 0., 5.], [-1., 0., 4.3], [-1., 0., 4.45],
                          [-1., 3., 5.], [-6., 0., 5.], [-1., 0., 4.]])
    mask, hits = crossing_rays(camera, endpoints, floor=1.)
    assert mask.tolist() == [True, False, False, False, False, False]
    assert np.allclose(hits, [[-1., 0., 4.44]])


def test_traversal_does_not_count_pose_jump_or_break_as_continuous():
    path = np.array([[-1., 4.], [-1., 4.8], [-1., 2.], [-1., 4.8]])
    rows = traversals(path, [0, 30, 60, 90], breaks=[1])
    assert len(rows) == 3
    assert not any(row['continuous_under_existing_guard'] for row in rows)
    assert traversals(path[:2], [0, 30])[0]['continuous_under_existing_guard']


def test_floor_returns_are_not_wall_support_and_profile_does_not_duplicate_edges():
    points = np.array([[-2.73, 0., 4.44], [-.44, 0., 4.44], [-1., .9, 4.44],
                       [-1., 0., 4.7]])
    assert span_mask(points, floor=1.).tolist() == [True, True, False, False]
    assert span_mask(points, floor=1., wall_height=False).tolist() == [True, True, True, False]
    assert sum(row['points'] for row in x_profile(points[:3], floor=1.)) == 3
