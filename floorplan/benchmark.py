"""Independent polygon/topology evaluation, invoked only after reconstruction."""
from __future__ import annotations

import json
from pathlib import Path
import re
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon


def _rigid(a,b):
    ac,bc = a.mean(axis=0),b.mean(axis=0)
    u,_,vt = np.linalg.svd((a-ac).T @ (b-bc))
    correction = np.eye(2); correction[-1,-1] = np.linalg.det(u@vt)
    rotation = u@correction@vt
    return rotation, bc-ac@rotation


def _global_alignment(actual,expected,mode):
    if mode == 'identity': return np.eye(2),np.zeros(2)
    if mode != 'rigid': raise ValueError('Alignment must be identity or rigid; rescaling is forbidden')
    tree = cKDTree(expected)
    options = []
    for angle in np.linspace(0,2*np.pi,16,endpoint=False):
        rotation = np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        translation = expected.mean(axis=0)-actual.mean(axis=0)@rotation
        for _ in range(30):
            _,ids = tree.query(actual@rotation+translation)
            rotation,translation = _rigid(actual,expected[ids])
        distances,_ = tree.query(actual@rotation+translation)
        reverse,_ = cKDTree(actual@rotation+translation).query(expected)
        options.append((np.mean(distances**2)+np.mean(reverse**2),rotation,translation))
    _,rotation,translation = min(options,key=lambda x:x[0])
    return rotation,translation


def evaluate_polygons(plan,truth,alignment='rigid'):
    predicted = plan.get('rooms',[]); reference = truth['rooms']
    if not reference: raise ValueError('Reference contains no rooms')
    if any(r.get('metric_status') == 'unscaled' for r in predicted):
        raise ValueError('Cannot evaluate metric accuracy without metric scale')
    expected = [np.asarray(r['corners'],float) for r in reference]
    actual = [np.asarray(r['corners'],float) for r in predicted]
    for points in actual+expected:
        polygon = Polygon(points)
        if not np.isfinite(points).all() or not polygon.is_valid or polygon.area <= 0:
            raise ValueError('Invalid reference or predicted polygon')
    rotation,translation = _global_alignment(np.concatenate(actual),np.concatenate(expected),alignment) if actual else (np.eye(2),np.zeros(2))
    actual = [a@rotation+translation for a in actual]
    costs = np.ones((len(actual),len(expected)))
    for i,a in enumerate(actual):
        for j,b in enumerate(expected):
            pa,pb = Polygon(a),Polygon(b)
            costs[i,j] = 1-pa.intersection(pb).area/pa.union(pb).area
    row,col = linear_sum_assignment(costs)
    matches = [(i,j) for i,j in zip(row,col) if costs[i,j] < 0.8]
    dimensions,corners,areas,covered,total,opening_errors = [],[],[],0,0,[],
    matched_ids = {}; room_results = []
    exclusions = {(str(e['room_id']),int(e['edge_index'])) for e in truth.get('excluded_evaluation_edges',[])}
    for i,j in matches:
        a,b = actual[i],expected[j]
        matched_ids[predicted[i]['id']] = reference[j]['id']
        boundary = Polygon(a).boundary
        for edge,(start,end) in enumerate(zip(b,np.roll(b,-1,axis=0))):
            length = np.linalg.norm(end-start)
            count = max(2,int(np.ceil(length/0.01)))
            samples = start+(end-start)*((np.arange(count)+0.5)/count)[:,None]
            covered += length*np.mean([boundary.distance(Point(p)) <= 0.05 for p in samples])
            total += length
        areas.append(abs(Polygon(a).area-Polygon(b).area))
        corner_errors = None
        if len(a) == len(b):
            variants = [np.roll(order,shift,axis=0) for order in (a,a[::-1]) for shift in range(len(a))]
            ordered = min(variants,key=lambda v:np.sum((v-b)**2))
            corner_errors = np.linalg.norm(ordered-b,axis=1).tolist(); corners.extend(corner_errors)
            errors = np.abs(np.linalg.norm(np.roll(ordered,-1,axis=0)-ordered,axis=1)-np.linalg.norm(np.roll(b,-1,axis=0)-b,axis=1))
            dimensions.extend(float(error) for edge,error in enumerate(errors) if (str(reference[j]['id']),edge) not in exclusions)
        room_results.append({'prediction':predicted[i]['id'],'reference':reference[j]['id'],'iou':1-costs[i,j],
                             'corner_errors_m':corner_errors,'corner_count_match':len(a)==len(b)})
    matched_reference = {j for _,j in matches}
    total += sum(Polygon(b).length for j,b in enumerate(expected) if j not in matched_reference)
    def links(source,mapping=None):
        values = set()
        for c in source.get('connections',[]):
            ids = c['rooms']
            if mapping is not None:
                ids = [mapping.get(v,'unmatched:'+v) for v in ids]
            values.add(tuple(sorted(ids)))
        return values
    predicted_links,expected_links = links(plan,matched_ids),links(truth)
    for connection in plan.get('connections',[]):
        key = tuple(sorted(matched_ids.get(v,'unmatched:'+v) for v in connection['rooms']))
        target = next((c for c in truth.get('connections',[]) if tuple(sorted(c['rooms']))==key),None)
        if target and 'width_m' in target and 'width_m' in connection:
            opening_errors.append(abs(connection['width_m']-target['width_m']))
    p95_dim = float(np.percentile(dimensions,95)) if dimensions else None
    p95_corner = float(np.percentile(corners,95)) if corners else None
    coverage = covered/total if total else 0
    topology = len(matches)==len(actual)==len(expected) and predicted_links==expected_links
    all_corners = all(r['corner_count_match'] for r in room_results) and len(matches)==len(expected)
    wall_targets = bool(topology and all_corners and coverage>=0.9 and p95_dim is not None and p95_dim<=0.03 and p95_corner is not None and p95_corner<=0.05)
    expected_openings = sum('width_m' in c for c in truth.get('connections', []))
    p95_opening = float(np.percentile(opening_errors,95)) if opening_errors else None
    opening_targets = len(opening_errors)==expected_openings and (not expected_openings or p95_opening<=0.03)
    return {'alignment':{'mode':alignment,'rotation':rotation.tolist(),'translation_m':translation.tolist(),'scale':1},
            'room_matches':room_results,'missing_rooms':len(expected)-len(matches),'extra_rooms':len(actual)-len(matches),
            'dimension_count':len(dimensions),'dimension_errors_m':dimensions,'corner_count':len(corners),
            'p95_dimension_error_m':p95_dim,'p95_corner_error_m':p95_corner,'boundary_coverage_at_5cm':coverage,
            'max_area_error_m2':max(areas) if areas else None,'opening_width_errors_m':opening_errors,
            'p95_opening_width_error_m':p95_opening, 'opening_width_targets_met':opening_targets,
            'wall_geometry_targets_met':wall_targets,
            'missing_connections':sorted(expected_links-predicted_links),'extra_connections':sorted(predicted_links-expected_links),
            'topology_correct':topology,'excluded_control_edges':len(exclusions),
            'reference_provenance':truth.get('provenance'),
            'reference_uncertainty_m':truth.get('provenance',{}).get('annotation_uncertainty_floor_m') if isinstance(truth.get('provenance'),dict) else None,
            'targets_met':wall_targets and opening_targets}


def run_suite(suite_path: Path,output: Path):
    from .workflow import reconstruct
    suite = json.loads(suite_path.read_text(encoding='utf-8'))
    if output.exists() and any(output.iterdir()): raise FileExistsError('Benchmark output must be fresh')
    output.mkdir(parents=True,exist_ok=True)
    cases = []; ids = set()
    for case in suite['cases']:
        name = case['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+',name) or name in ids: raise ValueError('Unique simple case IDs required')
        ids.add(name)
        print(f'Benchmark: {name}',flush=True)
        record = {'id':name,'category':case.get('category','unspecified'),'targets_met':False}
        try:
            ledger = reconstruct(suite_path.parent/case['capture'],output/name)
            record.update(status=ledger['result']['status'],runtime_s=ledger['runtime_s'],peak_rss_bytes=ledger['peak_process_tree_rss_bytes'])
            record['reason']=ledger['result'].get('reason',ledger['result'].get('geometry_failure'))
            plan_path = output/name/'plan.json'
            if plan_path.exists() and 'reference' in case:
                truth = json.loads((suite_path.parent/case['reference']).read_text(encoding='utf-8'))
                # Automatically exclude scale-control edges declared in the capture.
                controls = ledger['configuration'].get('scale_references',[])
                truth['excluded_evaluation_edges'] = truth.get('excluded_evaluation_edges',[])+[e for c in controls for e in c.get('excluded_evaluation_edges',[])]
                metrics = evaluate_polygons(json.loads(plan_path.read_text(encoding='utf-8')),truth,case.get('alignment','rigid'))
                record['metrics'] = metrics
                record['targets_met'] = metrics['targets_met'] and record['status']=='proposal_requires_review'
            elif plan_path.exists() and 'icl_mesh' in case:
                from .evaluation import evaluate_icl
                record['metrics'] = evaluate_icl(plan_path,suite_path.parent/case['icl_mesh'],output/name/'metrics.json')
                record['dimension_target_met'] = record['metrics']['dimension_target_met_on_this_case']
                record['evaluation_limitation'] = 'Rectangle dimensions only; full topology/corner targets unevaluated'
            else:
                record['evaluation_limitation'] = 'No evaluable metric plan or reference'
            if 'reference' in case and ledger['tier'] in {'photos','video','lidar'}:
                from .assignment_gates import evaluate_assignment
                from .assessment_io import load_document
                truth=json.loads((suite_path.parent/case['reference']).read_text(encoding='utf-8'))
                assignment=evaluate_assignment(load_document(output/name),truth,ledger['tier'])
                record['assignment_metrics']=assignment
                (output/name/'assignment_metrics.json').write_text(json.dumps(assignment,indent=2),encoding='utf-8')
                record['calibrated_known_gates_pass']=assignment['calibrated_known_gates_pass']
                record['assignment_complete']=False
            if 'damage_annotations' in case:
                from .damage_evaluation import evaluate_damage
                from .assessment_io import load_document
                annotations=json.loads((suite_path.parent/case['damage_annotations']).read_text(encoding='utf-8'))
                record['damage_metrics']=evaluate_damage(load_document(output/name),annotations)
                (output/name/'damage_metrics.json').write_text(json.dumps(record['damage_metrics'],indent=2),encoding='utf-8')
        except Exception as exc:
            record.update(status='failed',reason=str(exc))
        cases.append(record)
        (output/'benchmark.json').write_text(json.dumps({'cases':cases},indent=2),encoding='utf-8')
    summary = {'cases':cases,'case_count':len(cases),'full_target_passes':sum(c['targets_met'] for c in cases),
               'real_phone_cm_accuracy_validated':False,'note':'Per-case results; correlated tiers are not independent properties.'}
    (output/'benchmark.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    lines = ['# Integrated benchmark','','| Case | Category | Status | Full targets | Seconds |','|---|---|---|---|---|']
    lines += [f"| {c['id']} | {c['category']} | {c['status']} | {c['targets_met']} | {c.get('runtime_s',0):.1f} |" for c in cases]
    lines += ['','See benchmark.json for errors, coverage, failures and evaluation limitations.','No field accuracy certification is implied.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return summary
