"""Versioned evaluator for gates stated in the August 2026 assignment.

This does not replace the historical V3 benchmark. Earlier Round 1 gates and the
published output schema were not present in the supplied HTML; they remain pending.
"""
from __future__ import annotations

from copy import deepcopy

import numpy as np
from scipy.optimize import linear_sum_assignment
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .benchmark import evaluate_polygons


VERSION = 'assignment-aug2026-provisional-v1'
WALL_RELATIVE_TOLERANCE = {'photos': .08, 'video': .03}


def _edge_lengths(corners):
    points = np.asarray(corners, float)
    return np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)


def _matched_wall_errors(plan, truth, base):
    pred = {room['id']: room for room in plan.get('rooms', [])}
    refs = {room['id']: room for room in truth['rooms']}
    absolute, relative = [], []
    records = []
    for match in base['room_matches']:
        prediction, reference = pred[match['prediction']], refs[match['reference']]
        a, b = np.asarray(prediction['corners'], float), np.asarray(reference['corners'], float)
        if len(a) != len(b):
            continue
        rot = np.asarray(base['alignment']['rotation']); trans = np.asarray(base['alignment']['translation_m'])
        a = a @ rot + trans
        variants = [np.roll(order, offset, axis=0)
                    for order in (a, a[::-1]) for offset in range(len(a))]
        aligned = min(variants, key=lambda candidate: np.sum((candidate-b)**2))
        actual, expected = _edge_lengths(aligned), _edge_lengths(b)
        for edge, (observed, measured) in enumerate(zip(actual, expected)):
            if {'room_id': reference['id'], 'edge_index': edge} in truth.get('excluded_evaluation_edges', []):
                continue
            error = abs(float(observed-measured))
            absolute.append(error); relative.append(error / float(measured))
            records.append(dict(room_id=reference['id'], edge_index=edge, actual_m=float(observed),
                                reference_m=float(measured), absolute_error_m=error,
                                relative_error=error/float(measured)))
    return records, absolute, relative


def _opening_records(document, reference=False):
    if 'openings' in document:
        source = document['openings']
    else:
        source = document.get('connections', [])
    records = []
    for index, opening in enumerate(source):
        rooms = opening.get('rooms')
        if rooms is None:
            rooms = [opening.get('room_id')]
        records.append(dict(id=str(opening.get('id', f'opening_{index}')), rooms=tuple(sorted(str(r) for r in rooms)),
                            width_m=opening.get('width_m'), segment=opening.get('segment'), kind=opening.get('kind')))
    return records


def _opening_score(plan, truth, matched_ids, rotation, translation):
    actual = _opening_records(plan); expected = _opening_records(truth, True)
    for opening in actual:
        opening['rooms'] = tuple(sorted(matched_ids.get(room, f'unmatched:{room}') for room in opening['rooms']))
    cost = np.full((len(actual), len(expected)), 1e6)
    for i, a in enumerate(actual):
        for j, b in enumerate(expected):
            if a['rooms'] != b['rooms'] or (a['kind'] and b['kind'] and a['kind'] != b['kind']):
                continue
            if a['segment'] is not None and b['segment'] is not None:
                ac = np.asarray(a['segment'], float).mean(axis=0) @ rotation + translation
                bc = np.asarray(b['segment'], float).mean(axis=0)
                distance = float(np.linalg.norm(ac-bc))
                if distance > .30:
                    continue
            else:
                distance = 0.
            # Geometry or identity must identify an instance. Width is measured
            # after matching and cannot be used to cherry-pick a good opening.
            if a['segment'] is None or b['segment'] is None:
                if a['id'] != b['id'] and len([x for x in actual if x['rooms']==a['rooms']]) > 1:
                    continue
            cost[i,j] = distance
    if len(actual) and len(expected):
        row, col = linear_sum_assignment(cost)
        pairs = [(i,j) for i,j in zip(row,col) if cost[i,j] < 1e5]
    else:
        pairs = []
    matched_actual = {i for i,_ in pairs}; matched_expected = {j for _,j in pairs}
    measured = []
    for i,j in pairs:
        width_a, width_b = actual[i]['width_m'], expected[j]['width_m']
        error = abs(float(width_a)-float(width_b)) if width_a is not None and width_b is not None else None
        measured.append(dict(actual=actual[i]['id'], reference=expected[j]['id'], error_m=error,
                             within_2cm=error is not None and error <= .02))
    false_positives = len(actual)-len(matched_actual)
    false_negatives = len(expected)-len(matched_expected)
    # Provisional interpretation of "a missed or phantom opening counts as a miss".
    denominator = len(expected)+false_positives
    good = sum(m['within_2cm'] for m in measured)
    success = good/denominator if denominator else None
    return dict(reference_count=len(expected), predicted_count=len(actual), true_positives=len(pairs),
                false_positives=false_positives, false_negatives=false_negatives,
                matched=measured, score_denominator=denominator, within_2cm_count=good,
                success_fraction=success, matching_rule='room pair, kind and <=30 cm center distance when segments exist; provisional ID matching for duplicate segmentless openings',
                gate='pending_no_reference_openings' if not expected else 'pass' if success >= .85 else 'fail')


def _height_score(plan, truth, matched_ids):
    actual = {matched_ids.get(r['id']): r for r in plan.get('rooms', [])}
    errors = []
    missing = []
    for room in truth['rooms']:
        reference = room.get('ceiling_height_m')
        if reference is None:
            missing.append(dict(room_id=room['id'], reason='reference height missing'))
            continue
        prediction = actual.get(room['id'], {}).get('ceiling_height_m')
        if prediction is None:
            missing.append(dict(room_id=room['id'], reason='predicted height missing'))
            continue
        errors.append(dict(room_id=room['id'], error_m=abs(float(prediction)-float(reference))))
    gate = 'pass' if len(errors)==len(truth['rooms']) and all(x['error_m']<=.015 for x in errors) else 'fail'
    return dict(gate=gate, threshold_m=.015, errors=errors, missing=missing)


def _interval_score(plan):
    missing = []
    for room in plan.get('rooms', []):
        intervals = room.get('measurement_intervals', {})
        for name in ('floor_area_m2', 'ceiling_height_m'):
            value = intervals.get(name)
            if not isinstance(value, dict) or not all(k in value for k in ('lower','upper','confidence')):
                missing.append(f"{room['id']}:{name}")
        walls = intervals.get('walls_m', [])
        if len(walls) != len(room['corners']) or any(not isinstance(v, dict) or not all(k in v for k in ('lower','upper','confidence')) for v in walls):
            missing.append(f"{room['id']}:walls_m")
    for opening in _opening_records(plan):
        if 'openings' in plan:
            source = next((o for o in plan['openings'] if str(o.get('id'))==opening['id']), None)
        else:
            source = None
        if source is None or not isinstance(source.get('width_interval_m'),dict):
            missing.append(f"{opening['id']}:width_m")
    return dict(gate='pass' if not missing and plan.get('rooms') else 'fail', missing=missing,
                caveat='Presence gate only; empirical interval coverage requires independent held-out captures')


def _property_score(plan, truth, actual, expected):
    actual_polygons = [Polygon(r['corners']) for r in actual]
    expected_polygons = [Polygon(r['corners']) for r in expected]
    footprint = unary_union(actual_polygons).area if actual_polygons else 0.
    reference = unary_union(expected_polygons).area
    overlap = sum(actual_polygons[i].intersection(actual_polygons[j]).area
                  for i in range(len(actual_polygons)) for j in range(i))
    error = abs(footprint-reference)/reference if reference else None
    return dict(actual_area_m2=footprint, reference_area_m2=reference,
                relative_area_error=error, room_overlap_area_m2=overlap,
                gate='pass' if error is not None and error<=.08 and overlap<=1e-4 else 'fail')


def evaluate_assignment(plan, truth, tier):
    if tier not in {'photos','video','lidar'}:
        raise ValueError('tier must be photos, video or lidar')
    base = evaluate_polygons(plan, truth)
    matched_ids = {m['prediction']:m['reference'] for m in base['room_matches']}
    walls, absolute, relative = _matched_wall_errors(plan, truth, base)
    tolerance = WALL_RELATIVE_TOLERANCE.get(tier)
    wall_gate = ('pass' if tolerance is not None and len(walls)==sum(len(r['corners']) for r in truth['rooms'])
                 and all(x<=tolerance for x in relative) else 'fail' if tolerance is not None else 'pending_round1_definition')
    openings = _opening_score(plan, truth, matched_ids, np.asarray(base['alignment']['rotation']),
                              np.asarray(base['alignment']['translation_m']))
    predicted_rooms = [deepcopy(r) for r in plan.get('rooms', [])]
    rotation=np.asarray(base['alignment']['rotation']); translation=np.asarray(base['alignment']['translation_m'])
    for room in predicted_rooms:
        room['corners']=(np.asarray(room['corners'])@rotation+translation).tolist()
    result = dict(evaluator_version=VERSION, tier=tier, legacy_geometry=base,
                  walls=dict(gate=wall_gate, threshold_relative=tolerance, count=len(walls),
                             measurements=walls, max_relative_error=max(relative) if relative else None),
                  openings=openings, ceiling=_height_score(plan,truth,matched_ids),
                  intervals=_interval_score(plan),
                  property=_property_score(plan,truth,predicted_rooms,truth['rooms']),
                  topology=dict(gate='pass' if base['topology_correct'] else 'fail',
                                missing_rooms=base['missing_rooms'],extra_rooms=base['extra_rooms'],
                                missing_connections=base['missing_connections'],extra_connections=base['extra_connections']))
    result['known_gates_pass'] = all(result[k]['gate']=='pass' for k in ('walls','openings','ceiling','intervals','property','topology'))
    result['assignment_complete'] = False
    result['pending_specifications'] = ['published JSON schema','earlier Round 1 gates','LiDAR wall tolerance','interval coverage rule']
    result['not_evaluated_here'] = ['damage and scope','repeatability','drift ablation','consumer-app head-to-head']
    return result
