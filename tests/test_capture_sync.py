import numpy as np
import pytest

from floorplan.capture_sync import decoded_timing, compare_sensor_timing, validate_sensor_video


def timeline(times, tick=.001):
    return dict(time_base_s=tick, frames=[dict(decoded_index=i, pts=round(t/tick),
        timestamp_s=float(t), keyframe=i==0) for i,t in enumerate(times)])


def test_exact_pts_parser_does_not_use_rounded_showinfo_seconds():
    log='config in time_base: 1/60000, frame_rate: 60/1\n'
    log+='n: 0 pts: 0 pts_time:0 fmt:yuv420p iskey:1\n'
    log+='n: 1 pts: 1001 pts_time:0.0167 fmt:yuv420p iskey:0\n'
    data=decoded_timing(log)
    assert data['frames'][1]['timestamp_s']==pytest.approx(1001/60000)
    with pytest.raises(ValueError,match='discontinuous'):
        decoded_timing(log.replace('n: 1','n: 2'))


def test_clock_rate_and_origin_are_audited_without_changing_sensor_pose_identity():
    sensor=70000+np.cumsum(np.tile([.016669,.050007,.033338],20))
    rgb=(sensor-sensor[0])*.99985
    result=validate_sensor_video(timeline(rgb),sensor)
    assert result['timestamp_consistent']
    assert result['clock_rate']==pytest.approx(.99985)
    assert result['sensor_index_shift']==0
    assert not result['physical_accuracy_verified']


def test_an_internal_missing_rgb_frame_cannot_be_treated_as_a_tail():
    sensor=np.arange(20)*.1
    rgb=np.delete(sensor,7)
    with pytest.raises(ValueError,match='cadence'):
        validate_sensor_video(timeline(rgb),sensor)


def test_missing_initial_keyframe_is_rejected_even_if_a_clock_fit_can_hide_offset():
    data=timeline(np.arange(12)*.1); data['frames'][0]['keyframe']=False
    with pytest.raises(ValueError,match='keyframe'):
        validate_sensor_video(data,np.arange(12)*.1)


def test_missing_tail_is_disclosed_and_extra_rgb_is_rejected():
    result=validate_sensor_video(timeline(np.arange(5)*.1),np.arange(6)*.1)
    assert result['omitted_sensor_tail_frames']==1
    with pytest.raises(ValueError,match='more frames'):
        validate_sensor_video(timeline(np.arange(7)*.1),np.arange(6)*.1)


def test_invalid_sensor_clock_and_insufficient_correspondence_are_rejected():
    data=timeline([0,.1])
    with pytest.raises(ValueError,match='strictly increasing'):
        validate_sensor_video(data,[0,0])
    with pytest.raises(ValueError,match='two corresponding'):
        compare_sensor_timing(data,[0,.1],index_shift=1)
