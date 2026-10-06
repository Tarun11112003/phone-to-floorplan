"""Common capture entry point and reproducible run ledger."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import shutil
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema_version') != 2 or data.get('tier') not in {'photos','video','lidar','rgbd','assisted'}:
        raise ValueError('Capture requires schema_version=2 and tier photos/video/lidar/rgbd/assisted')
    forbidden = {'ground_truth','ground_truth_poses','reference_mesh','laser_cloud','highres_depth'}
    if forbidden.intersection(data):
        raise ValueError('Reference assets belong in a benchmark suite, not a capture manifest')
    if data.get('dense_backend', 'sgbm') not in {'sgbm', 'openmvs'}:
        raise ValueError('dense_backend must be sgbm or openmvs')
    return data


def _input_files(data, root):
    paths = set()
    for key in ('source','sequence','project'):
        if key in data:
            path = (root/data[key]).resolve()
            if path.is_dir():
                paths.update(p for p in path.rglob('*') if p.is_file())
            else:
                paths.add(path)
                if key == 'sequence' and path.is_file():
                    seq = json.loads(path.read_text(encoding='utf-8'))
                    for frame in seq['frames']:
                        paths.update((path.parent/frame[k]).resolve() for k in ('rgb','depth','confidence') if k in frame)
    return paths


def reconstruct(manifest_path: Path, output: Path):
    manifest_path = manifest_path.resolve(); output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Use a fresh output directory for a reproducible run')
    data = read_manifest(manifest_path)
    output.mkdir(parents=True,exist_ok=True)
    started = time.perf_counter()
    stop = threading.Event(); peak = [0]
    def monitor():
        import psutil
        process = psutil.Process()
        while not stop.is_set():
            try:
                peak[0] = max(peak[0],sum(p.memory_info().rss for p in [process]+process.children(recursive=True) if p.is_running()))
            except psutil.Error:
                pass
            stop.wait(0.2)
    watcher = threading.Thread(target=monitor,daemon=True); watcher.start()
    versions = {}
    for package in ('numpy','opencv-python-headless','pycolmap','open3d','shapely','ezdxf'):
        try: versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: pass
    ledger = {'run_id':str(uuid.uuid4()),'started_utc':datetime.now(timezone.utc).isoformat(),
              'manifest':str(manifest_path),'manifest_sha256':file_hash(manifest_path),'configuration':data,
              'python':platform.python_version(),'platform':platform.platform(),'versions':versions,
              'tier':data['tier'],'accuracy_validated':False}
    ledger['code_sha256']={p.name:file_hash(p) for p in Path(__file__).parent.glob('*.py')}
    result = {'status':'failed','floor_plan_ready':False}
    try:
        ledger['inputs'] = {str(p):file_hash(p) for p in sorted(_input_files(data,manifest_path.parent))}
        root = manifest_path.parent
        if data['tier'] == 'assisted':
            from .pipeline import run_project
            plan = run_project(root/data['project'],output/'artifacts')
            result = {'status':'assisted_proposal','floor_plan_ready':False,'plan_produced':True,
                      'assistance':'manually annotated floor corners and doorway anchors',
                      'metric_scale':all(r['metric_status']!='unscaled' for r in plan['rooms'])}
        elif data['tier'] in {'rgbd','lidar'}:
            from .rgbd import reconstruct_rgbd
            sequence_path = (root/data['sequence']).resolve()
            sequence = json.loads(sequence_path.read_text(encoding='utf-8'))
            for frame in sequence['frames']:
                for key in ('rgb','depth','confidence'):
                    if key in frame:
                        frame[key] = str((sequence_path.parent/frame[key]).resolve())
            sequence.update(layout='polygons',optimize_poses=data.get('optimize_poses',True))
            if 'down_direction' in data: sequence['down_direction'] = data['down_direction']
            normalized = output/'normalized_sequence.json'
            normalized.write_text(json.dumps(sequence,indent=2),encoding='utf-8')
            result = reconstruct_rgbd(normalized,output/'artifacts',data.get('max_frames'))
        else:
            from .sfm import reconstruct_rgb
            if data.get('sfm_cache'):
                cache=(root/data['sfm_cache']).resolve()
                prior=json.loads((cache/'run.json').read_text(encoding='utf-8'))
                if prior['inputs'] != ledger['inputs']:
                    raise ValueError('SfM cache inputs differ from this capture')
                for key in ('camera_model','camera_params','max_frames','matching','fps'):
                    if prior['configuration'].get(key) != data.get(key):
                        raise ValueError(f'SfM cache configuration changed: {key}')
                result=json.loads((cache/'sfm'/'sfm_summary.json').read_text(encoding='utf-8'))
                ledger['reused_sfm']={'source_run':str(cache),'run_sha256':file_hash(cache/'run.json'),
                    'model_files':{str(p):file_hash(p) for p in Path(result['model_directory']).glob('*') if p.is_file()}}
            else:
                result = reconstruct_rgb(root/data['source'],output/'sfm',fps=data.get('fps',2),
                    max_frames=data.get('max_frames',100),camera_model=data.get('camera_model','SIMPLE_RADIAL'),
                    camera_params=data.get('camera_params',''),matching_mode=data.get('matching','exhaustive'),quality_selection=True,
                    required_images=sorted({o['image'] for c in data.get('scale_references',[]) for endpoint in ('a','b') for o in c[endpoint]}))
            if result.get('model_directory'):
                if not data.get('scale_references'):
                    result.update(status='scale_unresolved',reason='Provide measured scale endpoints in at least two registered images')
                else:
                    sparse_result = result
                    backend = data.get('dense_backend', 'sgbm')
                    if backend == 'openmvs':
                        from .openmvs import reconstruct_openmvs
                        result = reconstruct_openmvs(Path(result['model_directory']), Path(result['images_directory']),
                            output/'artifacts', data['scale_references'],
                            ordered_capture=data.get('ordered_capture', data['tier']=='video'))
                    elif backend == 'sgbm':
                        from .dense import reconstruct_dense
                        result = reconstruct_dense(Path(result['model_directory']),Path(result['images_directory']),output/'artifacts',
                                                   data['scale_references'],data.get('max_pairs',80),
                                                   ordered_capture=data.get('ordered_capture',data['tier']=='video'))
                    else:
                        raise ValueError(f'Unknown dense_backend: {backend}')
                    result['sparse_reconstruction'] = sparse_result
                    if sparse_result['registered_fraction'] < 0.9 and result.get('plan_produced'):
                        result.update(status='partial',floor_plan_ready=False)
        ledger['result'] = result
    except Exception as exc:
        (output/'error.log').write_text(traceback.format_exc(),encoding='utf-8')
        result = {'status':'failed','floor_plan_ready':False,'error_type':type(exc).__name__,'reason':str(exc)}
        ledger['result'] = result
    finally:
        stop.set(); watcher.join(timeout=1)
        ledger['runtime_s'] = time.perf_counter()-started
        ledger['peak_process_tree_rss_bytes'] = peak[0]
        ledger['code_sha256_at_completion'] = {p.name:file_hash(p) for p in Path(__file__).parent.glob('*.py')}
        ledger['code_changed_during_run'] = ledger['code_sha256'] != ledger['code_sha256_at_completion']
        (output/'run.json').write_text(json.dumps(ledger,indent=2),encoding='utf-8')
    artifact = output/'artifacts'/'plan.json'
    if artifact.exists():
        # Stable top-level filenames for consumers; detailed stage data stays nested.
        for name in ('plan.json','plan.svg','plan.dxf','quantities.csv'):
            source = artifact.parent/name
            if source.exists(): shutil.copy2(source,output/name)
    return ledger
