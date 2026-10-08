"""Compare identical-input pose-correction runs without mistaking change for accuracy."""
import json
from pathlib import Path

from .workflow import file_hash


def _verified_constraints(mapping):
    """Count auditable accepted geometric edges, including segmented graphs.

    A loop is one correction mechanism, not the only allowed pose-graph edge.
    Raw pose priors and summary counters alone do not establish verification.
    """
    import numpy as np
    sequential=loops=0
    for edge in mapping.get('edges',[]):
        try:
            values=np.asarray([edge['fitness'],edge['rmse_m'],edge['icp_rotation_correction_deg']],float)
        except (KeyError,TypeError,ValueError):
            continue
        if (values.shape!=(3,) or not np.isfinite(values).all()
                or edge.get('icp_accepted') is not True
                or edge.get('constraint_source')!='verified_icp'
                or values[0]<.3 or not 0<=values[1]<.04 or not 0<=values[2]<5):
            continue
        if edge.get('loop') is True: loops+=1
        else: sequential+=1
    for segment in mapping.get('segments',[]):
        child=_verified_constraints(segment)
        sequential+=child['sequential_icp']; loops+=child['loop_icp']
    return dict(sequential_icp=sequential,loop_icp=loops,total=sequential+loops)


def compare_pose_correction(off_directory,on_directory,reference=None):
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
    for directory,ledger,expected in zip(directories,ledgers,[False,True]):
        sequence_path=directory/'normalized_sequence.json'
        if sequence_path.exists():
            sequence=json.loads(sequence_path.read_text(encoding='utf-8'))
            if sequence.get('optimize_poses') is not expected:
                raise ValueError('Normalized sequence does not honor the requested pose-correction mode')
        if not expected and ledger['result'].get('mapping',{}).get('enabled'):
            raise ValueError('Correction-off run actually enabled pose optimization')
    rows=[]
    for mode,directory,ledger in zip(['off','on'],directories,ledgers):
        result=ledger['result']; metadata=result.get('plan_metadata',{})
        plan_path=directory/'plan.json'
        plan=json.loads(plan_path.read_text(encoding='utf-8')) if plan_path.exists() else {}
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        polygons=[Polygon(r['corners']) for r in plan.get('rooms',[])]
        rows.append(dict(mode=mode,run_sha256=file_hash(directory/'run.json'),status=result['status'],
                         room_count=len(plan.get('rooms',[])),runtime_s=ledger['runtime_s'],
                         footprint_area_m2=float(unary_union(polygons).area) if polygons else None,
                         summed_room_area_m2=sum(p.area for p in polygons) if polygons else None,
                         room_overlap_area_m2=sum(polygons[i].intersection(polygons[j]).area for i in range(len(polygons)) for j in range(i)),
                         camera_coverage=metadata.get('camera_center_coverage_fraction'),
                         verified_loops=result.get('mapping',{}).get('verified_loops',0),
                         max_camera_translation_correction_m=result.get('mapping',{}).get('max_camera_translation_correction_m',0),
                         adjacency_count=len(plan.get('connections',[])),
                         correction_requested=ledger['configuration'].get('optimize_poses',True),
                         correction_applied=result.get('mapping',{}).get('enabled',False),
                         verified_constraints=_verified_constraints(result.get('mapping',{}))))
        if reference is not None:
            from .assignment_gates import evaluate_assignment
            from .assessment_io import load_document
            rows[-1]['surveyed_gates']=evaluate_assignment(load_document(directory),reference,ledger['tier'])
    trajectories=[]
    for directory in directories:
        path=directory/'artifacts/trajectory.json'
        trajectories.append({str(p['frame_id']):p['camera_to_first'] for p in json.loads(path.read_text())} if path.exists() else {})
    import numpy as np
    ids=sorted(set(trajectories[0])&set(trajectories[1])); translations=[]; rotations=[]
    for key in ids:
        a,b=(np.asarray(t[key],float) for t in trajectories)
        translations.append(float(np.linalg.norm(a[:3,3]-b[:3,3])))
        rotations.append(float(np.degrees(np.arccos(np.clip((np.trace(a[:3,:3].T@b[:3,:3])-1)/2,-1,1)))))
    changed=bool(translations and (max(translations)>1e-6 or max(rotations)>1e-4))
    return dict(experiment='pose_correction_on_off',identical_inputs=True,identical_code=True,
                accuracy_improvement=None,
                reason='Surveyed per-gate errors reported; no aggregate improvement assumed' if reference is not None else 'No independent surveyed reference supplied',
                pose_comparison=dict(shared_frames=len(ids),missing_off=sorted(set(trajectories[1])-set(trajectories[0])),
                    missing_on=sorted(set(trajectories[0])-set(trajectories[1])),
                    max_translation_change_m=max(translations) if translations else None,
                    max_rotation_change_deg=max(rotations) if rotations else None),
                verified_drift_correction_demonstrated=bool(changed and rows[1]['correction_applied']
                    and rows[1]['verified_constraints']['total']>0),
                correction_evidence_scope='Changed poses with verified geometric pose-graph constraints; not independent accuracy proof',
                runs=rows)
