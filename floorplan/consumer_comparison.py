"""Auditable shared-dimension comparison; no geometry changes enter inference."""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .acceptance import PROVISIONAL_INTERPRETATIONS
from .contracts import validate_assessment
from .provenance import sha256


def read_dimensions(path):
    """Transcribe an original consumer export into room/id/value_m CSV rows."""
    with Path(path).open(newline='',encoding='utf-8-sig') as stream:
        rows=list(csv.DictReader(stream))
    dimensions={}
    for row in rows:
        key=(row['room_id'],row['dimension_id'])
        if key in dimensions: raise ValueError('Duplicate consumer dimension identity')
        value=float(row['value_m'])
        if not np.isfinite(value) or value<=0: raise ValueError('Invalid consumer dimension')
        dimensions[key]=value
    return dimensions


def compare_consumer(assessment,consumer_dimensions,specification,export_path):
    validate_assessment(assessment)
    if assessment['tier']!='lidar': raise ValueError('Consumer comparison requires our LiDAR tier')
    if specification['property_id']!=assessment['property_id']: raise ValueError('Consumer property differs from our capture')
    for field in ('app_name','app_version','device_model'):
        if not specification.get(field): raise ValueError(f'Consumer comparison needs {field}')
    export_path=Path(export_path)
    export_hash=sha256(export_path)
    if specification.get('export_sha256')!=export_hash: raise ValueError('Original consumer export checksum mismatch')
    rooms=set(specification['room_ids'])
    if len(rooms)!=2: raise ValueError('Consumer comparison requires exactly two identified benchmark rooms')
    measurements={m['id']:m for m in assessment['measurements']}
    rows=[]; seen=set()
    for dimension in specification['dimensions']:
        key=(dimension['room_id'],dimension['dimension_id'])
        if key in seen: raise ValueError('Duplicate comparison dimension')
        seen.add(key)
        if key[0] not in rooms: raise ValueError('Dimension is outside the selected benchmark rooms')
        truth=float(dimension['reference_m'])
        if not np.isfinite(truth) or truth<=0: raise ValueError('Invalid independent reference dimension')
        our_measurement=measurements.get(dimension['measurement_id'])
        if our_measurement and our_measurement['unit']!='m': raise ValueError('Linear dimensions must use metres')
        actual=our_measurement['value'] if our_measurement else None
        consumer=consumer_dimensions.get(key)
        own_error=abs(actual-truth) if actual is not None else None
        app_error=abs(consumer-truth) if consumer is not None else None
        shared=actual is not None and consumer is not None
        rows.append(dict(room_id=key[0],dimension_id=key[1],measurement_id=dimension['measurement_id'],
                         reference_m=truth,ours_m=actual,consumer_m=consumer,ours_error_m=own_error,
                         consumer_error_m=app_error,shared=shared,
                         beat_or_tie=shared and own_error<=app_error+PROVISIONAL_INTERPRETATIONS['consumer_tie_epsilon_m']))
    shared=[r for r in rows if r['shared']]
    excluded=specification.get('excluded_dimensions',[])
    excluded_keys={(r['room_id'],r['dimension_id']) for r in excluded if r.get('reason')}
    unmapped=sorted(key for key in consumer_dimensions if key[0] in rooms and key not in seen and key not in excluded_keys)
    represented={r['room_id'] for r in shared}
    score=sum(r['beat_or_tie'] for r in shared)/len(shared) if shared else None
    return dict(version='lidar-consumer-comparison-v1',app=specification['app_name'],app_version=specification['app_version'],
                original_export_sha256=export_hash,property_id=assessment['property_id'],
                room_ids=sorted(rooms),dimensions=rows,shared_count=len(shared),
                missing_our_count=sum(r['ours_m'] is None for r in rows),
                missing_consumer_count=sum(r['consumer_m'] is None for r in rows),
                unmapped_consumer_dimensions=unmapped,excluded_dimensions=excluded,
                fraction_beat_or_tie=score,gate='pass' if not unmapped and represented==rooms and score is not None and score>=.70 else 'fail',
                mapping_status='declared survey-to-export correspondence; review all eligible dimensions',
                accuracy_validated=False)
