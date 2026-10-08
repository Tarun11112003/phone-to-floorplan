"""Producer fingerprints separate model/config identity from capture identity."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def producer(data,stage='measurement'):
    root=Path(__file__).parent
    names=['sfm.py','ingest.py','capture_sync.py'] if stage=='sfm' else [
        'sfm.py','ingest.py','capture_sync.py','rgbd.py','dense.py','openmvs.py','metric_depth.py',
        'layout.py','supported_cells.py','mapping.py','stitching.py','damage.py','assessment.py',
        'assessment_io.py','contracts.py','uncertainty.py','rgb_metric.py','openings.py',
        'pose_graph.py',
        'schemas/assessment.schema.json']
    packages=['numpy','Pillow','pycolmap','opencv-python-headless']
    if stage!='sfm': packages+=['open3d','scipy','shapely','torch','transformers']
    versions={}
    for package in packages:
        try: versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: versions[package]=None
    fields=['camera_model','camera_params','camera_grouping','max_frames','matching','fps','profile']
    if stage!='sfm': fields+=['tier','dense_backend','max_pairs','optimize_poses','metric_backend','model_revision','model_sha256']
    config={key:data.get(key) for key in fields}
    if stage=='measurement' and data.get('capture_structure')=='per_room_folders':
        # Intake sets this limit from image count, rather than a different
        # measurement recipe. All 2–8 supplied images per room are considered.
        config.pop('max_frames',None)
        config['photo_selection_policy']='all supplied views considered; quality rejections disclosed'
    if data.get('metric_backend')=='moge2_experimental':
        from .rgb_metric import REVISION,CODE_REVISION,WEIGHTS_SHA256
        config['model_identity']={'revision':REVISION,'code_revision':CODE_REVISION,'sha256':WEIGHTS_SHA256}
    payload=dict(version='producer-fingerprint-v1',stage=stage,
                 code={name:sha256(root/name) for name in names},versions=versions,configuration=config,seed=7)
    return dict(fingerprint=_fingerprint(payload),details=payload)


def model_files(directory):
    return {p.name:sha256(p) for p in sorted(Path(directory).glob('*')) if p.is_file()}


def validate_sfm_cache(prior,current_inputs,current_producer,directory):
    if prior.get('inputs')!=current_inputs or not current_inputs:
        raise ValueError('SfM cache inputs differ from this capture')
    if prior.get('sfm_producer_fingerprint')!=current_producer:
        raise ValueError('SfM cache producer changed or historical cache is unversioned; regenerate it')
    recorded=prior.get('sfm_model_sha256')
    if not recorded or recorded!=model_files(directory):
        raise ValueError('SfM cache model files differ from the recorded hashes')
