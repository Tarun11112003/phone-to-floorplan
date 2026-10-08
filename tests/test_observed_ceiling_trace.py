import sys

import numpy as np
import pytest
from shapely.geometry import Polygon

from floorplan import layout
from scripts.trace_observed_ceiling import (fingerprint, horizontal_inventory,
    native_trace, plane_decisions)


def fixture():
    poly = Polygon([(0, 0), (4, 0), (4, 3), (0, 3)])
    x, z = np.meshgrid(np.linspace(.1, 3.9, 40), np.linspace(.1, 2.9, 30))
    points = np.column_stack([x.ravel(), np.zeros(x.size), z.ravel()])
    points.setflags(write=False)
    return poly, points, np.eye(3), [[2., 1.5, -1.5]]


def plane(normal=(0, 1, 0), offset=0, rms=.002):
    return dict(normal=list(normal), offset=offset, rms_m=rms)


def test_inline_guard_evaluation_is_not_itself_a_rejection():
    poly, points, basis, cameras = fixture()
    planes = [plane((1, 0, 0)), plane()]
    result = native_trace(layout._observed_floor, poly, points, planes, basis, cameras,
                          reference_floor=0.)
    decisions = plane_decisions(result, planes)
    assert decisions[0]['native_rejection']['rejected_by_native_condition'].startswith('abs(normal')
    assert decisions[1]['native_rejection'] is None
    assert result['value'][0] == 0.
    assert result['value'][1]['coverage_fraction'] > .25


@pytest.mark.parametrize('case, expected', [
    ('orientation', 'abs(normal[1])<.97 or plane.get(\'rms_m\',1)>.03'),
    ('rms', 'abs(normal[1])<.97 or plane.get(\'rms_m\',1)>.03'),
    ('camera_height', 'level<=camera_y+.3'),
    ('reference_level', 'reference_floor is not None and abs(level-reference_floor)>.04'),
    ('coverage', 'coverage<.25'),
])
def test_floor_trace_records_only_the_taken_native_branch(case, expected):
    poly, points, basis, cameras = fixture()
    selected = plane()
    if case == 'orientation': selected = plane((1, 0, 0))
    if case == 'rms': selected = plane(rms=.031)
    if case == 'camera_height': selected = plane(offset=2.5)
    if case == 'reference_level': selected = plane(offset=.05)
    if case == 'coverage': points = points[(points[:, 0] < .7) & (points[:, 2] < .7)]
    result = native_trace(layout._observed_floor, poly, points, [selected], basis, cameras,
                          reference_floor=0.)
    decisions = plane_decisions(result, [selected])
    assert decisions[0]['native_rejection']['rejected_by_native_condition'] == expected
    assert result['value'] == [None, None]


def test_unavailable_floor_exits_before_any_ceiling_plane_is_considered():
    poly, points, basis, cameras = fixture()
    result = native_trace(layout._observed_ceiling, poly, points, [plane(offset=2.5)], basis,
                          cameras, floor=None)
    assert result['value'] == [None, None]
    assert all(row['plane_index'] is None for row in result['events'])
    assert any(row.get('floor', 1) is None for row in result['events'])


@pytest.mark.parametrize('case, expected', [
    ('orientation', 'abs(normal[1])<.97 or plane.get(\'rms_m\',1)>.03'),
    ('height', 'not 1.8<=height<=5.0 or level>camera_y-.5'),
    ('coverage', 'coverage<.25'),
])
def test_multiline_ceiling_guard_trace_keeps_existing_decisions(case, expected):
    poly, points, basis, cameras = fixture()
    points = points.copy(); points[:, 1] = -2.5
    selected = plane(offset=2.5)
    if case == 'orientation': selected = plane((1, 0, 0))
    if case == 'height': selected = plane(offset=1.)
    if case == 'coverage': points = points[(points[:, 0] < .7) & (points[:, 2] < .7)]
    result = native_trace(layout._observed_ceiling, poly, points, [selected], basis, cameras, floor=0.)
    decisions = plane_decisions(result, [selected])
    assert decisions[0]['native_rejection']['rejected_by_native_condition'] == expected
    assert result['value'] == [None, None]


def test_trace_matches_native_accepted_ceiling_and_preserves_every_input():
    poly, points, basis, cameras = fixture()
    points = points.copy(); points[:, 1] = -2.5; points.setflags(write=False)
    planes = [plane(offset=2.5)]
    before = fingerprint(poly, points, planes, basis, cameras)
    expected = layout._observed_ceiling(poly, points, planes, basis, 0., cameras)
    result = native_trace(layout._observed_ceiling, poly, points, planes, basis, cameras, floor=0.)
    assert result['value'] == list(expected)
    assert plane_decisions(result, planes)[0]['native_rejection'] is None
    assert fingerprint(poly, points, planes, basis, cameras) == before
    assert sys.gettrace() is None


def test_trace_restores_hook_after_native_failure():
    poly, points, basis, cameras = fixture()
    with pytest.raises(KeyError):
        native_trace(layout._observed_floor, poly, points, [dict(offset=0)], basis, cameras)
    assert sys.gettrace() is None


def test_preexisting_trace_hook_is_never_replaced():
    poly, points, basis, cameras = fixture()
    def existing(frame, event, arg): return existing
    sys.settrace(existing)
    try:
        with pytest.raises(ValueError, match='existing debugger'):
            native_trace(layout._observed_floor, poly, points, [plane()], basis, cameras)
        assert sys.gettrace() is existing
    finally:
        sys.settrace(None)


def test_supplementary_support_inventory_does_not_infer_ceiling_or_borrow_floor():
    poly, points, basis, cameras = fixture()
    points = points.copy(); points[:, 1] = -2.5; points.setflags(write=False)
    planes = [plane(offset=2.5)]
    result = native_trace(layout._observed_floor, poly, points, planes, basis, cameras, reference_floor=0.)
    inventory = horizontal_inventory(poly, points, plane_decisions(result, planes))
    assert result['value'] == [None, None]
    assert len(inventory) == 1 and inventory[0]['points_in_finite_room'] == len(points)
    assert inventory[0]['plane_above_camera']
    assert not inventory[0]['reached_by_observed_ceiling']
    assert not inventory[0]['ceiling_height_inferred']
