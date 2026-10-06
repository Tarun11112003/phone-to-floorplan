"""Capture normalization tests with source-shaped, deliberately small fixtures."""
import csv
import json
import subprocess
import sys

import cv2
import imageio_ffmpeg
import numpy as np
import pytest
from PIL import Image

from floorplan.ingest import prepare_capture


def test_photos_keep_room_identity_and_exif_orientation(tmp_path):
    source = tmp_path / 'property'
    for room in ('kitchen', 'hall'):
        directory = source / room
        directory.mkdir(parents=True)
        for index in range(2):
            image = Image.new('RGB', (12, 8), (10 + index, 20, 30))
            exif = Image.Exif()
            exif[274] = 6
            image.save(directory / f'IMG_{index:04d}.jpg', exif=exif)
    manifest_path = prepare_capture('photos', source, tmp_path / 'intake')
    manifest = json.loads(manifest_path.read_text())
    mapping = json.loads((manifest_path.parent / 'intake.json').read_text())
    assert manifest['tier'] == 'photos'
    assert set(mapping['rooms']) == {'kitchen', 'hall'}
    assert len({row['normalized'] for row in mapping['images']}) == 4
    assert all((row['width'], row['height']) == (8, 12) for row in mapping['images'])


def test_photos_enforce_assignment_range(tmp_path):
    room = tmp_path / 'source' / 'one'
    room.mkdir(parents=True)
    Image.new('RGB', (10, 10)).save(room / 'one.jpg')
    with pytest.raises(ValueError, match='2'):
        prepare_capture('photos', room.parent, tmp_path / 'intake')


def _scanner_fixture(path, missing_depth=False, high_resolution_rgb=False):
    path.mkdir()
    (path / 'depth').mkdir()
    (path / 'confidence').mkdir()
    frames = path / 'video_frames'
    frames.mkdir()
    for number in range(2):
        rgb_shape=(48,64,3) if high_resolution_rgb else (24,32,3)
        Image.fromarray(np.full(rgb_shape, number * 100, dtype=np.uint8)).save(frames / f'{number:06d}.png')
        if not missing_depth or number == 0:
            cv2.imwrite(str(path / 'depth' / f'{number:06d}.png'), np.full((24, 32), 2000, dtype=np.uint16))
        cv2.imwrite(str(path / 'confidence' / f'{number:06d}.png'), np.full((24, 32), 2, dtype=np.uint8))
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-loglevel', 'error', '-framerate', '2',
                    '-i', str(frames / '%06d.png'), '-pix_fmt', 'yuv420p', str(path / 'rgb.mp4')], check=True)
    fields = 'timestamp frame x y z qx qy qz qw fx fy cx cy'.split()
    with (path / 'odometry.csv').open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for number in range(2):
            scale=2 if high_resolution_rgb else 1
            writer.writerow(dict(timestamp=number / 2, frame=number, x=number / 10, y=0, z=0,
                                 qx=0, qy=0, qz=0, qw=1, fx=25*scale, fy=25*scale,
                                 cx=16*scale, cy=12*scale))


def test_stray_scanner_import_preserves_depth_intrinsics_and_pose(tmp_path):
    source = tmp_path / 'scanner'
    _scanner_fixture(source)
    manifest_path = prepare_capture('lidar', source, tmp_path / 'intake')
    capture = json.loads(manifest_path.read_text())
    sequence = json.loads((manifest_path.parent / 'sequence.json').read_text())
    assert capture['down_direction'] == [0.0, -1.0, 0.0]
    assert sequence['depth_scale'] == 1000
    assert sequence['frames'][0]['intrinsics']['fx'] == 25
    assert sequence['frames'][1]['camera_to_world'][0][3] == pytest.approx(0.1)
    assert sequence['frames'][0]['camera_to_world'][1][1] == -1


def test_stray_scanner_missing_depth_fails_loudly(tmp_path):
    source = tmp_path / 'scanner'
    _scanner_fixture(source, missing_depth=True)
    with pytest.raises(ValueError, match='pair missing'):
        prepare_capture('lidar', source, tmp_path / 'intake')


def test_stray_scanner_scales_rgb_and_intrinsics_together(tmp_path):
    source = tmp_path / 'scanner'
    _scanner_fixture(source, high_resolution_rgb=True)
    manifest_path = prepare_capture('lidar', source, tmp_path / 'intake')
    sequence = json.loads((manifest_path.parent / 'sequence.json').read_text())
    frame = sequence['frames'][0]
    assert frame['intrinsics']['fx'] == 25
    assert frame['intrinsics']['cx'] == 16
    with Image.open(frame['rgb']) as image:
        assert image.size == (32,24)


def test_one_command_leaves_auditable_failure_for_two_photos(tmp_path):
    room = tmp_path / 'source' / 'one'
    room.mkdir(parents=True)
    for number in range(2):
        Image.new('RGB', (20, 20)).save(room / f'{number}.png')
    output = tmp_path / 'run'
    result = subprocess.run([sys.executable, '-m', 'floorplan.cli', 'run-capture',
                             '--tier', 'photos', '--source', str(room.parent), '--out', str(output)],
                            capture_output=True, text=True)
    assert result.returncode == 1
    ledger = json.loads((output / 'result' / 'run.json').read_text())
    assert ledger['result']['status'] == 'failed'
    assert 'five overlapping images' in ledger['result']['reason']
    assert (output / 'intake' / 'capture.json').exists()
