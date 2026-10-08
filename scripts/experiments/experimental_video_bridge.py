"""Bounded RGB-only bridge-view experiment; never changes production policy.

Clone the frozen baseline database, retain every old image and guard, and add
quality-qualified original MP4 frames only within the specified source interval.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image

from floorplan.provenance import sha256
import floorplan.sfm as sfm
from scripts.diagnostics.audit_sfm_components import audit, connected_components


def read_pairs(database):
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True) as conn:
        names = dict(conn.execute('SELECT image_id, name FROM images'))
        rows = conn.execute('SELECT pair_id, rows, config FROM two_view_geometries WHERE rows>0 ORDER BY pair_id').fetchall()
    return names, [dict(a=names[p//2147483647], b=names[p%2147483647], inliers=n, config=c) for p,n,c in rows]


def shortest_bridge(nodes, pairs, left, right):
    """Report a verified graph path; never infer a camera pose from this path."""
    neighbors = {n:set() for n in nodes}
    for a,b in pairs:
        neighbors[a].add(b); neighbors[b].add(a)
    parent = {n:None for n in sorted(left)}; pending = deque(sorted(left))
    while pending:
        node = pending.popleft()
        if node in right:
            path = []
            while node is not None:
                path.append(node); node = parent[node]
            return path[::-1]
        for other in sorted(neighbors[node]):
            if other not in parent:
                parent[other] = node; pending.append(other)
    return []


def baseline_digest(database):
    """Per-row digests allow exact preservation checks including zero-pair rows."""
    result = {}
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True) as conn:
        for table in ('cameras','images','keypoints','descriptors','matches','two_view_geometries'):
            rows = conn.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall()
            result[table] = {str(row[0]):hashlib.sha256(json.dumps(
                [dict(blob_sha256=hashlib.sha256(v).hexdigest()) if isinstance(v,bytes) else v for v in row],
                sort_keys=True).encode()).hexdigest() for row in rows}
    return result


def bridge_diagnostics(database, original_database, added):
    _, old_pairs = read_pairs(original_database); names, pairs = read_pairs(database)
    old_nodes = sorted({n for p in old_pairs for n in (p['a'],p['b'])})
    old_groups = connected_components(old_nodes, [(p['a'],p['b']) for p in old_pairs])
    left, right = map(set, old_groups[:2])
    new_pairs = [p for p in pairs if p['a'] in added or p['b'] in added]
    graph_path = shortest_bridge(names.values(), [(p['a'],p['b']) for p in pairs], left, right)
    edge_lookup = {frozenset((p['a'],p['b'])):p for p in pairs}
    path_pairs = [edge_lookup[frozenset((a,b))] for a,b in zip(graph_path[:-1],graph_path[1:])]
    # Check epipolar residuals of actual verified bridge inliers, in pixel units.
    consistency = []
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True) as conn:
        ids = {name:identifier for identifier,name in names.items()}
        for pair in new_pairs:
            a,b = sorted((ids[pair['a']],ids[pair['b']]))
            pid = a*2147483647+b
            count, data, fdata = conn.execute('SELECT rows,data,F FROM two_view_geometries WHERE pair_id=?',(pid,)).fetchone()
            row = dict(**pair, sampson_residual_available=False)
            if fdata and len(fdata)==72:
                f = np.frombuffer(fdata, dtype=np.float64).reshape(3,3)
                if np.isfinite(f).all() and np.linalg.norm(f)>1e-15:
                    coordinates = []
                    for identifier in (a,b):
                        n,c,blob = conn.execute('SELECT rows,cols,data FROM keypoints WHERE image_id=?',(identifier,)).fetchone()
                        coordinates.append(np.frombuffer(blob,dtype=np.float32).reshape(n,c)[:,:2])
                    matches = np.frombuffer(data,dtype=np.uint32).reshape(count,2)
                    x = np.column_stack((coordinates[0][matches[:,0]],np.ones(count)))
                    y = np.column_stack((coordinates[1][matches[:,1]],np.ones(count)))
                    fx = x@f.T; fty = y@f
                    denominator = (fx[:,:2]**2).sum(1)+(fty[:,:2]**2).sum(1)
                    usable = denominator>1e-20
                    error = np.abs((y*fx).sum(1)[usable])/np.sqrt(denominator[usable])
                    if len(error):
                        row.update(sampson_residual_available=True, usable_inliers=len(error),
                                   median_sampson_px=float(np.median(error)),p95_sampson_px=float(np.quantile(error,.95)),
                                   max_sampson_px=float(error.max()))
            consistency.append(row)
    return dict(added_view_verified_pairs=new_pairs,added_view_verified_pair_count=len(new_pairs),
                target_groups=[sorted(left),sorted(right)],target_groups_connected=bool(graph_path),
                shortest_verified_bridge_path=graph_path,bridge_path_pairs=path_pairs,
                bridge_pair_consistency=consistency)


def run(baseline, source, out, reuse_images=None, spacing_s=.125):
    import pycolmap
    baseline,source,out = (Path(p).resolve() for p in (baseline,source,out))
    if spacing_s not in (.125,.0625):
        raise ValueError('Only the declared 8 Hz baseline and bounded 16 Hz alternative are supported')
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    summary = json.loads((baseline/'sfm_summary.json').read_text(encoding='utf-8'))
    if (summary['camera_mode'],summary['camera_model'],summary['matching_method'],summary['random_seed']) != ('AUTO','SIMPLE_RADIAL','exhaustive',7):
        raise ValueError('Experiment requires the frozen AUTO/exhaustive baseline')
    ledger = json.loads((baseline.parent/'run.json').read_text(encoding='utf-8'))
    if ledger['code_sha256']['sfm.py'] != sha256(Path(sfm.__file__)):
        raise ValueError('SfM producer differs from retained baseline')
    if ledger['versions']['pycolmap'] != pycolmap.__version__:
        raise ValueError('COLMAP version differs from baseline')
    before_code = {p.name:sha256(p) for p in Path(sfm.__file__).parent.glob('*.py')}
    images = out/'images'; images.mkdir()
    old_images = Path(summary['images_directory'])
    old_names = summary['feature_extraction_order']
    baseline_files = [baseline/'features.db',baseline/'sfm_summary.json',baseline.parent/'run.json']+[old_images/n for n in old_names]
    inputs = {str(p):sha256(p) for p in baseline_files}
    source_hash = sha256(source)
    if ledger['inputs'].get(str(source)) != source_hash:
        raise ValueError('Original MP4 differs from frozen input')
    inputs[str(source)] = source_hash
    for name in old_names:
        shutil.copy2(old_images/name,images/name)
    selected = []; extraction = []
    if reuse_images is not None:
        prior = Path(reuse_images).resolve()
        record = json.loads((prior/'experiment.json').read_text(encoding='utf-8'))
        if record['input_sha256'] != inputs:
            raise ValueError('Repeat trial input differs')
        if record['requested_spacing_s'] != spacing_s:
            raise ValueError('Repeat sampling recipe differs')
        for name,value in record['image_sha256'].items():
            if sha256(prior/'images'/name)!=value:
                raise ValueError('Retained repeat image changed')
        selected = record['added_images']; extraction = record['extraction']
        for name in selected:
            shutil.copy2(prior/'images'/name,images/name)
    else:
        candidates = out/'candidates'; candidates.mkdir()
        graph = f"select='between(t,11.55,13.066667)*if(isnan(prev_selected_t),1,gte(t-prev_selected_t,{spacing_s}))',showinfo"
        command = [imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','info','-i',str(source),'-vf',graph,
                   '-vsync','0','-frames:v','32',str(candidates/'bridge_%05d.png')]
        result = subprocess.run(command, check=True,capture_output=True,text=True,timeout=120)
        (out/'ffmpeg.log').write_text(result.stderr,encoding='utf-8')
        timestamps = [float(t) for t in re.findall(r'\bpts_time:([-+\d.eE]+)',result.stderr)]
        files = sorted(candidates.glob('*.png'))
        if len(timestamps)!=len(files):
            raise ValueError('Original frame timestamps do not match candidate count')
        old_mapping = json.loads((baseline/'video_frame_mapping.json').read_text(encoding='utf-8'))
        old_times = {r['image']:r['source_timestamp_s'] for r in old_mapping if r['image'] in old_names}
        expected_size = Image.open(old_images/old_names[0]).size
        for path,timestamp in zip(files,timestamps):
            with Image.open(path) as im:
                image = im.convert('RGB')
                if image.size!=expected_size:
                    raise ValueError('Bridge resolution differs from baseline')
                gray = cv2.cvtColor(np.asarray(image.resize((320,240))),cv2.COLOR_RGB2GRAY)
                sharpness = float(cv2.Laplacian(gray,cv2.CV_64F).var())
                duplicate = any(abs(timestamp-t)<.009 for t in old_times.values())
                accepted = sharpness>=10 and not duplicate
                extraction.append(dict(image=path.name,source_timestamp_s=timestamp,sharpness=sharpness,
                                       accepted=accepted,reason='duplicate_source_time' if duplicate else 'selected' if accepted else 'blurred'))
                if accepted:
                    image.save(images/path.name,exif=image.getexif()); selected.append(path.name)
    if not selected:
        raise ValueError('No new bridge frame passed existing quality guard; inspect retained extraction')
    print(f'Added {len(selected)} views to {len(old_names)} frozen views',flush=True)
    database = out/'features.db'
    with sqlite3.connect((baseline/'features.db').as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(database) as dst:
        src.backup(dst)
    before_rows = baseline_digest(baseline/'features.db')
    feature_opts = pycolmap.FeatureExtractionOptions(num_threads=1)
    match_opts = pycolmap.FeatureMatchingOptions(num_threads=1)
    verify_opts = pycolmap.TwoViewGeometryOptions(); verify_opts.ransac.random_seed = sfm.SFM_RANDOM_SEED
    reader = pycolmap.ImageReaderOptions(camera_model=summary['camera_model'],camera_params=summary['camera_params'])
    pycolmap.extract_features(database,images,image_names=sorted(selected),camera_mode=pycolmap.CameraMode.AUTO,
                             reader_options=reader,extraction_options=feature_opts,device=pycolmap.Device.cpu)
    pycolmap.match_exhaustive(database,matching_options=match_opts,verification_options=verify_opts,device=pycolmap.Device.cpu)
    after_rows = baseline_digest(database)
    preservation = {table:all(after_rows[table].get(key)==value for key,value in rows.items()) for table,rows in before_rows.items()}
    if not all(preservation.values()):
        raise ValueError(f'Original database records changed: {preservation}')
    sparse = out/'sparse'; sparse.mkdir()
    mapper = pycolmap.IncrementalPipelineOptions(num_threads=1,random_seed=sfm.SFM_RANDOM_SEED)
    mapper.mapper.num_threads=1; mapper.mapper.random_seed=sfm.SFM_RANDOM_SEED
    mapper.triangulation.random_seed=sfm.SFM_RANDOM_SEED
    mapper.min_model_size=min(mapper.min_model_size,len(old_names)+len(selected))
    models = pycolmap.incremental_mapping(database,images,sparse,options=mapper)
    best_id,best = max(models.items(),key=lambda row:row[1].num_reg_images()) if models else (None,None)
    result = dict(summary)
    result.update(input_images=len(old_names)+len(selected),registered_images=best.num_reg_images() if best else 0,
                  registered_fraction=best.num_reg_images()/(len(old_names)+len(selected)) if best else 0,
                  sparse_points=best.num_points3D() if best else 0,model_directory=str(sparse/str(best_id)) if best else None,
                  images_directory=str(images),feature_extraction_order=old_names+sorted(selected),
                  matching_diagnostics=sfm._matching_diagnostics(database,len(old_names)+len(selected)),
                  status='partial' if best else 'no_model',metric_scale=False,floor_plan_ready=False)
    # No stale baseline output path is allowed to imply a generated cloud.
    result.pop('point_cloud',None)
    (out/'sfm_summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    model_audit = audit(out,out/'component_audit')
    diagnostics = bridge_diagnostics(database,baseline/'features.db',set(selected))
    all_models = [pycolmap.Reconstruction(p.parent) for p in sparse.glob('*/images.bin')]
    left,right = map(set,diagnostics['target_groups'])
    joint_models = [sorted(i.name for i in model.images.values() if i.has_pose) for model in all_models
                    if any(i.name in left and i.has_pose for i in model.images.values())
                    and any(i.name in right and i.has_pose for i in model.images.values())]
    experiment = dict(experiment='bounded_original_rgb_bridge_trial',input_sha256=inputs,
                      image_sha256={p.name:sha256(p) for p in images.glob('*.png')},
                      script_sha256=sha256(Path(__file__)),code_sha256=before_code,
                      versions=dict(pycolmap=pycolmap.__version__,opencv=cv2.__version__,numpy=np.__version__),
                      interval_s=[11.55,13.066667],requested_spacing_s=spacing_s,extraction=extraction,added_images=selected,
                      baseline_rows_preserved=preservation,
                      options={name:opts.todict() for name,opts in [('features',feature_opts),('matching',match_opts),('verification',verify_opts),('mapping',mapper)]},
                      diagnostics=diagnostics,component_audit_sha256=sha256(out/'component_audit/audit.json'),
                      joint_target_sparse_models=joint_models,registered_images=result['registered_images'],
                      runtime_s=time.perf_counter()-started,accuracy_validated=False,production_policy_changed=False,
                      limitations=['Cached old features/pairs; runtime is not a fresh full-reconstruction speed comparison',
                                   'Verified graph paths alone do not prove common-coordinate 3D geometry',
                                   'Unscaled RGB poses and reprojection residuals do not demonstrate physical accuracy'])
    if inputs!={str(p):sha256(p) for p in baseline_files+[source]} or before_code!={p.name:sha256(p) for p in Path(sfm.__file__).parent.glob('*.py')}:
        raise ValueError('Original inputs or production code changed during trial')
    (out/'experiment.json').write_text(json.dumps(experiment,indent=2,default=str)+'\n',encoding='utf-8')
    print(json.dumps(dict(added_views=len(selected),verified_pairs=model_audit['verified_pairs'],
                         component_sizes=[c['images'] for c in model_audit['pair_components']],
                         new_verified_pairs=diagnostics['added_view_verified_pair_count'],
                         target_groups_connected=diagnostics['target_groups_connected'],
                         joint_target_sparse_models=joint_models,registered_images=result['registered_images']),indent=2),flush=True)
    return experiment


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--reuse-images',type=Path)
    parser.add_argument('--spacing-s',type=float,choices=(.125,.0625),default=.125)
    args=parser.parse_args();run(args.baseline,args.source,args.out,args.reuse_images,args.spacing_s)
