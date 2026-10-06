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
    if len(ids)!=len(set(ids)): raise ValueError('Deliverable IDs must be unique')
    room_ids={r['id'] for r in document['rooms']}
    surface_ids={s['id'] for s in document['surfaces']}
    entity_ids=room_ids|surface_ids|{o['id'] for o in document['openings']}|{r['id'] for r in document['damage_regions']}
    for surface in document['surfaces']:
        if surface['room_id'] not in room_ids: raise ValueError('Unknown surface room')
    for opening in document['openings']:
        if opening['surface_id'] not in surface_ids: raise ValueError('Unknown opening surface')
    for measurement in document['measurements']:
        if measurement['entity_id'] not in entity_ids: raise ValueError('Unknown measurement entity')
        value=measurement['value']; interval=measurement['interval']
        if value is not None and (not np.isfinite(value) or value<0): raise ValueError('Invalid measurement value')
        if interval is not None:
            lo,hi=interval['lower'],interval['upper']
            if value is None or not np.isfinite([lo,hi]).all() or not lo<=value<=hi:
                raise ValueError('Interval must be finite and contain its estimate')
    for item in document['scope_items']+document['damage_regions']+document['concealed_flags']:
        if item['surface_id'] not in surface_ids: raise ValueError('Unknown restoration surface')
    return document
