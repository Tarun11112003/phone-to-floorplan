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

from .provenance import producer,model_files,validate_sfm_cache


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema_version') not in {2,3} or data.get('tier') not in {'photos','video','lidar','rgbd','assisted'}:
        raise ValueError('Capture requires schema_version=2 and tier photos/video/lidar/rgbd/assisted')
    forbidden = {'ground_truth','ground_truth_poses','reference_mesh','laser_cloud','highres_depth'}
    def keys(value):
        if isinstance(value,dict):
            for key,child in value.items():
                yield key
                yield from keys(child)
        elif isinstance(value,list):
            for child in value: yield from keys(child)
    if forbidden.intersection(keys(data)):
        raise ValueError('Reference assets belong in a benchmark suite, not a capture manifest')
    if data.get('dense_backend', 'sgbm') not in {'sgbm', 'openmvs'}:
        raise ValueError('dense_backend must be sgbm or openmvs')
    if data.get('metric_backend') not in {None,'moge2_experimental'}:
        raise ValueError('Unknown RGB metric backend')
    if data.get('profile','research') not in {'research','assignment'}:
        raise ValueError('profile must be research or assignment')
    if data.get('profile')=='assignment':
        if data['tier']=='assisted': raise ValueError('Assignment profile forbids assisted captures')
        banned={'scale_references','manual_adjacency','project'}
        if data['tier']=='photos': banned|={'poses','camera_to_world','depth','sequence','odometry','room_transforms'}
        if banned.intersection(keys(data)): raise ValueError('Assignment profile forbids supplied photo poses/depth or manual scale/adjacency')
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


def reconstruct(manifest_path: Path, output: Path, pose_correction=None):
    manifest_path = manifest_path.resolve(); output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Use a fresh output directory for a reproducible run')
    data = read_manifest(manifest_path)
    if pose_correction is not None:
        data['optimize_poses'] = bool(pose_correction)
    output.mkdir(parents=True,exist_ok=True)
    started = time.perf_counter()
    stop = threading.Event(); peak = [0]
    monitoring={}
    def monitor():
        try:
            import psutil
        except ImportError:
            monitoring['error']='psutil unavailable; memory was not measured'
            return
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
    identities={stage:producer(data,stage) for stage in ('sfm','measurement')}
    ledger['sfm_producer_fingerprint']=identities['sfm']['fingerprint']
    ledger['measurement_producer_fingerprint']=identities['measurement']['fingerprint']
    ledger['producer_details']={stage:value['details'] for stage,value in identities.items()}
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
                result=json.loads((cache/'sfm'/'sfm_summary.json').read_text(encoding='utf-8'))
                validate_sfm_cache(prior,ledger['inputs'],ledger['sfm_producer_fingerprint'],result['model_directory'])
                ledger['reused_sfm']={'source_run':str(cache),'run_sha256':file_hash(cache/'run.json'),
                    'model_files':{str(p):file_hash(p) for p in Path(result['model_directory']).glob('*') if p.is_file()}}
            else:
                result = reconstruct_rgb(root/data['source'],output/'sfm',fps=data.get('fps',2),
                    max_frames=data.get('max_frames',100),camera_model=data.get('camera_model','SIMPLE_RADIAL'),
                    camera_params=data.get('camera_params',''),matching_mode=data.get('matching','exhaustive'),quality_selection=True,
                    camera_grouping=data.get('camera_grouping','auto'),
                    required_images=sorted({o['image'] for c in data.get('scale_references',[]) for endpoint in ('a','b') for o in c[endpoint]}))
            if result.get('model_directory'):
                ledger['sfm_model_sha256']=model_files(result['model_directory'])
            if data.get('metric_backend')=='moge2_experimental':
                from .rgb_metric import reconstruct_metric_rgb
                sparse_result=result
                result=reconstruct_metric_rgb(sparse_result,output,ordered_capture=data['tier']=='video',
                                              room_groups=data.get('room_groups'),room_image_source=root/data['source'],
                                              property_id=data.get('property_id'),optimize_poses=data.get('optimize_poses',True))
                result['sparse_reconstruction']=sparse_result
                if (sparse_result.get('model_directory') and sparse_result.get('registered_fraction',0)<.9
                        and result.get('registration_coverage_source')!='verified_per_room_models'):
                    result.update(status='partial',floor_plan_ready=False,reason='Incomplete original RGB registration')
            elif result.get('model_directory'):
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
    artifact = output/'artifacts'/'plan.json'
    if artifact.exists():
        # Stable top-level filenames for consumers; detailed stage data stays nested.
        for name in ('plan.json','plan.svg','plan.dxf','quantities.csv','layout_diagnostic.svg'):
            source = artifact.parent/name
            if source.exists(): shutil.copy2(source,output/name)
    else:
        diagnostic=output/'artifacts'/'layout_diagnostic.svg'
        if diagnostic.exists(): shutil.copy2(diagnostic,output/'layout_diagnostic.svg')
    from .assessment import write_assessment
    assessment_started = time.perf_counter()
    try:
        document=write_assessment(output,ledger)
        ledger['contract_complete']=document.get('contract_complete',False)
        ledger['assessment_status'] = 'written'
    except Exception as exc:
        ledger['assessment_status'] = 'failed'
        ledger['assessment_error'] = str(exc)
        (output/'assessment_error.log').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        stop.set(); watcher.join(timeout=1)
        ledger['assessment_runtime_s'] = time.perf_counter()-assessment_started
        ledger['runtime_s'] = time.perf_counter()-started
        ledger['peak_process_tree_rss_bytes'] = peak[0]
        ledger['memory_measurement_status']='unavailable' if monitoring.get('error') else 'measured'
        if monitoring: ledger['monitoring']=monitoring
        ledger['code_sha256_at_completion'] = {p.name:file_hash(p) for p in Path(__file__).parent.glob('*.py')}
        ledger['code_changed_during_run'] = ledger['code_sha256'] != ledger['code_sha256_at_completion']
        ledger['deliverable_sha256'] = {p.name:file_hash(p) for p in output.iterdir()
                                      if p.is_file() and p.name != 'run.json'}
        ledger['geometry_artifact_sha256'] = {
            str(p.relative_to(output)).replace('\\','/'):file_hash(p)
            for name in ('cloud.npz','trajectory.json','rgbd_summary.json','layout_evidence.json')
            if (p:=output/'artifacts'/name).is_file()}
        (output/'run.json').write_text(json.dumps(ledger,indent=2),encoding='utf-8')
    return ledger


def run_capture(tier,source,output,max_frames=300,*,profile='research',calibration=None,property_id=None,experimental_rgb=False):
    """Stock-capture entry point with the same auditable intake failure path."""
    from .ingest import prepare_capture
    output=Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError(f'Use a fresh output directory: {output}')
    started=time.perf_counter()
    try:
        manifest=prepare_capture(tier,source,output/'intake',max_frames)
        data=json.loads(manifest.read_text(encoding='utf-8'))
        data['profile']=profile
        if experimental_rgb:
            if tier not in {'photos','video'}: raise ValueError('Experimental RGB backend only accepts photos/video')
            data['metric_backend']='moge2_experimental'
        if calibration is not None: data['calibration']=str(Path(calibration).resolve())
        if property_id is not None: data['property_id']=str(property_id)
        manifest.write_text(json.dumps(data,indent=2),encoding='utf-8')
        ledger=reconstruct(manifest,output/'result')
    except Exception as exc:
        result_dir=output/'result'
        # An existing reconstruction ledger is never overwritten by this wrapper.
        if (result_dir/'run.json').exists(): raise
        result_dir.mkdir(parents=True,exist_ok=True)
        data=dict(schema_version=3,tier=tier,source=str(Path(source).resolve()),profile=profile)
        if property_id is not None: data['property_id']=str(property_id)
        attempt=output/'capture_attempt.json'
        attempt.write_text(json.dumps(data,indent=2),encoding='utf-8')
        ledger=dict(run_id=str(uuid.uuid4()),manifest=str(attempt),manifest_sha256=file_hash(attempt),
                    configuration=data,tier=tier,accuracy_validated=False,contract_complete=False,
                    result=dict(status='failed',floor_plan_ready=False,stage='intake_or_preflight',
                                reason=str(exc),error_type=type(exc).__name__),
                    runtime_s=time.perf_counter()-started)
        (result_dir/'error.log').write_text(traceback.format_exc(),encoding='utf-8')
        from .assessment import write_assessment
        try:
            write_assessment(result_dir,ledger)
            ledger['assessment_status']='written'
        except Exception as report_exc:
            ledger.update(assessment_status='failed',assessment_error=str(report_exc))
        (result_dir/'run.json').write_text(json.dumps(ledger,indent=2),encoding='utf-8')
    ledger['capture_runtime_s']=time.perf_counter()-started
    (output/'result'/'run.json').write_text(json.dumps(ledger,indent=2),encoding='utf-8')
    return ledger


def run_succeeded(ledger):
    return bool(ledger.get('result',{}).get('floor_plan_ready')
                and ledger.get('assessment_status')=='written'
                and (ledger.get('configuration',{}).get('profile','research')!='assignment'
                     or (ledger.get('contract_complete') is True and not ledger['result'].get('experimental_backend'))))
