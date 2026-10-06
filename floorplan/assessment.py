"""Surface-keyed measurements and an offline review report for every run status."""
from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

from .contracts import validate_assessment
from .uncertainty import engineering_interval


def build_assessment(plan,ledger):
    plan=plan or {}
    document=dict(schema_version='internal-assessment-v1',published_schema_verified=False,
                  property_id=str(ledger['configuration'].get('property_id',ledger['manifest_sha256'][:16])),
                  capture_id=ledger['run_id'],tier=ledger['tier'],status=ledger['result']['status'],
                  rooms=[],surfaces=[],openings=[],measurements=[],damage_regions=[],concealed_flags=[],scope_items=[],
                  damage_assessment_status='not_evaluated',
                  missing_requirements=['published output schema','calibrated uncertainty','validated damage segmentation','consumer comparison'])
    def measure(entity,kind,value,unit,radius,reason=None):
        key=f'{entity}:{kind}'
        document['measurements'].append(dict(id=key,entity_id=entity,kind=kind,
                                             value=None if value is None else float(value),unit=unit,
                                             status='unavailable' if value is None else 'estimated',
                                             interval=engineering_interval(value,radius,unit),reason=reason))
        return key
    for room in plan.get('rooms',[]):
        rid=f"room:{room['id']}"; corners=np.asarray(room['corners'],float)
        boundary=room.get('boundary_evidence',{})
        # Envelopes expose measured dispersion. They do not assert field coverage.
        radius=max([.03]+[float(e.get('max_location_shift_m',0)) for e in boundary.get('edges',[])])
        area=float(Polygon(corners).area); perimeter=float(Polygon(corners).length)
        height=room.get('ceiling_height_m')
        document['rooms'].append(dict(id=rid,label=room.get('label',rid),corners=corners.tolist(),
                                      requires_boundary_review=room.get('requires_boundary_review',False),
                                      boundary_evidence=boundary))
        measure(rid,'ceiling_height',height,'m',2*radius,'ceiling not observed' if height is None else None)
        for kind in ('floor','ceiling'):
            sid=f'{rid}:{kind}'
            document['surfaces'].append(dict(id=sid,room_id=rid,kind=kind,corners=corners.tolist(),
                                             observed=bool(plan.get('provenance',{}).get('floor_observed',False)) if kind=='floor' else height is not None))
            measure(sid,'area',area if kind=='floor' or height is not None else None,'m2',
                    perimeter*radius+np.pi*radius**2,'surface not observed' if kind=='ceiling' and height is None else None)
        for index,(a,b) in enumerate(zip(corners,np.roll(corners,-1,axis=0))):
            sid=f'{rid}:wall:{index}'; length=float(np.linalg.norm(b-a))
            surface=dict(id=sid,room_id=rid,kind='wall',edge_index=index,
                         endpoints=[a.tolist(),b.tolist()],height_m=height)
            document['surfaces'].append(surface)
            measure(sid,'length',length,'m',2*radius)
            measure(sid,'height',height,'m',2*radius,'ceiling not observed' if height is None else None)
            measure(sid,'gross_area',None if height is None else length*height,'m2',
                    2*radius*(length+(height or 0))+4*radius**2)
            openings=[o for o in room.get('openings',[]) if o.get('edge_index')==index]
            deductions=[]
            for oi,opening in enumerate(openings):
                oid=f'{sid}:opening:{oi}'
                width=length*(opening['end_fraction']-opening['start_fraction'])
                opening_height=opening.get('height_m')
                document['openings'].append(dict(id=oid,surface_id=sid,kind=opening.get('kind','unknown'),
                                                 start_fraction=opening['start_fraction'],end_fraction=opening['end_fraction']))
                measure(oid,'width',width,'m',2*radius)
                measure(oid,'height',opening_height,'m',2*radius)
                deductions.append(None if opening_height is None else width*opening_height)
            net=None if height is None or any(x is None for x in deductions) else max(0.,length*height-sum(deductions))
            measure(sid,'net_area',net,'m2',2*radius*(length+(height or 0))+4*radius**2)
    if not document['rooms']: document['missing_requirements'].append('closed room geometry')
    if any(m['kind']=='ceiling_height' and m['value'] is None for m in document['measurements']):
        document['missing_requirements'].append('observed per-room ceiling heights')
    if plan.get('status')=='partial': document['missing_requirements'].append('complete property coverage')
    return validate_assessment(document)


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
    validate_assessment(document)
    (output/'assessment.json').write_text(json.dumps(document,indent=2),encoding='utf-8')
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
    scope=''.join(f"<li>{esc(s['surface_id'])}: {esc(s['action'])}, {s['quantity']:.3f} {esc(s['unit'])}; rule {esc(s['rule_id'])}</li>" for s in document['scope_items'])
    evidence=''.join(f'<a href="{esc(e["image"])}"><img src="{esc(e["image"])}" width="220" alt="{esc(e["id"])}"></a>' for e in document.get('damage_assessment',{}).get('evidence',[]))
    body=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Capture review</title>
<style>body{{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 24px;color:#162435}}h1{{margin-bottom:4px}}.status{{background:#fff3cd;padding:16px;border-radius:8px}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:10px;text-align:left}}object{{background:#f6f8fb}}code{{overflow-wrap:anywhere}}</style>
<h1>Capture review</h1><p>{esc(document['tier'])} · {esc(document['property_id'])}</p>
<p class="status">Status: <strong>{esc(document['status'])}</strong>. Accuracy is unvalidated; intervals are engineering envelopes until calibrated.</p>
{drawing}<h2>Measurements</h2><table><tr><th>Surface / room</th><th>Measurement</th><th>Estimate</th><th>Interval</th></tr>{''.join(rows)}</table>
<h2>Restoration evidence</h2><p>Assessment status: {esc(document['damage_assessment_status'])}. Regions: {len(document['damage_regions'])}. Scope items: {len(document['scope_items'])}. Candidate marks require review; concealed damage is not an observed fact.</p><ul>{scope}</ul>{evidence}
<h2>Remaining requirements</h2><ul>{missing}</ul><p><a href="assessment.json">Assessment JSON</a> · <a href="run.json">Run evidence</a></p></html>'''
    (output/'report.html').write_text(body,encoding='utf-8')
    return document
