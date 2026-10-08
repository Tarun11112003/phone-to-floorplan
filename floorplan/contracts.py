"""Internal deliverable contract. The assignment's published schema is still absent."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def validate_assessment(document):
    from jsonschema import Draft202012Validator
    schema=json.loads((Path(__file__).parent/'schemas'/'assessment.schema.json').read_text())
    Draft202012Validator(schema).validate(document)
    ids=[item['id'] for key in ('rooms','surfaces','measurements','openings','damage_regions','concealed_flags','scope_items') for item in document[key]]
    if document.get('property_entity_id'): ids.append(document['property_entity_id'])
    if len(ids)!=len(set(ids)): raise ValueError('Deliverable IDs must be unique')
    room_ids={r['id'] for r in document['rooms']}
    surface_ids={s['id'] for s in document['surfaces']}
    entity_ids=room_ids|surface_ids|{o['id'] for o in document['openings']}|{r['id'] for r in document['damage_regions']}
    if document.get('property_entity_id'): entity_ids.add(document['property_entity_id'])
    region_ids={r['id']:r for r in document['damage_regions']}
    for room in document['rooms']:
        from shapely.geometry import Polygon
        corners=np.asarray(room['corners'],float)
        if corners.ndim!=2 or corners.shape[1]!=2 or not np.isfinite(corners).all():
            raise ValueError('Room corners must be finite Nx2 coordinates')
        polygon=Polygon(corners)
        if not polygon.is_valid or polygon.area<=0: raise ValueError('Invalid room polygon')
    for surface in document['surfaces']:
        if surface['room_id'] not in room_ids: raise ValueError('Unknown surface room')
    for opening in document['openings']:
        if opening['surface_id'] not in surface_ids: raise ValueError('Unknown opening surface')
        linked=opening.get('surface_ids',[opening['surface_id']])
        if not linked or opening['surface_id'] not in linked or not set(linked)<=surface_ids:
            raise ValueError('Unknown opening surface attachment')
        if not set(opening.get('rooms',[]))<=room_ids: raise ValueError('Unknown opening room')
    for connection in document.get('connections',[]):
        if not set(connection['rooms'])<=room_ids: raise ValueError('Unknown connection room')
    for measurement in document['measurements']:
        if measurement['entity_id'] not in entity_ids: raise ValueError('Unknown measurement entity')
        value=measurement['value']; interval=measurement['interval']
        if value is not None and (not np.isfinite(value) or value<0): raise ValueError('Invalid measurement value')
        if interval is not None:
            lo,hi=interval['lower'],interval['upper']
            if value is None or not np.isfinite([lo,hi]).all() or not lo<=value<=hi:
                raise ValueError('Interval must be finite and contain its estimate')
            confidence=interval.get('confidence')
            if confidence is None or not 0<confidence<1 or interval.get('unit')!=measurement['unit']:
                raise ValueError('Interval confidence and unit must be valid')
    for item in document['scope_items']+document['damage_regions']+document['concealed_flags']:
        if item['surface_id'] not in surface_ids: raise ValueError('Unknown restoration surface')
    from .damage import INSPECTION_RULES
    for item in document['scope_items']+document['concealed_flags']:
        region=region_ids.get(item.get('source_region_id'))
        if region is None or region['surface_id']!=item['surface_id']:
            raise ValueError('Unknown or mismatched scope source region')
        if item.get('rule_id') not in INSPECTION_RULES: raise ValueError('Unknown inspection rule')
    for item in document['scope_items']:
        quantity=item.get('quantity')
        if quantity is None or not np.isfinite(quantity) or quantity<0: raise ValueError('Invalid scope quantity')
    return document
