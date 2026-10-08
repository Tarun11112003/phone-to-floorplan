"""Read canonical assessments and historical plans without changing metric scale."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np


def load_document(path):
    path = Path(path)
    if path.is_dir():
        assessment = path / 'assessment.json'
        path = assessment if assessment.is_file() else path / 'plan.json'
    return json.loads(path.read_text(encoding='utf-8'))


def _segment(surface, opening):
    if opening.get('segment') is not None:
        return opening['segment']
    endpoints = surface.get('endpoints')
    if endpoints is None:
        return None
    a, b = np.asarray(endpoints, float)
    if 'start_fraction' not in opening or 'end_fraction' not in opening:
        return None
    return [
        (a + (b-a) * opening['start_fraction']).tolist(),
        (a + (b-a) * opening['end_fraction']).tolist(),
    ]


def physical_openings(plan):
    """Combine legacy opening locations; merge only exact shared observations.

    A doorway inferred from traversal can appear on both wall faces and in the
    connection list. Matching uses geometry, never its measured width. Distinct
    nearby openings and segmentless detections are not silently collapsed.
    """
    candidates = []
    room_ids = {str(room['id']) for room in plan.get('rooms', [])}
    for room in plan.get('rooms', []):
        corners = np.asarray(room['corners'], float)
        for index, opening in enumerate(room.get('openings', [])):
            item = deepcopy(opening)
            edge = item.get('edge_index')
            surface = {}
            if edge is not None and 0 <= edge < len(corners):
                surface = {'endpoints': [corners[edge].tolist(), corners[(edge+1) % len(corners)].tolist()]}
            item['segment'] = _segment(surface, item)
            item.setdefault('rooms', [str(room['id'])])
            item.setdefault('id', f"{room['id']}:opening:{index}")
            item['attachments'] = [{'room_id': str(room['id']), 'edge_index': edge}]
            if item.get('width_m') is None and item['segment'] is not None:
                item['width_m'] = float(np.linalg.norm(np.diff(item['segment'], axis=0)))
            candidates.append(item)
    for source in (plan.get('openings', []), [] if 'openings' in plan else plan.get('connections', [])):
        for index, opening in enumerate(source):
            item = deepcopy(opening)
            item.setdefault('rooms', [item.get('room_id')])
            if not any(str(room) in room_ids for room in item['rooms']):
                continue
            item.setdefault('id', f'opening:{len(candidates)}:{index}')
            item.setdefault('attachments', [])
            # Width-only adjacency is not automatically an extra detection if
            # exactly one observed doorway already identifies this room pair.
            matches = [c for c in candidates if set(map(str, c['rooms'])) == set(map(str, item['rooms']))]
            if item.get('segment') is None and len(matches) == 1 and len(item['rooms']) == 2:
                continue
            candidates.append(item)
    output = []
    for item in candidates:
        item['rooms'] = sorted({str(r) for r in item['rooms'] if r is not None})
        segment = item.get('segment')
        match = None
        for existing in output:
            if segment is None or existing.get('segment') is None:
                continue
            a, b = np.asarray(segment, float), np.asarray(existing['segment'], float)
            exact = np.allclose(a, b, atol=1e-6, rtol=0) or np.allclose(a, b[::-1], atol=1e-6, rtol=0)
            kinds={item.get('kind','unknown'), existing.get('kind','unknown')}
            compatible = len(kinds)==1 or 'unknown' in kinds or None in kinds
            if exact and compatible:
                match = existing
                break
        if match is None:
            output.append(item)
        else:
            match['rooms'] = sorted(set(match['rooms']) | set(item['rooms']))
            if match.get('kind','unknown')=='unknown' and item.get('kind'):
                match['kind']=item['kind']
            match['attachments'].extend(a for a in item['attachments'] if a not in match['attachments'])
            # Contradictory observed heights cannot be made consistent by choosing
            # the convenient one. They require review and stay unavailable.
            first, second = match.get('height_m'), item.get('height_m')
            if first is not None and second is not None and abs(first-second) > 1e-6:
                match['height_m'] = None
                match['height_conflict'] = True
            elif first is None and not match.get('height_conflict'):
                match['height_m'] = second
    return output


def to_evaluation_plan(document):
    """Project v1/v2 entity-linked measurements into the evaluator's geometry IR."""
    if document.get('schema_version') not in {'internal-assessment-v1', 'internal-assessment-v2'}:
        plan = deepcopy(document)
        plan['openings'] = physical_openings(plan)
        return plan
    from .contracts import validate_assessment
    validate_assessment(document)
    values = {(m['entity_id'], m['kind']): m for m in document['measurements']}
    surfaces = {s['id']: s for s in document['surfaces']}

    def measurement(entity, kind):
        return values.get((entity, kind), {'value': None, 'interval': None})

    rooms = []
    for room in document['rooms']:
        rid = room['id']
        height = measurement(rid, 'ceiling_height')
        floor = next((s for s in surfaces.values() if s['room_id'] == rid and s['kind'] == 'floor'), {})
        walls = sorted((s for s in surfaces.values() if s['room_id'] == rid and s['kind'] == 'wall'),
                       key=lambda s: s.get('edge_index', 0))
        rooms.append(dict(id=rid, corners=deepcopy(room['corners']),
                          metric_status=room.get('metric_status', 'unknown'),
                          ceiling_height_m=height['value'],
                          measurement_intervals=dict(
                              ceiling_height_m=height['interval'],
                              floor_area_m2=measurement(floor.get('id'), 'area')['interval'],
                              walls_m=[measurement(s['id'], 'length')['interval'] for s in walls])))
    openings = []
    for opening in document['openings']:
        surface = surfaces[opening['surface_id']]
        linked = opening.get('surface_ids', [surface['id']])
        width = measurement(opening['id'], 'width')
        height = measurement(opening['id'], 'height')
        openings.append(dict(id=opening['id'], kind=opening.get('kind', 'unknown'),
                             rooms=opening.get('rooms', sorted({surfaces[s]['room_id'] for s in linked})),
                             segment=_segment(surface, opening), width_m=width['value'],
                             height_m=height['value'], width_interval_m=width['interval']))
    plan = dict(rooms=rooms, openings=openings,
                connections=deepcopy(document.get('connections', [])),
                provenance=deepcopy(document.get('provenance', {})))
    # Historical v1 exported the two wall faces independently.
    if document['schema_version'] == 'internal-assessment-v1':
        plan['openings'] = physical_openings(plan)
    if not plan['connections']:
        plan['connections'] = [dict(rooms=o['rooms'], width_m=o['width_m'])
                               for o in plan['openings'] if len(o['rooms']) == 2]
    return plan
