"""Isolated pinned XFeat/LighterGlue trial on the frozen 32-view RGB context.

Imports original camera metadata only. Never reads optimized poses or modifies
production code. 64-D descriptors stay in memory, outside the SIFT database API.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import itertools
import json
from pathlib import Path
import random
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.provenance import sha256
from floorplan.sfm import _matching_diagnostics
from scripts.experimental_transition_context import copy_context_database, group_model_status
from scripts.experimental_transition_matchers import colmap_keypoints, frozen_options, geometry_report, VERSIONS
from scripts.experimental_video_bridge import shortest_bridge

REVISION = 'e92685f57f8318b18725c5c8c0bd28c7fe188d9a'
UPSTREAM_HASHES = {
    'LICENSE': 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4',
    'README.md': '9f05c442c4ef0ced48deefb51307f65e8d14f72b14fb3fd65e8f75bfd3e321a5',
    'requirements.txt': 'a2e3f506b40a43e978f72e9be482dd10de1c46d1e837a9d7e19fa7c0916303ae',
    'modules/xfeat.py': '385ccd31d095b0d4176b04e982088b85321b11ade4324f83b097ee6524f2a6e7',
    'modules/model.py': 'd9a665f18fcea5eaf3e278925e1a92103afcba9051e05b2334f3daa29f411964',
    'modules/interpolator.py': 'd63a6163eb6fff81e8720231f62537a42a69fccb44dc8851b04de5115daab4da',
    'modules/lighterglue.py': '65742312cc38ef2306915a148ff02d7cddd2b28e11d08f56827ba36f59f67df6',
    'weights/xfeat.pt': '0f5187fd7bedd26c7fe6acc9685444493a165a35ecc087b33c2db3627f3ea10b',
    'weights/xfeat-lighterglue.pt': '766102df37f11189efe5b0811d1f47c72b22629b79bfabfcfff9d2a2f84654b8',
}
MAX_KEYPOINTS = 2048
MAX_DIMENSION = 1024


def checkpoint_key_compatibility(checkpoint_keys, model_keys, parameter_keys):
    """Allow only the training extractor and Kornia's computed threshold buffer."""
    missing = set(model_keys)-set(checkpoint_keys)
    unused = set(checkpoint_keys)-set(model_keys)
    if set(parameter_keys)-set(checkpoint_keys) or missing-{'confidence_thresholds'} or any(
            not k.startswith('extractor.model.net.') for k in unused):
        raise ValueError('Kornia/checkpoint compatibility failed: incomplete parameter loading')
    return dict(computed_buffers=sorted(missing), unused_training_extractor_tensors=len(unused))


def validate_snapshot(root):
    for name, wanted in UPSTREAM_HASHES.items():
        if sha256(root/name) != wanted:
            raise ValueError(f'Pinned XFeat source/checkpoint changed: {name}')


def original_pixels(points, original_size, resized_size):
    points = np.asarray(points, dtype=np.float32)
    sizes = np.asarray([original_size, resized_size], dtype=float)
    if sizes.shape != (2, 2) or not np.isfinite(sizes).all() or (sizes <= 0).any():
        raise ValueError('Expected positive finite width/height pairs')
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError('Expected finite Nx2 keypoints')
    if (points < 0).any() or (points >= sizes[1]).any():
        raise ValueError('Keypoints lie outside the resized RGB image')
    return np.ascontiguousarray(points * (sizes[0]/sizes[1]).astype(np.float32))


def indexed_matches(matches, counts, image_ids):
    """Preserve extractor feature identities and canonical COLMAP pair orientation."""
    matches = np.asarray(matches)
    if matches.ndim != 2 or matches.shape[1] != 2 or not np.issubdtype(matches.dtype, np.integer):
        raise ValueError('Expected integer Nx2 match indices')
    if (matches < 0).any() or (matches >= np.asarray(counts)).any():
        raise ValueError('Match refers to an absent feature')
    if any(len(np.unique(matches[:, i])) != len(matches) for i in range(2)):
        raise ValueError('Matcher output must be one-to-one')
    a, b = image_ids
    if a == b:
        raise ValueError('Cannot match an image to itself')
    return (min(a, b), max(a, b), np.ascontiguousarray(
        matches if a < b else matches[:, ::-1], dtype=np.uint32))


def setup_models(snapshot, site):
    sys.path.insert(0, str(site.resolve()))
    sys.path.insert(0, str(snapshot.resolve()))
    for package, version in VERSIONS.items():
        if importlib.metadata.version(package) != version:
            raise ValueError(f'{package} differs from the retained runtime pin')
    validate_snapshot(snapshot)
    import torch
    from modules.xfeat import XFeat
    from modules.lighterglue import LighterGlue
    if torch.cuda.is_available():
        raise ValueError('This declared CPU experiment must not silently select CUDA')
    torch.manual_seed(7); np.random.seed(7); random.seed(7)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    extractor = XFeat(weights=str(snapshot/'weights/xfeat.pt'), top_k=MAX_KEYPOINTS).eval()
    # Disable CUDA FlashAttention only; retain trained architecture and matcher thresholds.
    LighterGlue.default_conf_xfeat = dict(LighterGlue.default_conf_xfeat, flash=False)
    matcher = LighterGlue(weights=str(snapshot/'weights/xfeat-lighterglue.pt')).eval()
    # Upstream uses strict=False. Require every parameter to come from this checkpoint.
    state = torch.load(snapshot/'weights/xfeat-lighterglue.pt', map_location='cpu', weights_only=True)
    for i in range(matcher.net.conf.n_layers):
        state = {k.replace(f'self_attn.{i}', f'transformers.{i}.self_attn')
                   .replace(f'cross_attn.{i}', f'transformers.{i}.cross_attn')
                   .replace('matcher.', ''): v for k, v in state.items()}
    actual = matcher.net.state_dict()
    compatibility = checkpoint_key_compatibility(state, actual, dict(matcher.net.named_parameters()))
    if not all(torch.equal(state[k], actual[k]) for k in set(actual)&set(state)):
        raise ValueError('Kornia/checkpoint compatibility failed: incomplete parameter loading')
    extractor.lighterglue = matcher
    identity = dict(code_revision=REVISION, upstream_sha256=UPSTREAM_HASHES,
        versions=VERSIONS, torch_threads=4, deterministic_algorithms=True, seed=7,
        extractor=dict(top_k=MAX_KEYPOINTS, detection_threshold=extractor.detection_threshold,
                       maximum_dimension=MAX_DIMENSION, descriptor_dimension=64),
        matcher=vars(matcher.net.conf), checkpoint_all_parameters_verified=True,
        checkpoint_compatibility=compatibility,
        usage_rights='Official Apache-2.0 repository including bundled checkpoints; no separate weight restrictions found',
        pixel_coordinate_conversion='Resize coordinates to original image, then +0.5 for COLMAP',
        descriptor_imported_as_sift=False)
    return extractor, identity


def xfeat_matches(database, images, names, ids, snapshot, site):
    import pycolmap
    extractor, identity = setup_models(snapshot, site)
    import torch
    from PIL import Image
    features = {}; counts = {}; hashes = {}; sizes = {}
    start = time.perf_counter()
    with pycolmap.Database.open(database) as db, torch.inference_mode():
        for index, name in enumerate(names):
            with Image.open(images/name) as im:
                im = im.convert('RGB'); original = im.size
                tensor = torch.from_numpy(np.array(im, dtype=np.float32)/255).permute(2, 0, 1)[None]
            ratio = min(1., MAX_DIMENSION/max(original))
            resized = tuple(round(v*ratio) for v in original)
            tensor = torch.nn.functional.interpolate(tensor, size=(resized[1], resized[0]),
                                                     mode='bilinear', align_corners=False, antialias=True)
            feature = extractor.detectAndCompute(tensor, top_k=MAX_KEYPOINTS)[0]
            feature['image_size'] = resized
            features[name] = feature
            points = original_pixels(feature['keypoints'].numpy(), original, resized)
            counts[name] = len(points); sizes[name] = dict(original=original, resized=resized)
            hashes[name] = {key: hashlib.sha256(value.numpy().tobytes()).hexdigest()
                           for key, value in feature.items() if torch.is_tensor(value)}
            db.write_keypoints(ids[name], colmap_keypoints(points))
            print(f'XFeat features {index+1}/{len(names)}: {name} {len(points)}', flush=True)
        extracted = time.perf_counter()
        pairs = list(itertools.combinations(names, 2)); candidates = []
        for index, (a, b) in enumerate(pairs):
            _, _, matches = extractor.match_lighterglue(features[a], features[b], min_conf=.1)
            aa, bb, matches = indexed_matches(matches, (counts[a], counts[b]), (ids[a], ids[b]))
            db.write_matches(aa, bb, matches)
            candidates.append(dict(image_a=a, image_b=b, candidate_matches=len(matches)))
            if index % 12 == 0:
                print(f'XFeat/LighterGlue pairs {index+1}/{len(pairs)}', flush=True)
    identity.update(keypoint_counts=counts, feature_sha256=hashes, image_sizes=sizes)
    import kornia
    package = Path(kornia.__file__).parent
    identity['kornia_python_sha256'] = {str(p.relative_to(package)): sha256(p) for p in sorted(package.rglob('*.py'))}
    return candidates, identity, dict(extraction_s=extracted-start, matching_s=time.perf_counter()-extracted)


def run(baseline, out, snapshot, site):
    import pycolmap
    baseline, out, snapshot, site = [Path(p).resolve() for p in (baseline, out, snapshot, site)]
    control = json.loads((baseline/'experiment.json').read_text())
    if control['experiment'] != 'matched_32_view_RGB_context' or len(control['image_sha256']) != 32:
        raise ValueError('Expected retained completed 32-view context')
    inputs = {str(baseline/'experiment.json'): sha256(baseline/'experiment.json')}
    for table in (control['input_sha256'], control['production_code_sha256'], control['dependency_sha256']):
        for p, wanted in table.items():
            if sha256(p) != wanted: raise ValueError(f'Frozen baseline changed: {p}')
            inputs[p] = wanted
    dependencies = {str(Path(p).resolve()): sha256(p) for p in (
        __file__, 'scripts/experimental_transition_context.py', 'scripts/experimental_transition_matchers.py',
        'scripts/experimental_video_bridge.py')}
    code = {str(p.resolve()): sha256(p) for p in Path('floorplan').glob('*.py')}
    if code != control['production_code_sha256']: raise ValueError('Production baseline changed')
    validate_snapshot(snapshot)
    inputs.update({str(snapshot/p): h for p, h in UPSTREAM_HASHES.items()})
    names = [r['image'] for r in control['temporal_window']]
    for name, wanted in control['image_sha256'].items():
        if sha256(baseline/'images'/name) != wanted: raise ValueError('Retained RGB changed')
        inputs[str(baseline/'images'/name)] = wanted
    verification, mapper = frozen_options(pycolmap, control)
    out.mkdir(parents=True, exist_ok=False); images=out/'images'; images.mkdir()
    for name in names: shutil.copy2(baseline/'images'/name, images/name)
    started = time.perf_counter(); database=out/'features.db'
    # Completed baseline DB contains original, unoptimized camera/image metadata.
    ids = copy_context_database(baseline/'features.db', database, names, False, pycolmap)
    candidates, identity, timings = xfeat_matches(database, images, names, ids, snapshot, site)
    # Retain frontend evidence before native mapping, which may outlive the session.
    checkpoint=dict(input_sha256=inputs,identity=identity,candidates=candidates,stage_runtime_s=dict(timings),
        dependency_sha256=dependencies,production_code_sha256=code,image_sha256=control['image_sha256'])
    (out/'frontend.json').write_text(json.dumps(checkpoint,indent=2)+'\n',encoding='utf-8')
    pair_file=out/'pairs.txt'
    pair_file.write_text('\n'.join(f'{a} {b}' for a,b in itertools.combinations(names,2))+'\n')
    stage=time.perf_counter(); pycolmap.verify_matches(database, pair_file, options=verification)
    timings['verification_s']=time.perf_counter()-stage
    graph=geometry_report(database, names, candidates); groups=control['target_groups']
    graph['target_group_path']=shortest_bridge(names,
        [(p['image_a'],p['image_b']) for p in graph['pairs'] if p['verified_inliers']],
        set(groups[0])&set(names), set(groups[1])&set(names))
    (out/'verified_frontend.json').write_text(json.dumps(dict(graph=graph,options=control['options'],
        stage_runtime_s=dict(timings)),indent=2)+'\n',encoding='utf-8')
    sparse=out/'sparse'; sparse.mkdir(); stage=time.perf_counter()
    models=pycolmap.incremental_mapping(database, images, sparse, options=mapper)
    timings['mapping_s']=time.perf_counter()-stage
    rows=[]
    for key, model in models.items():
        registered=sorted(i.name for i in model.images.values() if i.has_pose)
        errors=[p.error for p in model.points3D.values() if np.isfinite(p.error) and p.error>=0]
        rows.append(dict(model_id=key, image_names=registered, registered_images=len(registered),
            sparse_points=model.num_points3D(), mean_reprojection_error_px=model.compute_mean_reprojection_error(),
            point_mean_error_quantiles_px=np.quantile(errors,[0,.5,.95,1]).tolist() if errors else [],
            both_endpoints_registered={'frame_00024.png','frame_00027.png'}.issubset(registered),
            **group_model_status(registered,groups),
            binary_sha256={p.name:sha256(p) for p in (sparse/str(key)).glob('*.bin')}))
    result=dict(experiment='matched_32_view_xfeat_lighterglue', mode='xfeat_lighterglue',
        input_sha256=inputs, image_sha256=control['image_sha256'], temporal_window=control['temporal_window'],
        context_anchors=control['context_anchors'], options=control['options'], identity=identity,
        graph=graph, models=rows, target_groups=groups,
        matching_diagnostics=_matching_diagnostics(database,len(names)),
        maximum_registered_images=max((r['registered_images'] for r in rows),default=0),
        total_registered_images=len({n for r in rows for n in r['image_names']}),
        joint_endpoint_model=any(r['both_endpoints_registered'] for r in rows),
        joint_target_group_model=any(r['both_target_groups_registered'] for r in rows),
        runtime_s=time.perf_counter()-started, stage_runtime_s=timings,
        script_sha256=sha256(__file__), dependency_sha256=dependencies, production_code_sha256=code,
        accuracy_validated=False, metric_scale=False, production_policy_changed=False,
        previous_optimized_poses_used=False, production_adoption=False)
    if any(sha256(p)!=h for p,h in {**inputs,**code,**dependencies}.items()):
        raise ValueError('Frozen baseline or experiment recipe changed during execution')
    (out/'experiment.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('models','joint_target_group_model','runtime_s')},indent=2),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,default=Path('demo/phase3_transition_context/sift1'))
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--snapshot',type=Path,default=Path('.tools/xfeat_experiment')/REVISION)
    p.add_argument('--site',type=Path,default=Path('.tools/lightglue_experiment/site'))
    a=p.parse_args(); run(a.baseline,a.out,a.snapshot,a.site)
