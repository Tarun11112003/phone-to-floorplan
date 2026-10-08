"""Surface-keyed measurements and an offline review report for every run status."""
from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .contracts import validate_assessment
from .uncertainty import engineering_interval
from .assessment_io import physical_openings


def build_assessment(plan,ledger):
    plan=plan or {}
    document=dict(schema_version='internal-assessment-v2',published_schema_verified=False,
                  property_id=str(ledger['configuration'].get('property_id',ledger['manifest_sha256'][:16])),
                  capture_id=ledger['run_id'],tier=ledger['tier'],status=ledger['result']['status'],
                  rooms=[],surfaces=[],openings=[],connections=[],measurements=[],damage_regions=[],concealed_flags=[],scope_items=[],
                  provenance=plan.get('provenance',{}),
                  damage_assessment_status='not_evaluated',
                  missing_requirements=['published output schema','calibrated uncertainty','validated damage segmentation','consumer comparison'])
    def measure(entity,kind,value,unit,radius,reason=None):
        key=f'{entity}:{kind}'
        document['measurements'].append(dict(id=key,entity_id=entity,kind=kind,
                                             value=None if value is None else float(value),unit=unit,
                                             status='unavailable' if value is None else 'estimated',
                                             interval=engineering_interval(value,radius,unit),reason=reason if value is None else None))
        return key
    for room in plan.get('rooms',[]):
        rid=f"room:{room['id']}"; corners=np.asarray(room['corners'],float)
        boundary=room.get('boundary_evidence',{})
        # Envelopes expose measured dispersion. They do not assert field coverage.
        radius=max([.03]+[float(e.get('max_location_shift_m',0)) for e in boundary.get('edges',[])])
        area=float(Polygon(corners).area); perimeter=float(Polygon(corners).length)
        height=room.get('ceiling_height_m')
        document['rooms'].append(dict(id=rid,label=room.get('label',rid),corners=corners.tolist(),
                                      source_room_id=str(room['id']),metric_status=room.get('metric_status','unknown'),
                                      requires_boundary_review=room.get('requires_boundary_review',False),
                                      boundary_evidence=boundary,
                                      floor_level_m=room.get('floor_level_m'),floor_evidence=room.get('floor_evidence'),
                                      ceiling_evidence=room.get('ceiling_evidence')))
        height_reason=(room.get('ceiling_evidence') or {}).get('height_definition','ceiling or per-room floor not observed')
        measure(rid,'ceiling_height',height,'m',2*radius,height_reason if height is None else None)
        for kind in ('floor','ceiling'):
            sid=f'{rid}:{kind}'
            document['surfaces'].append(dict(id=sid,room_id=rid,kind=kind,corners=corners.tolist(),
                                             observed=bool(room.get('floor_observed',plan.get('provenance',{}).get('floor_observed',False))) if kind=='floor' else height is not None))
            measure(sid,'area',area if kind=='floor' or height is not None else None,'m2',
                    perimeter*radius+np.pi*radius**2,'surface not observed' if kind=='ceiling' and height is None else None)
        for index,(a,b) in enumerate(zip(corners,np.roll(corners,-1,axis=0))):
            sid=f'{rid}:wall:{index}'; length=float(np.linalg.norm(b-a))
            surface=dict(id=sid,room_id=rid,kind='wall',edge_index=index,
                         endpoints=[a.tolist(),b.tolist()],height_m=height,
                         floor_level_m=room.get('floor_level_m',plan.get('provenance',{}).get('floor_level_m')))
            document['surfaces'].append(surface)
            measure(sid,'length',length,'m',2*radius)
            measure(sid,'height',height,'m',2*radius,'ceiling not observed' if height is None else None)
            measure(sid,'gross_area',None if height is None else length*height,'m2',
                    2*radius*(length+(height or 0))+4*radius**2)
            openings=[o for o in room.get('openings',[]) if o.get('edge_index')==index]
            deductions=[]
            for opening in openings:
                width=opening.get('width_m')
                if width is None: width=length*(opening['end_fraction']-opening['start_fraction'])
                opening_height=opening.get('height_m')
                deductions.append(None if opening_height is None else width*opening_height)
            net=None if height is None or any(x is None for x in deductions) else max(0.,length*height-sum(deductions))
            measure(sid,'net_area',net,'m2',2*radius*(length+(height or 0))+4*radius**2)
    room_lookup={str(r['source_room_id']):r['id'] for r in document['rooms']}
    wall_surfaces=[s for s in document['surfaces'] if s['kind']=='wall']
    for index,opening in enumerate(physical_openings(plan)):
        linked=[]
        for attachment in opening.get('attachments',[]):
            rid=room_lookup.get(attachment['room_id'])
            linked.extend(s['id'] for s in wall_surfaces if s['room_id']==rid and s['edge_index']==attachment['edge_index'])
        segment=opening.get('segment')
        # Top-level instances need an observed wall association, not a guessed
        # first wall. Collinearity and segment bounds establish the attachment.
        if segment is not None:
            a,b=np.asarray(segment,float)
            for surface in wall_surfaces:
                if surface['room_id'] not in [room_lookup.get(str(r)) for r in opening['rooms']]: continue
                start,end=np.asarray(surface['endpoints'],float)
                direction=end-start; length=np.linalg.norm(direction); direction/=length
                offsets=np.array([a-start,b-start])
                u=offsets@direction
                if np.max(np.abs(offsets@np.array([-direction[1],direction[0]])))<=1e-5 and u.min()>=-1e-5 and u.max()<=length+1e-5:
                    linked.append(surface['id'])
        linked=sorted(set(linked))
        if not linked:
            document['missing_requirements'].append(f"opening {opening['id']} has no observed wall attachment")
            continue
        oid=f'opening:{index}'
        document['openings'].append(dict(id=oid,surface_id=linked[0],surface_ids=linked,
                                         rooms=sorted({room_lookup[str(r)] for r in opening['rooms'] if str(r) in room_lookup}),
                                         segment=segment,kind=opening.get('kind','unknown')))
        measure(oid,'width',opening.get('width_m'),'m',.06,'opening width not observed')
        measure(oid,'height',opening.get('height_m'),'m',.06,'opening height not observed')
    document['connections']=[dict(rooms=[room_lookup[str(r)] for r in c['rooms']],
                                  **{k:v for k,v in c.items() if k!='rooms'})
                             for c in plan.get('connections',[]) if all(str(r) in room_lookup for r in c['rooms'])]
    if not document['connections']:
        document['connections']=[dict(rooms=o['rooms'],opening_id=o['id']) for o in document['openings'] if len(o['rooms'])==2]
    measurement_lookup={(m['entity_id'],m['kind']):m for m in document['measurements']}
    for surface in wall_surfaces:
        gross=measurement_lookup[(surface['id'],'gross_area')]['value']
        attached=[o for o in document['openings'] if surface['id'] in o['surface_ids']]
        dimensions=[(measurement_lookup[(o['id'],'width')]['value'],measurement_lookup[(o['id'],'height')]['value']) for o in attached]
        net=measurement_lookup[(surface['id'],'net_area')]
        if gross is None or any(w is None or h is None for w,h in dimensions):
            net.update(value=None,status='unavailable',interval=None,reason='wall or opening height not observed')
        else:
            net['value']=max(0.,gross-sum(w*h for w,h in dimensions))
            net['interval']=engineering_interval(net['value'],.06*(surface['height_m']+np.linalg.norm(np.diff(surface['endpoints'],axis=0))), 'm2')
    document['property_entity_id']=f"property:{document['property_id']}"
    polygons=[Polygon(r['corners']) for r in document['rooms']]
    footprint=unary_union(polygons) if polygons else None
    measure(document['property_entity_id'],'footprint_area',None if footprint is None else footprint.area,'m2',
            .03*footprint.length if footprint is not None else 0,'no closed rooms' if footprint is None else None)
    document['room_overlap_area_m2']=sum(polygons[i].intersection(polygons[j]).area for i in range(len(polygons)) for j in range(i))
    if not document['rooms']: document['missing_requirements'].append('closed room geometry')
    if any(m['kind']=='ceiling_height' and m['value'] is None for m in document['measurements']):
        document['missing_requirements'].append('observed per-room ceiling heights')
    if plan.get('status')=='partial': document['missing_requirements'].append('complete property coverage')
    return validate_assessment(document)


def _contract_coverage(document,plan,output,ledger):
    """Inventory required per-capture outputs without turning presence into a pass."""
    plan=plan or {}; rooms=plan.get('rooms',[])
    measurements=document.get('measurements',[])
    heights=[r.get('ceiling_height_m') for r in rooms]
    openings=plan.get('openings')
    if openings is None:
        openings=[opening for room in rooms for opening in room.get('openings',[])]
    connections=plan.get('connections',[])

    def item(key,label,status,evidence,limitation):
        return dict(key=key,label=label,status=status,evidence=evidence,limitation=limitation)

    geometry='present_unvalidated' if rooms else 'not_produced'
    if heights and all(value is not None for value in heights):
        ceiling='present_unvalidated'; ceiling_evidence=f'{len(heights)} room height estimate(s)'
    elif any(value is not None for value in heights):
        ceiling='partial'; ceiling_evidence=f'{sum(value is not None for value in heights)} of {len(heights)} room heights'
    else:
        ceiling='not_produced'; ceiling_evidence='No observed per-room ceiling estimates'
    stitch=('present_unvalidated' if len(rooms)>1 and connections else
            'partial' if len(rooms)>1 else 'not_evaluated')
    stitch_evidence=f'{len(rooms)} room(s), {len(connections)} connection(s)'
    intervals_present=bool(measurements) and all(m.get('interval') is not None for m in measurements)
    calibrated=intervals_present and all(m['interval'].get('calibrated') is True for m in measurements)
    interval_status='calibrated' if calibrated else 'uncalibrated' if intervals_present else 'incomplete'
    damage_status=document.get('damage_assessment_status','not_evaluated')
    damage_state=('present_unvalidated' if document.get('damage_regions') else
                  'partial' if damage_status=='experimental_candidates_require_review' else 'not_evaluated')
    rendered=(output/'plan.svg').is_file()
    rows=[
        item('dimensioned_room_plans','Dimensioned per-room wall plan',geometry,
             f'{len(rooms)} room polygon(s)' if rooms else 'No plan.json with room polygons',
             'Presence is not a surveyed accuracy result.'),
        item('ceiling_heights','Ceiling height for each room',ceiling,ceiling_evidence,
             'Missing observations stay null; no fixed height is substituted.'),
        item('floor_area','Floor area per room','present_unvalidated' if rooms else 'not_produced',
             f'{len(rooms)} room polygon(s)' if rooms else 'No room geometry',
             'Area is derived from the proposed polygon and needs truth comparison.'),
        item('openings','Opening instances and dimensions',
             'present_unvalidated' if openings else 'not_evaluated',
             f'{len(openings)} opening candidate(s)',
             'An empty list does not prove that no opening was missed.'),
        item('whole_property_stitch','Stitched rooms, adjacency and non-overlap',stitch,
             stitch_evidence,'Presence does not establish correct adjacency or footprint tolerance.'),
        item('surface_damage','Per-surface damage class and metric extent',damage_state,
             f"{len(document.get('damage_regions',[]))} region(s); detector status {damage_status}",
             'Candidate masks require validated class/extent scoring.'),
        item('concealed_damage','Concealed-damage flags with fired rule',
             'present_unvalidated' if document.get('concealed_flags') else 'not_evaluated',
             f"{len(document.get('concealed_flags',[]))} flag(s)",
             'A rule flag is a request to inspect, not observed concealed damage.'),
        item('scope_items','Surface-keyed restoration scope line items',
             'present_unvalidated' if document.get('scope_items') else 'not_evaluated',
             f"{len(document.get('scope_items',[]))} item(s)",
             'Quantities/actions have not passed a restoration benchmark.'),
        item('measurement_intervals','Confidence interval on every measurement',interval_status,
             f'{sum(m.get("interval") is not None for m in measurements)} of {len(measurements)} intervals present',
             'Engineering envelopes are not calibrated statistical intervals.'),
        item('published_json_schema','JSON conforming to published schema','pending_external_spec',
             document.get('schema_version','No internal assessment'),
             'The supplied brief references a published schema but does not include it.'),
        item('rendered_plan','Rendered whole-property plan',
             'present_unvalidated' if rendered else 'not_produced',
             'plan.svg exists' if rendered else 'No plan.svg was produced',
             'A diagnostic drawing is not a complete accepted plan.'),
        item('one_command_run','One-command capture and audit trail',
             'recorded' if ledger.get('run_id') else 'not_recorded',
             f"run_id={ledger.get('run_id','unavailable')}; status={ledger.get('result',{}).get('status','unknown')}",
             'A completed command does not mean the geometry or assignment gates passed.'),
    ]
    return dict(version='assignment-output-coverage-v1',tier=ledger.get('tier'),
                accuracy_validated=False,items=rows,
                summary=dict(item_count=len(rows),not_produced=sum(r['status']=='not_produced' for r in rows),
                             incomplete=sum(r['status'] in {'partial','incomplete','uncalibrated','not_evaluated','pending_external_spec'} for r in rows),
                             present_but_unvalidated=sum(r['status']=='present_unvalidated' for r in rows)))


def contract_blockers(document,ledger):
    """Internal completeness checks, separate from external accuracy acceptance."""
    blockers=[]
    rooms={r['id'] for r in document['rooms']}
    if not rooms: blockers.append('no closed rooms')
    if not ledger.get('result',{}).get('floor_plan_ready') or document['status']=='partial':
        blockers.append('complete geometry not ready')
    if any(r.get('requires_boundary_review') or r.get('metric_status') in {'unknown','unscaled'} for r in document['rooms']):
        blockers.append('unresolved room boundary or metric scale')
    if document.get('room_overlap_area_m2',0)>1e-4:
        blockers.append('overlapping room interiors')
    reached=set()
    if rooms:
        reached.add(next(iter(rooms)))
        while True:
            previous=len(reached)
            for edge in document['connections']:
                if reached.intersection(edge['rooms']): reached.update(edge['rooms'])
            if len(reached)==previous: break
    if reached!=rooms: blockers.append('disconnected property adjacency')
    if any(s['kind']=='floor' and not s.get('observed') for s in document['surfaces']):
        blockers.append('floor plane not observed')
    if any('no observed wall attachment' in item for item in document.get('missing_requirements',[])):
        blockers.append('unattached opening observation')
    if any(m['value'] is None or not m.get('interval') or not m['interval'].get('calibrated',False)
           for m in document['measurements']):
        blockers.append('unavailable measurement or calibrated interval')
    if document['damage_assessment_status']!='evaluated':
        blockers.append('damage assessment not validated/evaluated')
    return blockers


def write_assessment(output,ledger,assessment=None):
    output=Path(output)
    plan_path=output/'plan.json'
    plan=json.loads(plan_path.read_text()) if plan_path.exists() else None
    document=assessment if assessment is not None else build_assessment(plan,ledger)
    if assessment is None and plan is not None:
        from .damage import assess_rgbd_damage
        try:
            damage=assess_rgbd_damage(plan,output,document)
        except Exception as exc:
            damage=dict(status='failed',reason=str(exc),evidence=[])
        document['damage_assessment']=damage
        document['damage_assessment_status']=damage['status']
    from .uncertainty import apply_calibration
    calibration=ledger.get('configuration',{}).get('calibration')
    if calibration:
        calibration_path=Path(calibration)
        if not calibration_path.is_absolute():
            calibration_path=Path(ledger['manifest']).parent/calibration_path
        apply_calibration(document,json.loads(calibration_path.read_text(encoding='utf-8')),
                          ledger.get('measurement_producer_fingerprint'))
    document['contract_blockers']=contract_blockers(document,ledger)
    document['contract_complete']=not document['contract_blockers']
    ledger['contract_complete']=document['contract_complete']
    validate_assessment(document)
    (output/'assessment.json').write_text(json.dumps(document,indent=2),encoding='utf-8')
    coverage=_contract_coverage(document,plan,output,ledger)
    (output/'contract_coverage.json').write_text(json.dumps(coverage,indent=2),encoding='utf-8')
    esc=lambda value:html.escape(str(value),quote=True)
    rows=[]
    for m in document['measurements']:
        bounds=m['interval']
        value='unavailable' if m['value'] is None else f"{m['value']:.3f} {m['unit']}"
        interval='—' if bounds is None else f"[{bounds['lower']:.3f}, {bounds['upper']:.3f}] ({'calibrated' if bounds.get('calibrated') else 'uncalibrated'})"
        rows.append(f"<tr><td>{esc(m['entity_id'])}</td><td>{esc(m['kind'])}</td><td>{esc(value)}</td><td>{esc(interval)}</td></tr>")
    visual='plan.svg' if (output/'plan.svg').exists() else 'layout_diagnostic.svg'
    drawing=f'<object data="{visual}" type="image/svg+xml" width="100%" height="560"></object>' if (output/visual).exists() else '<p>No supported plan geometry was produced.</p>'
    missing=''.join(f'<li>{esc(item)}</li>' for item in document['missing_requirements'])
    coverage_rows=''.join(f"<tr><td>{esc(row['label'])}</td><td><strong>{esc(row['status'])}</strong></td><td>{esc(row['evidence'])}</td><td>{esc(row['limitation'])}</td></tr>" for row in coverage['items'])
    scope=''.join(f"<li>{esc(s['surface_id'])}: {esc(s['action'])}, {s['quantity']:.3f} {esc(s['unit'])}; rule {esc(s['rule_id'])}</li>" for s in document['scope_items'])
    evidence=''.join(f'<a href="{esc(e["image"])}"><img src="{esc(e["image"])}" width="220" alt="{esc(e["id"])}"></a>' for e in document.get('damage_assessment',{}).get('evidence',[]))
    result=ledger.get('result',{})
    sparse=result.get('sparse_reconstruction',result)
    diagnostics=sparse.get('matching_diagnostics') if isinstance(sparse,dict) else None
    matching_section=''
    if diagnostics:
        pairs=''.join(
            f"<tr><td>{esc(pair['image_a'])}</td><td>{esc(pair['image_b'])}</td><td>{pair['verified_inliers']}</td></tr>"
            for pair in diagnostics.get('strongest_verified_pairs',[])
        )
        unmatched=''.join(f'<li>{esc(name)}</li>' for name in diagnostics.get('images_without_verified_pairs',[]))
        guidance=esc(sparse.get('reconstruction_guidance',''))
        matching_section=f'''<h2>Photo-matching diagnostics</h2><p>{guidance}</p>
<p>Geometrically verified pairs: {diagnostics['geometrically_verified_pair_count']} of {diagnostics['candidate_image_pairs']};
maximum verified inliers: {diagnostics['max_verified_inliers']}; median: {diagnostics['median_verified_inliers']:.1f}.
These diagnose SfM support and do not measure room accuracy.</p>
<table><tr><th>Image A</th><th>Image B</th><th>Verified inliers</th></tr>{pairs}</table>
<p>Images without a verified pair:</p><ul>{unmatched or '<li>None</li>'}</ul>'''
    body=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Capture review</title>
<style>body{{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 24px;color:#162435}}h1{{margin-bottom:4px}}.status{{background:#fff3cd;padding:16px;border-radius:8px}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:10px;text-align:left}}object{{background:#f6f8fb}}code{{overflow-wrap:anywhere}}</style>
<h1>Capture review</h1><p>{esc(document['tier'])} · {esc(document['property_id'])}</p>
<p class="status">Status: <strong>{esc(document['status'])}</strong>. Accuracy is unvalidated. Interval status: {esc('calibrated' if document['measurements'] and all(m.get('interval') and m['interval'].get('calibrated') for m in document['measurements']) else 'incomplete or uncalibrated')}.</p>
{drawing}{matching_section}<h2>Measurements</h2><table><tr><th>Surface / room</th><th>Measurement</th><th>Estimate</th><th>Interval</th></tr>{''.join(rows)}</table>
<h2>Assignment output coverage</h2><p>This is an output-presence checklist, not an accuracy pass. Status summary: {coverage['summary']['not_produced']} not produced, {coverage['summary']['incomplete']} incomplete/pending, {coverage['summary']['present_but_unvalidated']} present but unvalidated.</p><table><tr><th>Required output</th><th>Status</th><th>Evidence</th><th>Limit</th></tr>{coverage_rows}</table><p><a href="contract_coverage.json">Machine-readable coverage</a></p>
<h2>Restoration evidence</h2><p>Assessment status: {esc(document['damage_assessment_status'])}. Regions: {len(document['damage_regions'])}. Scope items: {len(document['scope_items'])}. Candidate marks require review; concealed damage is not an observed fact.</p><ul>{scope}</ul>{evidence}
<h2>Remaining requirements</h2><ul>{missing}</ul><p><a href="assessment.json">Assessment JSON</a> · <a href="run.json">Run evidence</a></p></html>'''
    (output/'report.html').write_text(body,encoding='utf-8')
    return document
