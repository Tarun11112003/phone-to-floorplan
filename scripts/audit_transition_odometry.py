"""Post-hoc sensor audit of saved RGB-only models; never map or optimize poses.

All translations are compared in each first camera's optical coordinates.
Length ratios remove monocular scale without fitting a transform to odometry.
Artifacts are read-only; diagnostic output must use a new, separate directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation
from floorplan.capture_sync import compare_sensor_timing
from floorplan.provenance import sha256

PTS_ROUNDING_S = 0.5e-6  # Half the retained manifest's six-decimal second digit.
REFERENCE_PAIR = ('frame_00019.png', 'frame_00024.png')
TRANSITION = ('frame_00024.png', 'frame_00027.png')
HASH_SECTIONS = ('artifacts', 'input_sha256', 'production_code_sha256',
                 'source_trial_sha256', 'dependency_sha256')


def verify_retained_summaries(paths):
    expected = {}
    for path in paths:
        record = json.loads(Path(path).read_text(encoding='utf-8'))
        for key in HASH_SECTIONS:
            for name, digest in record.get(key, {}).items():
                if name in expected and expected[name] != digest:
                    raise ValueError(f'Conflicting retained digest: {name}')
                expected[name] = digest
    for name, digest in expected.items():
        if not Path(name).is_file() or sha256(name) != digest:
            raise ValueError(f'Retained evidence changed: {name}')
    return expected


def read_odometry(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        raw = list(csv.DictReader(stream, skipinitialspace=True))
    rows = []
    for index, row in enumerate(raw):
        if int(row['frame']) != index:
            raise ValueError('Odometry frame IDs must be contiguous from zero')
        q = np.array([float(row[k]) for k in ('qx', 'qy', 'qz', 'qw')])
        center = np.array([float(row[k]) for k in ('x', 'y', 'z')])
        stamp = float(row['timestamp'])
        if (not np.isfinite(np.r_[q, center, stamp]).all()
                or abs(np.linalg.norm(q)-1) > .01):  # Existing scanner intake guard.
            raise ValueError(f'Invalid odometry pose at frame {index}')
        rows.append(dict(frame=index, timestamp_s=stamp, center=center,
                         rotation=Rotation.from_quat(q/np.linalg.norm(q)).as_matrix(),
                         quaternion_norm=float(np.linalg.norm(q)),
                         fx_px=float(row['fx']), fy_px=float(row['fy'])))
    if len(rows) < 2 or np.any(np.diff([r['timestamp_s'] for r in rows]) <= 0):
        raise ValueError('Odometry time must be strictly increasing')
    return rows


def timing_alignment(playback, encoded, rows, timeline):
    for timing in (playback, encoded):
        frames = timing['frames']
        if ([r['decoded_index'] for r in frames] != list(range(len(frames)))
                or any(abs(r['timestamp_s']-r['pts']*timing['time_base_s']) > 1e-12
                       for r in frames)):
            raise ValueError('Cached timing frame identities or integer PTS changed')
    timestamps = [r['timestamp_s'] for r in rows]
    comparisons = {mode: [compare_sensor_timing(timing, timestamps, shift)
                         for shift in (0, 1)]
                   for mode, timing in (('playback', playback), ('encoded', encoded))}
    shifts = {}
    for mode, checks in comparisons.items():
        valid = [c['sensor_index_shift'] for c in checks if c['timestamp_consistent']]
        if len(valid) != 1:
            raise ValueError(f'No unique full-cadence alignment for {mode}')
        shifts[mode] = valid[0]
    if (shifts['encoded'] != 0 or not encoded['frames'][0]['keyframe']
            or len(encoded['frames']) != len(rows)
            or len(playback['frames']) + shifts['playback'] != len(rows)):
        raise ValueError('Encoded scanner origin or complete playback count is unsupported')
    pts = np.array([r['pts']*playback['time_base_s'] for r in playback['frames']])
    aligned = []
    for item in timeline:
        stamp = float(item['source_timestamp_s'])
        candidates = np.flatnonzero(np.abs(pts-stamp) <= PTS_ROUNDING_S+1e-12)
        if len(candidates) != 1:
            raise ValueError(f"No unique retained PTS for {item['image']}")
        index = int(candidates[0]); sensor_index = index+shifts['playback']
        aligned.append(dict(image=item['image'], source_timestamp_s=stamp,
                            playback_index=index, playback_pts=int(playback['frames'][index]['pts']),
                            exact_playback_timestamp_s=float(pts[index]), sensor_frame=sensor_index,
                            sensor_timestamp_s=rows[sensor_index]['timestamp_s'],
                            encoded_pts=int(encoded['frames'][sensor_index]['pts']),
                            pts_rounding_residual_s=float(stamp-pts[index])))
    if (len({a['image'] for a in aligned}) != len(aligned)
            or np.any(np.diff([a['sensor_frame'] for a in aligned]) <= 0)):
        raise ValueError('Retained views are duplicated or not ordered in sensor time')
    return dict(comparisons=comparisons, shifts=shifts, views=aligned,
                pts_rounding_limit_s=PTS_ROUNDING_S,
                max_pts_rounding_residual_s=max(abs(a['pts_rounding_residual_s']) for a in aligned))


def pixel_witness(video, images, alignment, out):
    """Prove both indexed decode conventions reproduce all original RGB pixels."""
    import imageio_ffmpeg
    witnesses = []
    for mode, field in (('playback', 'playback_index'), ('encoded', 'sensor_frame')):
        directory = out/mode; directory.mkdir()
        indices = [a[field] for a in alignment['views']]
        expression = '+'.join(f'eq(n,{i})' for i in indices)
        command = [imageio_ffmpeg.get_ffmpeg_exe(), '-loglevel', 'error']
        if mode == 'encoded':
            command += ['-ignore_editlist', '1', '-noautorotate']
        command += ['-i', str(video), '-vf', f"select='{expression}'", '-vsync', '0',
                    '-frames:v', str(len(indices)), str(directory/'rgb_%05d.png')]
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=180)
        (directory/'ffmpeg.log').write_text(result.stderr, encoding='utf-8')
        files = sorted(directory.glob('rgb_*.png'))
        if len(files) != len(indices):
            raise ValueError(f'Pixel witness decoder returned wrong frame count: {mode}')
        for item, decoded in zip(alignment['views'], files):
            with Image.open(images/item['image']) as source, Image.open(decoded) as witness:
                original = np.asarray(source.convert('RGB')); actual = np.asarray(witness.convert('RGB'))
            if original.shape != actual.shape or not np.array_equal(original, actual):
                raise ValueError(f"RGB identity disagrees: {mode} / {item['image']}")
            witnesses.append(dict(mode=mode, image=item['image'], decoded_index=item[field],
                                  rgb_shape=list(original.shape), pixels_exact=True,
                                  rgb_pixel_sha256=hashlib.sha256(original.tobytes()).hexdigest()))
    return witnesses


def motion(a, b):
    relative = a['rotation'].T @ b['rotation']
    translation = a['rotation'].T @ (b['center']-a['center'])
    return relative, translation


def direction_error(a, b):
    denominator = np.linalg.norm(a)*np.linalg.norm(b)
    if denominator <= 1e-24:  # Arithmetic singularity only, not a sensor noise tolerance.
        return None
    return float(np.degrees(np.arccos(np.clip(np.dot(a, b)/denominator, -1, 1))))


def relative_comparison(a, b, candidate, sensors, lengths, sensor_dt):
    cr, ct = motion(candidate[a], candidate[b]); sr, st = motion(sensors[a], sensors[b])
    cl, sl = float(np.linalg.norm(ct)), float(np.linalg.norm(st))
    rotation_error = float(np.degrees(Rotation.from_matrix(sr.T@cr).magnitude()))
    return dict(image_a=a, image_b=b, sensor_dt_s=float(sensor_dt),
                candidate_relative_rotation=cr.tolist(), sensor_relative_rotation=sr.tolist(),
                candidate_local_translation_model_units=ct.tolist(), sensor_local_translation_m=st.tolist(),
                candidate_rotation_deg=float(np.degrees(Rotation.from_matrix(cr).magnitude())),
                sensor_rotation_deg=float(np.degrees(Rotation.from_matrix(sr).magnitude())),
                relative_rotation_error_deg=rotation_error, translation_direction_error_deg=direction_error(ct, st),
                candidate_length_model_units=cl, sensor_length_m=sl,
                candidate_length_over_reference=cl/lengths[0], sensor_length_over_reference=sl/lengths[1],
                relative_length_ratio=(cl/lengths[0])/(sl/lengths[1]) if sl > 1e-12 else None)


def percentiles(values):
    values = [v for v in values if v is not None]
    return dict(zip(('min', 'median', 'p95', 'max'), np.quantile(values, [0, .5, .95, 1]).tolist())) if values else {}


def audit_model(path, record, alignment, rows):
    import pycolmap
    model = pycolmap.Reconstruction(path)
    candidate = {}
    for image in model.images.values():
        if not image.has_pose:
            continue
        camera = model.cameras[image.camera_id]
        candidate[image.name] = dict(center=np.asarray(image.projection_center()),
                                    rotation=image.cam_from_world().rotation.matrix().T,
                                    focal_px=float(camera.params[0]))
    stamps = {v['image']: v for v in alignment['views']}
    if not set(candidate) <= set(stamps):
        raise ValueError('Saved model contains a view outside the frozen input context')
    sensors = {name: rows[stamps[name]['sensor_frame']] for name in candidate}
    if not all(name in candidate for name in REFERENCE_PAIR):
        raise ValueError('Common pre-transition reference pair is not registered')
    lengths = [float(np.linalg.norm(motion(poses[REFERENCE_PAIR[0]], poses[REFERENCE_PAIR[1]])[1]))
               for poses in (candidate, sensors)]
    if min(lengths) <= 1e-12:
        raise ValueError('Reference translation is singular')
    names = [v['image'] for v in alignment['views'] if v['image'] in candidate]
    def compare(a, b):
        return relative_comparison(a, b, candidate, sensors, lengths,
                                   stamps[b]['sensor_timestamp_s']-stamps[a]['sensor_timestamp_s'])
    adjacent = [compare(a, b) for a, b in zip(names, names[1:])]
    transition_adjacent = [v for v in adjacent if stamps[v['image_a']]['exact_playback_timestamp_s'] >= 11.55
                           and stamps[v['image_b']]['exact_playback_timestamp_s'] <= 13.066667]
    anchor = [compare(TRANSITION[0], n) for n in names if n != TRANSITION[0]]
    pairs = sorted(set([REFERENCE_PAIR, TRANSITION, ('frame_00023.png', 'frame_00028.png'),
                        ('frame_00022.png', 'frame_00027.png'), ('frame_00022.png', 'frame_00028.png'),
                        ('frame_00023.png', 'frame_00027.png'), ('bridge_00003.png', 'frame_00027.png')]))
    selected = [compare(a, b) for a, b in pairs if a in candidate and b in candidate]
    sensitivity = []
    for item in selected:
        a, b = item['image_a'], item['image_b']; ia, ib = [stamps[n]['sensor_frame'] for n in (a, b)]
        variants = []
        # Conservative timing sensitivity: vary BOTH endpoint associations by one
        # sensor frame, despite exact pixel identity. No new tolerance or pose fit.
        for da in (-1, 0, 1):
            for db in (-1, 0, 1):
                if not (0 <= ia+da < len(rows) and 0 <= ib+db < len(rows)):
                    continue
                shifted = {a: rows[ia+da], b: rows[ib+db]}
                variants.append(relative_comparison(a, b, candidate, shifted, lengths, item['sensor_dt_s']))
        sensitivity.append(dict(image_a=a, image_b=b,
                                relative_rotation_error_deg_range=[min(v['relative_rotation_error_deg'] for v in variants),
                                                                    max(v['relative_rotation_error_deg'] for v in variants)],
                                translation_direction_error_deg_range=[min(v['translation_direction_error_deg'] for v in variants),
                                                                        max(v['translation_direction_error_deg'] for v in variants)],
                                interpretation='one-frame association sensitivity, not an acceptance band'))
    trajectory = []
    for name in names:
        v = stamps[name]; sensor = sensors[name]
        trajectory.append(dict(**v, candidate_center_model_units=candidate[name]['center'].tolist(),
                               candidate_camera_to_world_rotation=candidate[name]['rotation'].tolist(),
                               sensor_center_m=sensor['center'].tolist(), sensor_camera_to_world_rotation=sensor['rotation'].tolist(),
                               candidate_focal_px=candidate[name]['focal_px'], sensor_fx_px=sensor['fx_px'],
                               sensor_fy_px=sensor['fy_px'], focal_ratio=candidate[name]['focal_px']/sensor['fx_px']))
    return dict(registered_views=len(candidate), registered_timeline=trajectory,
                unregistered_views=[n for n in stamps if n not in candidate],
                reference_pair=list(REFERENCE_PAIR), reference_candidate_length_model_units=lengths[0],
                reference_sensor_length_m=lengths[1], adjacent=adjacent,
                transition_adjacent=transition_adjacent, transition_anchor_comparisons=anchor,
                selected_pairs=selected, one_frame_sensitivity=sensitivity,
                adjacent_rotation_error_deg=percentiles([v['relative_rotation_error_deg'] for v in adjacent]),
                transition_adjacent_rotation_error_deg=percentiles([v['relative_rotation_error_deg'] for v in transition_adjacent]),
                transition_adjacent_direction_error_deg=percentiles([v['translation_direction_error_deg'] for v in transition_adjacent]),
                transition_adjacent_relative_length_ratio=percentiles([v['relative_length_ratio'] for v in transition_adjacent]),
                largest_adjacent_rotation_disagreements=sorted(adjacent, key=lambda v: v['relative_rotation_error_deg'], reverse=True)[:5],
                saved_sparse_points=model.num_points3D(), saved_mean_reprojection_error_px=model.compute_mean_reprojection_error(),
                binary_sha256={p.name: sha256(p) for p in Path(path).glob('*.bin')})


def run(root, context, timing, source, out):
    start = time.perf_counter()
    root, context, timing, source, out = [Path(p).resolve() for p in (root, context, timing, source, out)]
    if out.exists() or any(out == p or out in p.parents or p in out.parents for p in (root, context, timing, source)):
        raise ValueError('Audit output must be a new, separate directory')
    summaries = [Path('docs/results/phase3_transition_context_summary.json'),
                 Path('docs/results/phase3_xfeat_context_summary.json')]
    frozen = verify_retained_summaries(summaries)
    sync = json.loads((timing/'sync_audit.json').read_text(encoding='utf-8'))
    for name, digest in sync['input_sha256'].items():
        if sha256(source/name) != digest:
            raise ValueError('Source capture changed since synchronization audit')
    if sha256('floorplan/capture_sync.py') != sync['timing_module_sha256']:
        raise ValueError('Synchronization guards changed since timing audit')
    input_files = [source/'rgb.mp4', source/'odometry.csv']+list(timing.glob('*.json'))+summaries
    input_hashes = {str(p): sha256(p) for p in input_files}
    rows = read_odometry(source/'odometry.csv')
    records = [json.loads((root/f'trial{i}'/'experiment.json').read_text(encoding='utf-8')) for i in (2, 3)]
    if any(r['previous_optimized_poses_used'] for r in records):
        raise ValueError('Candidate experiment used prior optimized poses')
    if records[0]['temporal_window'] != records[1]['temporal_window']:
        raise ValueError('Candidate repeats have different temporal input mappings')
    alignment = timing_alignment(json.loads((timing/'playback_timing.json').read_text()),
                                 json.loads((timing/'encoded_timing.json').read_text()), rows, records[0]['temporal_window'])
    out.mkdir(parents=True)
    witness = pixel_witness(source/'rgb.mp4', root/'trial2'/'images', alignment, out)
    trials = [audit_model(root/f'trial{i}'/'sparse'/'0', record, alignment, rows)
              for i, record in zip((2, 3), records)]
    control_record = json.loads((context/'sift1'/'experiment.json').read_text(encoding='utf-8'))
    control = audit_model(context/'sift1'/'sparse'/'0', control_record, alignment, rows)
    common = set(v['image'] for v in control['registered_timeline'])
    common_comparisons = {}
    for label, result in (('sift', control), ('xfeat', trials[0])):
        model_path = context/'sift1'/'sparse'/'0' if label == 'sift' else root/'trial2'/'sparse'/'0'
        import pycolmap
        model = pycolmap.Reconstruction(model_path)
        poses = {i.name: dict(center=i.projection_center(), rotation=i.cam_from_world().rotation.matrix().T)
                 for i in model.images.values() if i.has_pose and i.name in common}
        sensors = {v['image']: rows[v['sensor_frame']] for v in result['registered_timeline'] if v['image'] in common}
        views = [v for v in alignment['views'] if v['image'] in common]
        lengths = [result['reference_candidate_length_model_units'], result['reference_sensor_length_m']]
        common_comparisons[label] = [relative_comparison(a['image'], b['image'], poses, sensors, lengths,
                                     b['sensor_timestamp_s']-a['sensor_timestamp_s']) for a, b in zip(views, views[1:])]
    repeat_exact = trials[0] == trials[1]
    if not repeat_exact:
        raise ValueError('Saved candidate repeats differ in post-hoc audit')
    for path, digest in dict(frozen, **input_hashes).items():
        if sha256(path) != digest:
            raise ValueError(f'Audit mutated its inputs: {path}')
    report = dict(experiment='saved_29_view_relative_pose_odometry_audit', alignment=alignment,
                  pixel_witnesses=witness, trials=trials, sift_control=control,
                  common_view_comparison=common_comparisons, repeated_saved_model_metrics_exact=repeat_exact,
                  frozen_hashes_checked=len(frozen), frozen_artifacts_unchanged=True,
                  input_sha256=input_hashes, script_sha256=sha256(__file__),
                  sensor_poses_used_in_inference=False, sensor_poses_used_to_optimize=False,
                  model_alignment_or_scale_fit=False, physical_accuracy_validated=False,
                  pose_acceptance_tolerance=None, assessment_acceptance=False,
                  tolerance_scope='existing clock identity guards, six-decimal PTS rounding, numerical validity only',
                  runtime_s=time.perf_counter()-start)
    (out/'audit.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(registered_views=trials[0]['registered_views'],
                         selected_pairs=trials[0]['selected_pairs'], repeats_exact=repeat_exact,
                         pixel_witnesses=len(witness), frozen_hashes_checked=len(frozen),
                         runtime_s=report['runtime_s']), indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='demo/phase3_xfeat_context')
    parser.add_argument('--context', default='demo/phase3_transition_context')
    parser.add_argument('--timing', default='demo/phase3_sync_boundary/sync_audit/single_room')
    parser.add_argument('--source', default='datasets/Given_dataset/single_room/c00a170fe1')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    run(args.root, args.context, args.timing, args.source, args.out)
