"""Pinned, isolated matcher comparison on the retained 24-view RGB transition.

SIFT retains the exact cached features/verified pairs of the density trial.
LightGlue starts from camera/image metadata only. Neither reads prior poses.
Downstream verification and mapper options must equal the frozen trial options.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path
import random
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np

from floorplan.provenance import sha256
from floorplan.sfm import _matching_diagnostics
from scripts.diagnostics.audit_sfm_components import connected_components
from scripts.experiments.experimental_video_bridge import read_pairs, shortest_bridge

LIGHTGLUE_COMMIT = 'eb42fee2d71449efb0aa5c10549752b5d75384d8'
WEIGHTS = {'depth-save.pth': '9c2ee4ded238892dfa51569941372601e35e4a74aa6f84ea80053d2ab1c07abe',
           'disk_lightglue_v0-1_arxiv.pth': 'b5b21d47ea24f2c5e501aec9c91b9716e4c8c3429a4dc1e615c133c4c9378335'}
VERSIONS = {'torch': '2.6.0+cpu', 'torchvision': '0.21.0+cpu', 'kornia': '0.8.1', 'pycolmap': '4.2.1'}
TORCH_THREADS = 4
ANCHORS = ['frame_00024.png', 'frame_00025.png', 'frame_00026.png', 'frame_00027.png']
MAX_ID = 2147483647


def colmap_keypoints(points):
    """LightGlue returns original-image zero-based centers; COLMAP uses +0.5."""
    points = np.asarray(points, dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError('Expected finite original-image Nx2 keypoints')
    return np.ascontiguousarray(points + .5)


def pair_belongs(pair_id, ids):
    return pair_id // MAX_ID in ids and pair_id % MAX_ID in ids


def frozen_options(pycolmap, experiment):
    verification = pycolmap.TwoViewGeometryOptions()
    verification.ransac.random_seed = 7
    mapper = pycolmap.IncrementalPipelineOptions(num_threads=1, random_seed=7)
    mapper.mapper.num_threads = 1
    mapper.mapper.random_seed = 7
    mapper.triangulation.random_seed = 7
    serial = lambda value: json.loads(json.dumps(value.todict(), default=str))
    for name, value in [('verification', verification), ('mapping', mapper)]:
        if serial(value) != experiment['options'][name]:
            raise ValueError(f'{name} options differ from the frozen density trial')
    return verification, mapper


def copy_database(source, target, names, sift, pycolmap):
    """Copy declared camera priors and frame identities, never optimized poses."""
    with pycolmap.Database.open(target):
        pass
    with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as src, sqlite3.connect(target) as dst:
        placeholders = ','.join('?' for _ in names)
        images = src.execute(f'SELECT * FROM images WHERE name IN ({placeholders}) ORDER BY image_id', names).fetchall()
        if len(images) != 24:
            raise ValueError('The retained transition must contain exactly 24 database views')
        ids = {r[0] for r in images}; cameras = {r[2] for r in images}
        frames = src.execute('SELECT * FROM frame_data').fetchall()
        frame_data = [r for r in frames if r[1] in ids and r[3] == 0]
        frame_ids = {r[0] for r in frame_data}
        retained_frames = [r for r in src.execute('SELECT * FROM frames') if r[0] in frame_ids]
        rigs = {r[1] for r in retained_frames}
        selected = {
            'cameras': [r for r in src.execute('SELECT * FROM cameras') if r[0] in cameras],
            'rigs': [r for r in src.execute('SELECT * FROM rigs') if r[0] in rigs],
            'rig_sensors': [r for r in src.execute('SELECT * FROM rig_sensors') if r[0] in rigs],
            'frames': retained_frames, 'frame_data': frame_data, 'images': images,
        }
        if sift:
            for table in ('keypoints', 'descriptors'):
                selected[table] = [r for r in src.execute(f'SELECT * FROM {table}') if r[0] in ids]
            for table in ('matches', 'two_view_geometries'):
                selected[table] = [r for r in src.execute(f'SELECT * FROM {table}') if pair_belongs(r[0], ids)]
        for table, rows in selected.items():
            if rows:
                dst.executemany(f"INSERT INTO {table} VALUES ({','.join('?' for _ in rows[0])})", rows)
    return {r[1]: r[0] for r in images}


def learned_matches(database, images, names, ids, site, cache):
    import importlib.metadata
    sys.path.insert(0, str(site.resolve()))
    os.environ['TORCH_HOME'] = str(cache.resolve())
    for name, expected in VERSIONS.items():
        if importlib.metadata.version(name) != expected:
            raise ValueError(f'{name} version differs from the experiment pin')
    direct = json.loads((site/'lightglue-0.0.dist-info/direct_url.json').read_text())
    if direct.get('vcs_info', {}).get('commit_id') != LIGHTGLUE_COMMIT:
        raise ValueError('Installed LightGlue code revision differs from the pin')
    for name, wanted in WEIGHTS.items():
        if sha256(cache/'hub/checkpoints'/name) != wanted:
            raise ValueError(f'Checkpoint differs from the pin: {name}')
    import torch
    from lightglue import DISK, LightGlue
    from lightglue.utils import load_image
    import pycolmap
    torch.manual_seed(7); np.random.seed(7); random.seed(7)
    torch.set_num_threads(TORCH_THREADS)
    torch.use_deterministic_algorithms(True)
    extractor = DISK(max_num_keypoints=2048).eval().cpu()
    matcher = LightGlue(features='disk', flash=False).eval().cpu()
    features = {}; counts = {}; feature_hashes = {}
    with pycolmap.Database.open(database) as db, torch.inference_mode():
        for index, name in enumerate(names):
            feats = extractor.extract(load_image(images/name))
            features[name] = feats
            points = colmap_keypoints(feats['keypoints'][0].numpy())
            counts[name] = len(points)
            # Hash the model output, including descriptors used by LightGlue.
            import hashlib
            feature_hashes[name] = {key: hashlib.sha256(value.numpy().tobytes()).hexdigest()
                                    for key, value in feats.items() if torch.is_tensor(value)}
            db.write_keypoints(ids[name], points)
            print(f'DISK features {index+1}/{len(names)}: {name} {len(points)}', flush=True)
        rows = []
        for index, (a, b) in enumerate(itertools.combinations(names, 2)):
            prediction = matcher({'image0': features[a], 'image1': features[b]})
            matches = prediction['matches'][0].numpy().astype(np.uint32)
            aa, bb = ids[a], ids[b]
            if aa > bb:
                aa, bb = bb, aa; matches = matches[:, ::-1].copy()
            db.write_matches(aa, bb, matches)
            rows.append(dict(image_a=a, image_b=b, candidate_matches=len(matches)))
            if index % 12 == 0:
                print(f'LightGlue pairs {index+1}/276', flush=True)
    package = site/'lightglue'
    return rows, dict(code_revision=LIGHTGLUE_COMMIT, checkpoint_sha256=WEIGHTS,
                      package_python_sha256={str(p.relative_to(package)): sha256(p) for p in sorted(package.rglob('*.py'))},
                      versions=VERSIONS, keypoint_counts=counts, feature_sha256=feature_hashes,
                      extractor=dict(vars(extractor.conf)), matcher=dict(vars(matcher.conf)),
                      torch_threads=TORCH_THREADS, deterministic_algorithms=True, seed=7,
                      pixel_coordinate_conversion='original-image keypoints +0.5 for COLMAP')


def sift_candidates(database, names, ids, pycolmap, frozen):
    opts = pycolmap.FeatureMatchingOptions(num_threads=1)
    if json.loads(json.dumps(opts.todict(), default=str)) != frozen['options']['matching']:
        raise ValueError('SIFT options differ from retained trial')
    matcher = pycolmap.FeatureMatcher.create(options=opts, device=pycolmap.Device.cpu)
    descriptors = {}; counts = {}
    with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as conn:
        for name in names:
            n, c, data = conn.execute('SELECT rows,cols,data FROM descriptors WHERE image_id=?', (ids[name],)).fetchone()
            descriptors[name] = pycolmap.FeatureDescriptors(type=pycolmap.FeatureExtractorType.SIFT,
                        data=np.frombuffer(data, dtype=np.uint8).reshape(n,c).copy())
            counts[name] = n
        stored = dict(conn.execute('SELECT pair_id,rows FROM matches'))
    rows = []
    for a, b in itertools.combinations(names, 2):
        aa, bb = sorted((ids[a], ids[b])); pair = aa*MAX_ID+bb
        matches = matcher.match(pycolmap.FeatureKeypoints(), descriptors[a],
                                pycolmap.FeatureKeypoints(), descriptors[b])
        rows.append(dict(image_a=a,image_b=b,candidate_matches=len(matches),stored_matches=stored.get(pair)))
    return rows, dict(keypoint_counts=counts, candidate_count_scope='fresh native SIFT replay, not exact historic pre-trimming counts')


def geometry_report(database, names, candidates):
    _, pairs = read_pairs(database)
    components = connected_components(names, [(p['a'], p['b']) for p in pairs])
    path = shortest_bridge(names, [(p['a'], p['b']) for p in pairs], {ANCHORS[0]}, {ANCHORS[-1]})
    lookup = {frozenset((p['a'], p['b'])):p for p in pairs}
    annotated = [dict(**r, verified_inliers=lookup.get(frozenset((r['image_a'],r['image_b'])),{}).get('inliers',0),
                      geometry_config=lookup.get(frozenset((r['image_a'],r['image_b'])),{}).get('config',0)) for r in candidates]
    residuals=[]
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as conn:
        ids={name:i for i,name in conn.execute('SELECT image_id,name FROM images')}
        for pair in pairs:
            a,b=sorted((ids[pair['a']],ids[pair['b']]))
            count,data,fdata=conn.execute('SELECT rows,data,F FROM two_view_geometries WHERE pair_id=?',(a*MAX_ID+b,)).fetchone()
            row=dict(image_a=pair['a'],image_b=pair['b'],available=False)
            if fdata and len(fdata)==72:
                f=np.frombuffer(fdata,dtype=np.float64).reshape(3,3)
                if np.isfinite(f).all() and np.linalg.norm(f)>1e-15:
                    coordinates=[]
                    for i in (a,b):
                        n,c,blob=conn.execute('SELECT rows,cols,data FROM keypoints WHERE image_id=?',(i,)).fetchone()
                        coordinates.append(np.frombuffer(blob,dtype=np.float32).reshape(n,c)[:,:2])
                    matches=np.frombuffer(data,dtype=np.uint32).reshape(count,2)
                    x=np.column_stack((coordinates[0][matches[:,0]],np.ones(count)))
                    y=np.column_stack((coordinates[1][matches[:,1]],np.ones(count)))
                    fx=x@f.T;fty=y@f
                    den=(fx[:,:2]**2).sum(1)+(fty[:,:2]**2).sum(1)
                    valid=den>1e-20
                    err=np.abs((y*fx).sum(1)[valid])/np.sqrt(den[valid])
                    if len(err): row.update(available=True,inliers=len(err),median_px=float(np.median(err)),
                                           p95_px=float(np.quantile(err,.95)),max_px=float(err.max()))
            residuals.append(row)
    return dict(verified_pairs=len(pairs),components=components,
                isolated_views=sum(len(c)==1 for c in components),target_connected=bool(path),
                verified_endpoint_path=path,pairs=annotated,sampson_residuals=residuals)


def run(trial, comparison, out, mode, site, cache):
    import pycolmap
    trial, comparison, out = map(lambda p:Path(p).resolve(), (trial,comparison,out))
    experiment = json.loads((trial/'experiment.json').read_text())
    prior = json.loads((comparison/'comparison.json').read_text())
    window = prior['temporal_window']; names = [r['image'] for r in window]
    if len(names)!=24 or len(set(names))!=24 or set(names)!=set(ANCHORS+experiment['added_images']):
        raise ValueError('Inputs differ from the retained 24-view transition chain')
    if experiment['requested_spacing_s'] != .0625:
        raise ValueError('Expected the retained 16 Hz trial')
    inputs = {str(trial/'experiment.json'): sha256(trial/'experiment.json'),
              str(comparison/'comparison.json'): sha256(comparison/'comparison.json'),
              str(trial/'features.db'): sha256(trial/'features.db')}
    for p,h in prior['input_sha256'].items():
        if sha256(p)!=h: raise ValueError('Previously frozen comparison input changed')
    for name in names:
        p = trial/'images'/name; h=sha256(p)
        if h != experiment['image_sha256'][name]: raise ValueError('A retained image changed')
        inputs[str(p)]=h
    code = {str(p):sha256(p) for p in Path(__file__).resolve().parents[2].joinpath('floorplan').glob('*.py')}
    verification, mapper = frozen_options(pycolmap, experiment)
    out.mkdir(parents=True,exist_ok=False); images=out/'images';images.mkdir()
    for name in names: shutil.copy2(trial/'images'/name, images/name)
    started=time.perf_counter(); database=out/'features.db'
    ids=copy_database(trial/'features.db',database,names,mode=='sift',pycolmap)
    if mode=='lightglue':
        candidates, identity=learned_matches(database,images,names,ids,site,cache)
        pair_file=out/'pairs.txt'
        pair_file.write_text('\n'.join(f'{a} {b}' for a,b in itertools.combinations(names,2))+'\n')
        pycolmap.verify_matches(database,pair_file,options=verification)
    else:
        candidates, identity=sift_candidates(database,names,ids,pycolmap,experiment)
    graph=geometry_report(database,names,candidates)
    sparse=out/'sparse';sparse.mkdir()
    models=pycolmap.incremental_mapping(database,images,sparse,options=mapper)
    model_rows=[]
    for key,model in models.items():
        registered=sorted(i.name for i in model.images.values() if i.has_pose)
        model_rows.append(dict(model_id=key,image_names=registered,registered_images=len(registered),
                               sparse_points=model.num_points3D(),mean_reprojection_error_px=model.compute_mean_reprojection_error(),
                               both_endpoints_registered=set((ANCHORS[0],ANCHORS[-1])).issubset(registered),
                               binary_sha256={p.name:sha256(p) for p in (sparse/str(key)).glob('*.bin')}))
    best=max(model_rows,key=lambda r:r['registered_images']) if model_rows else None
    result=dict(experiment='retained_24_view_matcher_comparison',mode=mode,input_sha256=inputs,
                image_sha256={n:sha256(images/n) for n in names},temporal_window=window,
                options=experiment['options'],identity=identity,graph=graph,models=model_rows,
                matching_diagnostics=_matching_diagnostics(database,len(names)),
                maximum_registered_images=best['registered_images'] if best else 0,
                joint_endpoint_model=any(m['both_endpoints_registered'] for m in model_rows),
                runtime_s=time.perf_counter()-started,script_sha256=sha256(Path(__file__)),
                production_code_sha256=code,accuracy_validated=False,metric_scale=False,
                production_policy_changed=False,
                limitations=['Bounded 24-view trial, not a full-video accuracy or coverage result',
                             'SIFT uses the exact retained feature/verified-pair subset; candidate counts are a separate native replay',
                             'Same-input reproducibility is not independent physical repeatability',
                             'Camera metadata contains RGB initialization priors only; no optimized poses or sensor sidecars are used'])
    if inputs!={p:sha256(p) for p in inputs} or code!={p:sha256(p) for p in code}:
        raise ValueError('Frozen inputs or production code changed')
    (out/'experiment.json').write_text(json.dumps(result,indent=2,default=str)+'\n',encoding='utf-8')
    print(json.dumps(dict(mode=mode,verified_pairs=graph['verified_pairs'],component_sizes=[len(c) for c in graph['components']],
                         isolated_views=graph['isolated_views'],target_connected=graph['target_connected'],
                         joint_endpoint_model=result['joint_endpoint_model'],models=model_rows,
                         runtime_s=result['runtime_s']),indent=2),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trial',type=Path,default=Path('demo/phase3_video_bridge/dense_trial1'))
    p.add_argument('--comparison',type=Path,default=Path('demo/phase3_video_bridge/dense_comparison'))
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--mode',choices=('sift','lightglue'),required=True)
    p.add_argument('--site',type=Path,default=Path('.tools/lightglue_experiment/site'))
    p.add_argument('--cache',type=Path,default=Path('.tools/lightglue_cache'))
    a=p.parse_args();run(a.trial,a.comparison,a.out,a.mode,a.site,a.cache)
