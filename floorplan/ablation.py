"""Compare identical-input pose-correction runs without mistaking change for accuracy."""
import json
from pathlib import Path

from .workflow import file_hash


def compare_pose_correction(off_directory,on_directory):
    directories=[Path(off_directory),Path(on_directory)]
    ledgers=[json.loads((p/'run.json').read_text(encoding='utf-8')) for p in directories]
    off,on=ledgers
    if off.get('inputs') != on.get('inputs') or not off.get('inputs'):
        raise ValueError('Ablation requires identical hashed capture inputs')
    configs=[{k:v for k,v in d['configuration'].items() if k!='optimize_poses'} for d in ledgers]
    if configs[0]!=configs[1]: raise ValueError('Only pose correction may change in this ablation')
    if off['configuration'].get('optimize_poses',True) or not on['configuration'].get('optimize_poses',True):
        raise ValueError('Expected correction off then on')
    if off.get('code_sha256')!=on.get('code_sha256') or any(d.get('code_changed_during_run') for d in ledgers):
        raise ValueError('Ablation requires unchanged identical reconstruction code')
    rows=[]
    for mode,directory,ledger in zip(['off','on'],directories,ledgers):
        result=ledger['result']; metadata=result.get('plan_metadata',{})
        plan_path=directory/'plan.json'
        plan=json.loads(plan_path.read_text(encoding='utf-8')) if plan_path.exists() else {}
        from shapely.geometry import Polygon
        rows.append(dict(mode=mode,run_sha256=file_hash(directory/'run.json'),status=result['status'],
                         room_count=len(plan.get('rooms',[])),runtime_s=ledger['runtime_s'],
                         footprint_area_m2=sum(Polygon(r['corners']).area for r in plan.get('rooms',[])) if plan else None,
                         camera_coverage=metadata.get('camera_center_coverage_fraction'),
                         verified_loops=result.get('mapping',{}).get('verified_loops',0),
                         max_camera_translation_correction_m=result.get('mapping',{}).get('max_camera_translation_correction_m',0)))
    return dict(experiment='pose_correction_on_off',identical_inputs=True,identical_code=True,
                accuracy_improvement=None,reason='No independent surveyed reference supplied',runs=rows)
