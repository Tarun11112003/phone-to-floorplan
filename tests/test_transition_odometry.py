import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest
from scipy.spatial.transform import Rotation

from scripts.audit_transition_odometry import (direction_error, motion, pixel_witness,
    read_odometry, relative_comparison, run, timing_alignment, verify_retained_summaries)
from floorplan.provenance import sha256


def timing_fixture():
    stamps = np.array([0, .017, .067, .10, .117, .167, .20, .217, .25, .30, .317])
    rows = [dict(timestamp_s=100+s) for s in stamps]
    def timing(times, keyframe):
        return dict(time_base_s=.001, frames=[dict(decoded_index=i, pts=round(t*1000),
                    timestamp_s=round(t*1000)*.001, keyframe=keyframe and i == 0)
                    for i, t in enumerate(times)])
    playback = timing(stamps[1:]-stamps[1], False)
    encoded = timing(stamps, True)
    timeline = [dict(image=f'view{i}.png', source_timestamp_s=playback['frames'][i]['timestamp_s'])
                for i in (0, 2, 5, 8)]
    return playback, encoded, rows, timeline


def test_full_cadence_recovers_playback_offset_without_nearest_sensor_matching():
    result = timing_alignment(*timing_fixture())
    assert result['shifts'] == {'playback': 1, 'encoded': 0}
    assert [v['sensor_frame'] for v in result['views']] == [1, 3, 6, 9]
    assert result['comparisons']['playback'][0]['timestamp_consistent'] is False
    assert result['comparisons']['encoded'][1]['timestamp_consistent'] is False


@pytest.mark.parametrize('failure', ['pts', 'ordering', 'duplicate', 'cached_identity', 'origin'])
def test_invalid_frame_associations_are_rejected(failure):
    playback, encoded, rows, timeline = timing_fixture()
    if failure == 'pts': timeline[0]['source_timestamp_s'] += .0001
    if failure == 'ordering': timeline.reverse()
    if failure == 'duplicate': timeline[1] = dict(timeline[0])
    if failure == 'cached_identity': playback['frames'][0]['decoded_index'] = 1
    if failure == 'origin': encoded['frames'][0]['keyframe'] = False
    with pytest.raises(ValueError):
        timing_alignment(playback, encoded, rows, timeline)


def test_quaternion_and_camera_local_motion_ignore_independent_world_gauges():
    r0 = Rotation.from_euler('xyz', [12, 27, -9], degrees=True).as_matrix()
    r1 = r0 @ Rotation.from_euler('xyz', [0, 20, 3], degrees=True).as_matrix()
    sensors = {'a': dict(rotation=r0, center=np.array([2., -4., 7.])),
               'b': dict(rotation=r1, center=np.array([4., -3., 5.]))}
    gauge = Rotation.from_euler('xyz', [-43, 22, 98], degrees=True).as_matrix()
    candidate = {n: dict(rotation=gauge @ p['rotation'],
                         center=8*gauge @ p['center']+np.array([57., -3., 11.]))
                 for n, p in sensors.items()}
    length = np.linalg.norm(motion(sensors['a'], sensors['b'])[1])
    comparison = relative_comparison('a', 'b', candidate, sensors, [8*length, length], .5)
    assert comparison['relative_rotation_error_deg'] == pytest.approx(0, abs=1e-10)
    assert comparison['translation_direction_error_deg'] == pytest.approx(0, abs=1e-5)
    assert comparison['relative_length_ratio'] == pytest.approx(1)
    assert comparison['candidate_length_model_units'] == pytest.approx(8*length)
    assert comparison['sensor_length_m'] == pytest.approx(length)


def test_relative_orientation_and_direction_disagreement_detected_without_pose_fit():
    sensors = {'a': dict(rotation=np.eye(3), center=np.zeros(3)),
               'b': dict(rotation=np.eye(3), center=np.array([1., 0, 0]))}
    candidate = {'a': sensors['a'], 'b': dict(rotation=Rotation.from_euler('z', 90, degrees=True).as_matrix(),
                                           center=np.array([0., 2., 0]))}
    result = relative_comparison('a', 'b', candidate, sensors, [1, 1], .5)
    assert result['relative_rotation_error_deg'] == pytest.approx(90)
    assert result['translation_direction_error_deg'] == pytest.approx(90)
    assert result['relative_length_ratio'] == pytest.approx(2)
    assert direction_error(np.zeros(3), np.ones(3)) is None


def write_odometry(path, frames=(0, 1), quaternion=(0, 0, 0, 1)):
    path.write_text('timestamp, frame, x, y, z, qx, qy, qz, qw, fx, fy\n'+''.join(
        f'{100+i/60}, {frame}, 1, 2, 3, '+', '.join(map(str, quaternion))+', 1597, 1597\n'
        for i, frame in enumerate(frames)))


def test_scanner_csv_spaces_and_xyzw_convention(tmp_path):
    path = tmp_path/'odometry.csv'; write_odometry(path)
    rows = read_odometry(path)
    assert np.array_equal(rows[0]['rotation'], np.eye(3))
    assert rows[1]['timestamp_s'] > rows[0]['timestamp_s']
    assert rows[0]['center'].tolist() == [1, 2, 3]


@pytest.mark.parametrize('frames,q', [((0, 2), (0, 0, 0, 1)), ((0, 1), (0, 0, 0, 0)),
                                      ((0, 1), (0, 0, float('nan'), 1))])
def test_invalid_sensor_pose_is_rejected(tmp_path, frames, q):
    path = tmp_path/'odometry.csv'; write_odometry(path, frames, q)
    with pytest.raises(ValueError): read_odometry(path)


def test_retained_artifact_changes_are_rejected(tmp_path):
    artifact = tmp_path/'record.txt'; artifact.write_text('original')
    summary = tmp_path/'summary.json'
    summary.write_text(json.dumps(dict(artifacts={str(artifact): sha256(artifact)})))
    assert len(verify_retained_summaries([summary])) == 1
    artifact.write_text('changed')
    with pytest.raises(ValueError, match='Retained evidence changed'):
        verify_retained_summaries([summary])


def test_audit_output_cannot_overlap_source_or_replace_existing_output(tmp_path):
    source = tmp_path/'source'; source.mkdir()
    with pytest.raises(ValueError, match='new, separate'):
        run(tmp_path/'model', tmp_path/'context', tmp_path/'timing', source, source/'audit')
    with pytest.raises(ValueError, match='new, separate'):
        run(tmp_path/'model', tmp_path/'context', tmp_path/'timing', source, tmp_path)


@pytest.mark.parametrize('wrong_pixel', [False, True])
def test_pixel_witness_checks_content_in_both_decode_conventions(tmp_path, monkeypatch, wrong_pixel):
    images = tmp_path/'images'; images.mkdir()
    out = tmp_path/'out'; out.mkdir()
    rgb = np.full((4, 6, 3), 137, dtype=np.uint8)
    Image.fromarray(rgb).save(images/'frame.png')
    calls = []
    def decoder(command, **kwargs):
        calls.append(command)
        decoded = rgb.copy()
        if wrong_pixel: decoded[0, 0, 0] += 1
        Image.fromarray(decoded).save(Path(command[-1].replace('%05d', '00001')))
        return SimpleNamespace(stderr='')
    monkeypatch.setattr('scripts.audit_transition_odometry.subprocess.run', decoder)
    alignment = dict(views=[dict(image='frame.png', playback_index=40, sensor_frame=41)])
    if wrong_pixel:
        with pytest.raises(ValueError, match='RGB identity disagrees'):
            pixel_witness(tmp_path/'rgb.mp4', images, alignment, out)
    else:
        result = pixel_witness(tmp_path/'rgb.mp4', images, alignment, out)
        assert len(result) == 2 and all(r['pixels_exact'] for r in result)
        assert '-ignore_editlist' not in calls[0] and '-ignore_editlist' in calls[1]
        assert "eq(n,40)" in calls[0][calls[0].index('-vf')+1]
        assert "eq(n,41)" in calls[1][calls[1].index('-vf')+1]
