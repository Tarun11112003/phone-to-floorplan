"""Isolated native frame34 registration replay; no matching or sensor poses.

Resume the saved30-view RGB reconstruction only. Interpret the captured accepted
registration pose only after unchanged refinement reproduces snapshot28 exactly.
The image-record order may change on native read/write; every record byte must
still match. All other model binaries must match without a numeric tolerance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from floorplan.provenance import sha256
from scripts.audit_transition_odometry import verify_retained_summaries
from scripts.experimental_fixed_intrinsics import check_saved_intrinsics, fixed_options, serialize
from scripts.experimental_mapping_only import require_pose_free_database, require_same_options
from scripts.experimental_registration_snapshots import SUMMARIES
from scripts.experimental_transition_context import copy_context_database
from scripts.experimental_video_bridge import baseline_digest

RETAINED = SUMMARIES + ['docs/results/phase3_registration_snapshots_summary.json']
BINARIES = {'cameras.bin', 'images.bin', 'points3D.bin', 'frames.bin', 'rigs.bin'}


def image_records(path):
    """Parse complete COLMAP4.2.1 image records, retaining every payload byte."""
    data = Path(path).read_bytes()
    if len(data) < 8:
        raise ValueError('Truncated image header')
    count = struct.unpack_from('<Q', data)[0]
    cursor = 8; records = {}; order = []
    for _ in range(count):
        start = cursor
        if cursor + 64 > len(data):
            raise ValueError('Truncated image pose record')
        identity = struct.unpack_from('<I', data, cursor)[0]
        cursor += 64  # image id, quaternion, translation, camera id
        end = data.find(b'\0', cursor)
        if end < 0:
            raise ValueError('Unterminated image name')
        cursor = end + 1
        if cursor + 8 > len(data):
            raise ValueError('Truncated image observation count')
        observations = struct.unpack_from('<Q', data, cursor)[0]
        cursor += 8 + observations * 24
        if cursor > len(data):
            raise ValueError('Truncated image observations')
        if identity in records:
            raise ValueError('Duplicate image identity')
        records[identity] = data[start:cursor]
        order.append(identity)
    if cursor != len(data):
        raise ValueError('Trailing image bytes')
    return records, order


def require_snapshot_reproduction(expected, actual):
    expected, actual = Path(expected), Path(actual)
    for root in (expected, actual):
        if {p.name for p in root.glob('*.bin')} != BINARIES:
            raise ValueError('Expected exactly five native model binaries')
    before = {n: sha256(expected/n) for n in sorted(BINARIES)}
    after = {n: sha256(actual/n) for n in sorted(BINARIES)}
    exact = {n: before[n] == after[n] for n in before}
    if not all(exact[n] for n in BINARIES - {'images.bin'}):
        raise ValueError('Refinement does not reproduce native model bytes')
    records, order = image_records(expected/'images.bin')
    repeated, new_order = image_records(actual/'images.bin')
    if records != repeated:
        raise ValueError('Refinement does not reproduce exact image record payloads')
    return dict(model_state_exact=True, numeric_tolerance_used=False,
        raw_binary_equality=exact, expected_sha256=before, actual_sha256=after,
        image_records_exact=len(records), expected_image_order=order, actual_image_order=new_order,
        image_record_sha256={str(k): hashlib.sha256(v).hexdigest() for k,v in sorted(records.items())},
        order_only_difference=order != new_order)


def replay_registration(mapper, options, image_id, capture, extract_colors):
    """Keep native stage order, with read-only captures before refinement."""
    capture('before_registration')
    if not mapper.register_next_image(options.get_mapper(), image_id):
        raise ValueError('Native registration failed; no pose-stage conclusion allowed')
    capture('accepted_registration')
    triangulated = mapper.triangulate_image(options.get_triangulation(), image_id)
    capture('after_triangulation')
    mapper.iterative_local_refinement(options.ba_local_max_refinements,
        options.ba_local_max_refinement_change, options.get_mapper(),
        options.get_local_bundle_adjustment(), options.get_triangulation(), image_id)
    capture('after_local_refinement')
    if not extract_colors():
        raise ValueError('Native post-refinement color extraction failed')
    capture('after_color_extraction')
    return triangulated


def run(source, out):
    import pycolmap
    start = time.perf_counter()
    source, out = Path(source).resolve(), Path(out).resolve()
    if out.exists() or out == source or source in out.parents or out in source.parents:
        raise ValueError('Output must be fresh and separate from retained inputs')
    if pycolmap.__version__ != '4.2.1':
        raise ValueError('Stage replay requires pinned PyCOLMAP4.2.1')
    frozen = verify_retained_summaries(RETAINED)
    record_path = source/'experiment.json'
    record = json.loads(record_path.read_text(encoding='utf-8'))
    if record['experiment'] != 'native_per_registration_snapshot_replay':
        raise ValueError('Expected batch025 native snapshots')
    frontend = Path(record['frontend'])
    original = json.loads((frontend/'experiment.json').read_text(encoding='utf-8'))
    baseline = json.loads((Path(record['baseline'])/'experiment.json').read_text(encoding='utf-8'))
    names = [v['image'] for v in record['temporal_window']]
    if len(names) != 32 or record['image_sha256'] != original['image_sha256']:
        raise ValueError('Retain exactly the original32 RGBs')
    expected = {int(k):v for k,v in record['camera_parameters'].items()}
    _, options, frozen_options, _ = fixed_options(pycolmap, original, expected)
    require_same_options(baseline['options'], frozen_options)
    if options.use_prior_position:
        raise ValueError('Sensor-assisted optimization is forbidden')
    entry, next_entry = record['snapshots'][27:29]
    if entry['registered_images'] != 30 or next_entry['registered_images'] != 31:
        raise ValueError('Incorrect saved registration interval')
    for item in (entry, next_entry):
        if {p.name:sha256(p) for p in Path(item['path']).glob('*.bin')} != item['binary_sha256']:
            raise ValueError('Retained snapshot changed')
    for name,digest in record['image_sha256'].items():
        if sha256(source/'images'/name) != digest:
            raise ValueError('Retained RGB changed')
    require_pose_free_database(source/'features.db')
    tables = baseline_digest(source/'features.db')
    out.mkdir(parents=True)
    images = out/'images'; images.mkdir()
    for name in names:
        shutil.copy2(source/'images'/name, images/name)
    database = out/'features.db'
    copy_context_database(source/'features.db', database, names, True, pycolmap)
    if baseline_digest(database) != tables:
        raise ValueError('Copied camera/frontend database differs')
    require_pose_free_database(database)
    cache_options = pycolmap.DatabaseCacheOptions(min_num_matches=options.min_num_matches,
        ignore_watermarks=options.ignore_watermarks, image_names=set(options.image_names),
        load_all_images=options.load_all_images, convert_pose_priors_to_enu=options.use_prior_position)
    with pycolmap.Database.open(database) as db:
        cache = pycolmap.DatabaseCache.create(db, cache_options)
    model = pycolmap.Reconstruction(entry['path'])
    check_saved_intrinsics(model, expected)
    mapper = pycolmap.IncrementalMapper(cache)
    mapper.begin_reconstruction(model)
    candidates = mapper.find_next_images(options.get_mapper(), False)
    image_id = next(k for k,v in model.images.items() if v.name == 'frame_00034.png')
    if not candidates or candidates[0] != image_id or model.images[image_id].has_pose:
        raise ValueError('Frame34 must be the native next unregistered selection')
    visible = mapper.observation_manager.num_visible_points3D(image_id)
    observations = mapper.observation_manager.num_observations(image_id)
    if (visible, observations) != (83,458):
        raise ValueError('Native visible support differs from retained registration log')
    stages = []
    def capture(label):
        path = out/label; path.mkdir()
        model.write(path)
        stages.append(dict(stage=label, path=str(path), registered_views=model.num_reg_images(),
            sparse_points=model.num_points3D(), fixed_intrinsics=check_saved_intrinsics(model,expected),
            binary_sha256={p.name:sha256(p) for p in path.glob('*.bin')}))
    native_start = time.perf_counter()
    triangulated = replay_registration(mapper, options, image_id, capture,
        lambda: model.extract_colors_for_image(image_id, images))
    native_s = time.perf_counter()-native_start
    reproduction = require_snapshot_reproduction(next_entry['path'],out/'after_color_extraction')
    if baseline_digest(database) != tables or baseline_digest(source/'features.db') != tables:
        raise ValueError('Native resume changed camera/frontend database rows')
    require_pose_free_database(database)
    if any(sha256(p) != digest for p,digest in frozen.items()):
        raise ValueError('Prior pinned evidence changed')
    result = dict(experiment='native_registration_before_local_refinement',pycolmap=pycolmap.__version__,
        source=str(source), source_snapshot_index=27, expected_snapshot_index=28,
        source_snapshot=entry, expected_snapshot=next_entry, stages=stages,
        native_selected_ids=list(candidates), registered_image_id=image_id,
        registered_image_name='frame_00034.png', visible_landmarks_before=visible,
        observations_before=observations, triangulated_observations=triangulated,
        snapshot_reproduction=reproduction, options=frozen_options,
        effective_mapper_options=serialize(options.get_mapper()),
        effective_local_ba_options=serialize(options.get_local_bundle_adjustment()),
        effective_triangulation_options=serialize(options.get_triangulation()),
        cache_options=serialize(cache_options), source_database_tables=tables,
        image_sha256=record['image_sha256'],temporal_window=record['temporal_window'],
        camera_parameters=record['camera_parameters'], graph=record['graph'],
        input_sha256={str(p):sha256(p) for p in (record_path,frontend/'experiment.json',
            Path(record['baseline'])/'experiment.json')},
        saved_rgb_only_state_resumed=True, sensor_poses_used_in_reconstruction=False,
        matching_rerun=False, verification_rerun=False, global_refinement_called=False,
        production_changed=False, production_adoption=False,accuracy_validated=False,
        frozen_hashes_checked=len(frozen),script_sha256=sha256(__file__),
        native_stage_runtime_s=native_s,runtime_s=time.perf_counter()-start)
    (out/'experiment.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(reproduction=reproduction,stages=[{k:s[k] for k in
        ('stage','registered_views','sparse_points')} for s in stages],
        native_stage_runtime_s=native_s),indent=2),flush=True)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default='demo/phase3_registration_snapshots/trial1')
    parser.add_argument('--out',required=True)
    args=parser.parse_args(); run(args.source,args.out)
