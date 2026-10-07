"""Audit decoded sensor-video identity before pairing it with depth and poses.

Raw scanner exports index the encoded frames, rather than an MP4 playback edit
timeline. Ordinary photo/video intake must continue honoring playback edits.
"""
from __future__ import annotations

import re

import numpy as np


def decoded_timing(stderr):
    """Read exact integer PTS and time base from FFmpeg's showinfo filter."""
    base = re.search(r'config in time_base:\s*(\d+)/(\d+)', stderr)
    if not base or int(base[2]) == 0:
        raise ValueError('Decoder did not report the sensor video time base')
    tick = int(base[1]) / int(base[2])
    if tick <= 0:
        raise ValueError('Decoder reported an invalid sensor video time base')
    pattern = r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:.*?\biskey:(\d+)'
    rows = [dict(decoded_index=int(n), pts=int(pts), timestamp_s=int(pts)*tick,
                 keyframe=bool(int(key))) for n, pts, key in re.findall(pattern, stderr)]
    if not rows or [r['decoded_index'] for r in rows] != list(range(len(rows))):
        raise ValueError('Decoder frame identities are missing or discontinuous')
    return dict(time_base_s=tick, frames=rows)


def compare_sensor_timing(timing, sensor_timestamps, index_shift=0):
    """Compare an explicit index hypothesis; never infer a pairing by nearest time.

An affine clock fit accommodates sensor clock rate versus the MP4 time base.
It cannot certify optical calibration or physical accuracy.
"""
    sensor = np.asarray(sensor_timestamps, dtype=float)
    rgb = np.asarray([r['timestamp_s'] for r in timing['frames']], dtype=float)
    if (sensor.ndim != 1 or len(sensor) < 2 or not np.isfinite(sensor).all()
            or np.any(np.diff(sensor) <= 0)):
        raise ValueError('Sensor timestamps must be finite and strictly increasing')
    if len(rgb) < 2 or not np.isfinite(rgb).all() or np.any(np.diff(rgb) <= 0):
        raise ValueError('Decoded RGB timestamps must be finite and strictly increasing')
    if index_shift < 0 or index_shift >= len(sensor):
        raise ValueError('Invalid sensor index hypothesis')
    count = min(len(rgb), len(sensor)-index_shift)
    if count < 2:
        raise ValueError('At least two corresponding frames are required')
    x = sensor[index_shift:index_shift+count] - sensor[0]
    y = rgb[:count]
    rate, offset = np.linalg.lstsq(np.column_stack([x, np.ones(count)]), y, rcond=None)[0]
    residual = y - (rate*x+offset)
    cadence = np.diff(y)-rate*np.diff(x)
    # At most half a timestamp tick for quantization, but never enough to hide
    # half a sensor frame. This is an identity check, not an accuracy tolerance.
    limit = max(1e-6, min(timing['time_base_s']/2, np.min(np.diff(sensor))/4))
    return dict(sensor_index_shift=index_shift, compared_frames=count,
                decoded_frames=len(rgb), sensor_frames=len(sensor),
                clock_rate=float(rate), clock_offset_s=float(offset),
                max_absolute_residual_s=float(np.max(np.abs(residual))),
                rms_residual_s=float(np.sqrt(np.mean(residual**2))),
                max_cadence_residual_s=float(np.max(np.abs(cadence))),
                residual_limit_s=float(limit),
                timestamp_consistent=bool(abs(rate-1) <= .001
                    and np.max(np.abs(residual)) <= limit
                    and np.max(np.abs(cadence)) <= 2*limit))


def validate_sensor_video(timing, sensor_timestamps):
    """Validate frame-zero pairing for an unedited, frame-indexed scanner export."""
    comparison = compare_sensor_timing(timing, sensor_timestamps)
    if not timing['frames'][0]['keyframe']:
        raise ValueError('Sensor RGB does not begin with its encoded keyframe; frame identity is ambiguous')
    if comparison['decoded_frames'] > comparison['sensor_frames']:
        raise ValueError('Sensor RGB has more frames than odometry')
    if not comparison['timestamp_consistent']:
        raise ValueError('RGB/odometry cadence disagrees; no silent index synchronization')
    return dict(**comparison, method='encoded-frame index with full affine-clock cadence audit',
                ignore_editlist=True, optical_registration_verified=False,
                physical_accuracy_verified=False,
                clock_rate_limit_ppm=1000,
                omitted_sensor_tail_frames=comparison['sensor_frames']-comparison['decoded_frames'])
