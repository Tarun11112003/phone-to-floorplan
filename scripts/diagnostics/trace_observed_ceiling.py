"""Read-only native floor/ceiling decision trace on retained room geometry.

Calls the unmodified production functions with their saved inputs. It does not
generate planes, move cameras, change guard values, borrow a neighbouring floor,
or run a hypothetical ceiling inference using the global projection datum.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
from pathlib import Path
import sys
import textwrap

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from shapely.geometry import Polygon

from floorplan import layout
from floorplan.provenance import sha256


def guard_sites(function):
    """Map native continue-to-loop line transitions, including inline guards."""
    lines, start = inspect.getsourcelines(function)
    source = textwrap.dedent(''.join(lines))
    result = {}
    for loop in ast.walk(ast.parse(source)):
        if not isinstance(loop, ast.For):
            continue
        for node in ast.walk(loop):
            if isinstance(node, ast.If):
                for child in node.body:
                    if isinstance(child, ast.Continue):
                        transition = (child.lineno + start - 1, loop.lineno + start - 1)
                        result[transition] = ast.get_source_segment(source, node.test)
    return result


def native_trace(function, poly, points, planes, basis, camera_path, *, floor=None, reference_floor=None):
    """Capture actual line/return events; never replace a production function."""
    if function not in (layout._observed_floor, layout._observed_ceiling):
        raise ValueError('Only the native observed surface functions are supported')
    if sys.gettrace() is not None:
        raise ValueError('Do not replace an existing debugger/trace hook')
    functions = (function, layout._horizontal_support)
    codes = {f.__code__: f for f in functions}
    source = {f.__code__: dict(zip(range(start, start + len(lines)), [line.strip() for line in lines]))
              for f in functions for lines, start in [inspect.getsourcelines(f)]}
    guards = guard_sites(function)
    identities = {id(plane): i for i, plane in enumerate(planes)}
    rows = []
    previous_line = {}

    def trace(frame, event, arg):
        if frame.f_code not in codes:
            return None
        if event in ('line', 'return'):
            values = frame.f_locals
            caller = frame.f_back.f_locals if frame.f_code == layout._horizontal_support.__code__ else values
            plane = caller.get('plane')
            row = dict(function=frame.f_code.co_name, event=event, line=frame.f_lineno,
                       source=source[frame.f_code].get(frame.f_lineno),
                       plane_index=identities.get(id(plane)))
            if plane is not None:
                row['plane_rms_m'] = plane.get('rms_m', 1)
            for key in ('camera_y', 'level', 'height', 'reference_floor', 'floor', 'count',
                        'coverage', 'minimum', 'maximum', 'sloped', 'area'):
                if key in values:
                    v = values[key]
                    row[key] = v.item() if isinstance(v, np.generic) else v
            for key in ('cameras', 'inside_cameras', 'support', 'cells', 'candidates'):
                if key in values:
                    row[f'{key}_count'] = len(values[key])
            if 'normal' in values:
                row['aligned_normal'] = np.asarray(values['normal']).tolist()
            transition = (previous_line.get(id(frame)), frame.f_lineno)
            if event == 'line' and frame.f_code == function.__code__ and transition in guards:
                row['rejected_by_native_condition'] = guards[transition]
                row['executed_continue_line_transition'] = list(transition)
            if event == 'return':
                row['native_return'] = arg
            rows.append(row)
            if event == 'line':
                previous_line[id(frame)] = frame.f_lineno
            else:
                previous_line.pop(id(frame), None)
        return trace

    sys.settrace(trace)
    try:
        if function is layout._observed_floor:
            value = function(poly, points, planes, basis, camera_path, reference_floor)
        else:
            value = function(poly, points, planes, basis, floor, camera_path)
    finally:
        sys.settrace(None)
    # Native values contain plain Python numbers/dicts and support counts.
    return dict(value=json.loads(json.dumps(value)), events=json.loads(json.dumps(rows)))


def fingerprint(poly, points, planes, basis, camera_path):
    payload = (poly.wkb + np.asarray(points).tobytes() + np.asarray(basis).tobytes()
               + json.dumps(planes, sort_keys=True).encode()
               + json.dumps(camera_path).encode())
    return hashlib.sha256(payload).hexdigest()


def plane_decisions(trace, planes):
    """Summarize native branch events; unreached conditions remain unreached."""
    decisions = []
    for index, plane in enumerate(planes):
        events = [row for row in trace['events'] if row['plane_index'] == index]
        rejected = next((row for row in events if 'rejected_by_native_condition' in row), None)
        support = [row for row in events if row['function'] == '_horizontal_support']
        returned = next((row for row in reversed(support) if row['event'] == 'return'), None)
        row = dict(plane_index=index, input_plane=plane,
                   visited=bool(events), native_rejection=rejected,
                   native_horizontal_support_return=returned.get('native_return') if returned else None)
        if returned:
            row['plane_band_points'] = max(event.get('support_count', 0) for event in support)
            row['finite_room_support_points'] = returned.get('support_count')
            row['occupied_cells'] = returned.get('cells_count', 0)
        decisions.append(row)
    return decisions


def horizontal_inventory(poly, points, decisions):
    """Measure existing horizontal returns without inferring a ceiling height.

    This supplementary helper is not a reached observed_ceiling decision. Its
    plane identities and camera-relative levels come from the native floor trace.
    """
    rows = []
    for decision in decisions:
        rejected = decision['native_rejection']
        if rejected is None or rejected['rejected_by_native_condition'] != 'level<=camera_y+.3':
            continue
        plane = decision['input_plane']
        normal = np.asarray(rejected['aligned_normal'])
        count, coverage = layout._horizontal_support(poly, points, normal, plane['offset'])
        rows.append(dict(plane_index=decision['plane_index'],
            aligned_plane_normal=normal.tolist(), plane_level_at_centroid=rejected['level'],
            camera_median_y=rejected['camera_y'],
            plane_above_camera=rejected['level'] < rejected['camera_y'],
            points_in_finite_room=count, occupied_cell_coverage_fraction=coverage,
            queried_native_helper='_horizontal_support',
            reached_by_observed_ceiling=False, ceiling_height_inferred=False))
    return rows


def run(run_dir, room_id, out):
    run_dir, out = Path(run_dir).resolve(), Path(out).resolve()
    if out.exists() or out == run_dir or run_dir in out.parents or out in run_dir.parents:
        raise ValueError('Use a fresh diagnostic output separate from the retained run')
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    inputs = [run_dir / 'plan.json', run_dir / 'run.json',
              *[run_dir / 'artifacts' / name for name in
                ('cloud.npz', 'trajectory.json', 'rgbd_summary.json', 'layout_evidence.json')],
              Path(layout.__file__).resolve()]
    frozen = {str(p): sha256(p) for p in inputs}
    plan = read(inputs[0]); ledger = read(inputs[1]); meta = read(inputs[-2])
    summary = read(run_dir / 'artifacts/rgbd_summary.json')
    trajectory = read(run_dir / 'artifacts/trajectory.json')
    if any(sha256(run_dir / p) != h for p, h in ledger['geometry_artifact_sha256'].items()):
        raise ValueError('Saved geometry artifact integrity failed')
    if ledger['code_sha256']['layout.py'] != sha256(layout.__file__):
        raise ValueError('Native layout producer differs from the saved run')
    matching = [r for r in plan['rooms'] if r['id'] == room_id]
    if len(matching) != 1:
        raise ValueError('Expected a unique saved room identity')
    room = matching[0]; poly = Polygon(room['corners'])
    points = np.load(run_dir / 'artifacts/cloud.npz')['points']
    basis = np.asarray(meta['basis_columns_in_input'])
    aligned = points @ basis
    centers = np.asarray([row['camera_to_first'] for row in trajectory])[:, :3, 3] @ basis
    camera_path = centers[:, [0, 2, 1]].tolist()
    planes = summary['planes'] + meta.get('wall_seed_planes', []) + meta['wall_plane_proposals']
    reference = meta['wall_sampling_slab_bound_m'] if meta['floor_observed'] else None
    aligned.setflags(write=False)
    before = fingerprint(poly, aligned, planes, basis, camera_path)
    floor_trace = native_trace(layout._observed_floor, poly, aligned, planes, basis, camera_path,
                               reference_floor=reference)
    room_floor, floor_evidence = floor_trace['value']
    ceiling_trace = native_trace(layout._observed_ceiling, poly, aligned, planes, basis, camera_path,
                                 floor=room_floor)
    ceiling, ceiling_evidence = ceiling_trace['value']
    decisions = plane_decisions(floor_trace, planes)
    inventory = horizontal_inventory(poly, aligned, decisions)
    checks = dict(
        floor_level_exact=room_floor == room['floor_level_m'],
        floor_evidence_exact=floor_evidence == room['floor_evidence'],
        ceiling_height_exact=ceiling == room['ceiling_height_m'],
        ceiling_evidence_exact=ceiling_evidence == room['ceiling_evidence'],
        function_inputs_unchanged=before == fingerprint(poly, aligned, planes, basis, camera_path),
        saved_inputs_and_layout_code_unchanged=all(sha256(p) == h for p, h in frozen.items()))
    if not all(checks.values()):
        raise ValueError(f'Native room decision reproduction failed: {checks}')
    groups = {}
    for row in decisions:
        reason = (row['native_rejection'] or {}).get('rejected_by_native_condition', 'no_native_rejection')
        groups.setdefault(reason, []).append(row['plane_index'])
    result = dict(experiment='read_only_native_room_ceiling_decision_trace', run=str(run_dir), room_id=room_id,
        polygon_area_m2=poly.area, point_count=len(points), camera_count=len(centers), plane_count=len(planes),
        reference_projection_floor=reference, actual_local_room_floor=room_floor,
        local_floor_trace=floor_trace, local_floor_plane_decisions=decisions, floor_rejection_groups=groups,
        supplementary_horizontal_surface_inventory=inventory,
        observed_ceiling_trace=ceiling_trace,
        ceiling_planes_visited=len({row['plane_index'] for row in ceiling_trace['events'] if row['plane_index'] is not None}),
        checks=checks, inputs_sha256=frozen, script_sha256=sha256(__file__),
        native_production_functions=True, geometry_changed=False, thresholds_changed=False,
        production_changed=False, hypothetical_global_floor_ceiling_inference_run=False,
        accuracy_validated=False, acceptance_claimed=False,
        limitations=['Native decision reproduction is not independent physical measurement',
                    'Local floor support may be occluded or absent from the retained cloud',
                    'No point/plane/camera generation or selection changes in this diagnostic'])
    out.mkdir(parents=True)
    (out / 'trace.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('room_id', 'polygon_area_m2', 'point_count',
        'camera_count', 'plane_count', 'reference_projection_floor', 'actual_local_room_floor',
        'floor_rejection_groups', 'ceiling_planes_visited', 'checks')}, indent=2))
    for row in decisions:
        if row['native_horizontal_support_return'] is not None:
            print(json.dumps(row, indent=2))
    print(json.dumps(inventory, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default='demo/phase3_strip_trace/current_exterior/ceiling')
    parser.add_argument('--room', default='room_2')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    run(args.run, args.room, args.out)
