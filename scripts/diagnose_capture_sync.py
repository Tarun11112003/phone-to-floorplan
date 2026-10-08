"""Compare scanner RGB playback and encoded timelines with all sensor frames."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import imageio_ffmpeg
from floorplan.capture_sync import decoded_timing, compare_sensor_timing
from floorplan.provenance import sha256


def audit(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    with (source/'odometry.csv').open(newline='', encoding='utf-8-sig') as stream:
        sensor = list(csv.DictReader(stream, skipinitialspace=True))
    if [int(r['frame']) for r in sensor] != list(range(len(sensor))):
        raise ValueError('This scanner export does not have contiguous sensor frame IDs')
    timestamps = [float(r['timestamp']) for r in sensor]
    modes = {}
    for name, options in [('playback', []), ('encoded', ['-ignore_editlist', '1'])]:
        start = time.perf_counter()
        command = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-threads', '2',
                   *options, '-noautorotate', '-i', str(source/'rgb.mp4'),
                   '-map', '0:v:0', '-vf', 'showinfo=checksum=0', '-vsync', '0', '-f', 'null', '-']
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=600)
        timing = decoded_timing(result.stderr)
        (output/f'{name}_timing.json').write_text(json.dumps(timing, indent=2), encoding='utf-8')
        comparisons = [compare_sensor_timing(timing, timestamps, shift)
                       for shift in range(2) if len(sensor)-shift >= 2]
        modes[name] = dict(decoded_frames=len(timing['frames']),
                           starts_with_keyframe=timing['frames'][0]['keyframe'],
                           time_base_s=timing['time_base_s'], comparisons=comparisons,
                           runtime_s=time.perf_counter()-start)
        print(json.dumps(dict(session=source.name, mode=name, **modes[name])), flush=True)
    summary = dict(source=str(source), sensor_frames=len(sensor), modes=modes,
                   input_sha256={p.name:sha256(p) for p in [source/'rgb.mp4', source/'odometry.csv']},
                   diagnostic_source_sha256=sha256(Path(__file__)),
                   timing_module_sha256=sha256(Path(__file__).parents[1]/'floorplan/capture_sync.py'),
                   physical_accuracy_validated=False)
    (output/'sync_audit.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if (args.source/'odometry.csv').is_file():
        audit(args.source, args.out)
    else:
        for case in ('single_room', 'single_scan_floor_only', 'single_scan_with_ceiling'):
            sessions = [p for p in (args.source/case).iterdir() if (p/'odometry.csv').is_file()]
            if len(sessions) != 1:
                raise ValueError(f'Expected one identified session under {case}')
            audit(sessions[0], args.out/case)
