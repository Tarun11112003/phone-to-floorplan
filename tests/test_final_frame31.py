import shutil
import struct

import pytest

from scripts.diagnostics.audit_final_frame31 import STAGES, logged_stages, native_interval, replay_gate
from scripts.experiments.experimental_registration_stage import BINARIES


def model(path, identities):
    path.mkdir()
    for name in BINARIES-{'images.bin'}:
        (path/name).write_bytes(name.encode())
    records = [struct.pack('<I7dI', identity, 1., 0., 0., 0., 0., 0., 0., identity)
               +b'image.png\0'+struct.pack('<QddQ', 1, 10., 20., 9) for identity in identities]
    (path/'images.bin').write_bytes(struct.pack('<Q', len(records))+b''.join(records))
    return path


def test_exact_replay_gate_accepts_only_record_order_difference(tmp_path):
    source = model(tmp_path/'source', [8, 3])
    before = model(tmp_path/'before', [3, 8])
    expected = model(tmp_path/'expected', [8, 3, 5])
    final = model(tmp_path/'final', [5, 3, 8])
    gate = replay_gate(source, before, expected, final)
    assert gate['input_reproduction']['model_state_exact']
    assert gate['output_reproduction']['model_state_exact']
    assert gate['intermediate_interpretation_allowed']
    assert gate['failure'] is None


@pytest.mark.parametrize('binary', ['cameras.bin', 'frames.bin', 'points3D.bin', 'rigs.bin', 'images.bin'])
def test_output_failure_blocks_causal_interpretation_even_with_matching_view_counts(tmp_path, binary):
    source = model(tmp_path/'source', [3])
    before = model(tmp_path/'before', [3])
    expected = model(tmp_path/'expected', [3, 8])
    final = tmp_path/'final'
    shutil.copytree(expected, final)
    path = final/binary
    payload = bytearray(path.read_bytes())
    payload[-1] ^= 1
    path.write_bytes(payload)
    gate = replay_gate(source, before, expected, final)
    assert not gate['output_reproduction']['model_state_exact']
    assert not gate['intermediate_interpretation_allowed']
    assert gate['failure']
    assert not gate['final_raw_binary_equality'][binary]
    assert not gate['output_reproduction']['numeric_tolerance_used']


def test_input_failure_stops_before_output_interpretation(tmp_path):
    source = model(tmp_path/'source', [3])
    before = model(tmp_path/'before', [8])
    with pytest.raises(ValueError):
        replay_gate(source, before, tmp_path/'missing_expected', tmp_path/'missing_final')


def test_native_warning_interval_excludes_upstream_and_next_registration():
    log = ('Linear solver failure\nRegistering image #28 (num_reg_frames=29)\n'
           'support107/479\nCreating snapshot\nRegistering image #31 (num_reg_frames=30)\n'
           'Linear solver failure\n')
    interval = native_interval(log, 28, 31)
    assert 'Creating snapshot' in interval
    assert 'Linear solver failure' not in interval


@pytest.mark.parametrize('log', ['', 'Registering image #31 (\nRegistering image #28 (',
    'Registering image #28 (\nRegistering image #28 (\nRegistering image #31 ('])
def test_missing_reversed_or_duplicate_intervals_are_rejected(log):
    with pytest.raises(ValueError):
        native_interval(log, 28, 31)


def test_all_native_capture_counts_are_preserved():
    log = 'selected [28, 31]\nsupport 107 479\n'
    log += '\n'.join(f'{name} 30 6055' for name in STAGES)+'\n'
    assert logged_stages(log) == {name: (30, 6055) for name in STAGES}


@pytest.mark.parametrize('stages', [STAGES[:-1], STAGES[::-1], STAGES+('after_color_extraction',)])
def test_incomplete_reordered_duplicate_stage_capture_is_rejected(stages):
    with pytest.raises(ValueError):
        logged_stages('\n'.join(f'{name} 30 6055' for name in stages))
