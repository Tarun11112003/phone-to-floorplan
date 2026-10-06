"""Conservative CPU wall-segment polygonization; no reference geometry inputs."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import polygonize, unary_union

from .pipeline import _dxf, _quantities, _svg


def weighted_voxels(points, colors=None, weights=None, size=0.02):
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all() or size <= 0:
        raise ValueError("Expected finite Nx3 points and positive voxel size")
    weights = np.ones(len(points)) if weights is None else np.asarray(weights, float)
    if weights.shape != (len(points),) or not np.isfinite(weights).all() or np.any(weights <= 0):
        raise ValueError("Voxel weights must be finite and positive")
    _, ids = np.unique(np.floor(points / size).astype(np.int64), axis=0, return_inverse=True)
    total = np.bincount(ids, weights=weights)
    xyz = np.column_stack([np.bincount(ids, weights=points[:, i] * weights) / total for i in range(3)])
    rgb = None if colors is None else np.column_stack([np.bincount(ids, weights=np.asarray(colors)[:, i] * weights) / total for i in range(3)])
    return xyz, rgb, total


def floor_basis(points, planes, camera_centers, down=None):
    """Estimate vertical from a supported plane, using camera down as a weak prior."""
    prior = np.asarray([0, 1, 0] if down is None else down, dtype=float)
    if prior.shape != (3,) or not np.isfinite(prior).all() or np.linalg.norm(prior) < 1e-8:
        raise ValueError("Invalid down direction")
    prior /= np.linalg.norm(prior)
    candidates = [p for p in planes if abs(np.dot(p['normal'], prior)) > np.cos(np.deg2rad(40))]
    if candidates:
        best = max(candidates, key=lambda p: p['support'])
        vertical = np.asarray(best['normal'], float)
        vertical_source = 'supported horizontal plane'
    else:
        # A footprint can be projected from walls without inventing a floor
        # surface. Infer vertical from two nonparallel, supported wall normals.
        options=[]
        for i,a in enumerate(planes):
            for b in planes[i+1:]:
                na,nb=np.asarray(a['normal']),np.asarray(b['normal'])
                if abs(np.dot(na,nb))>.15: continue
                direction=np.cross(na,nb); direction/=np.linalg.norm(direction)
                agreement=abs(np.dot(direction,prior))
                if agreement>np.cos(np.deg2rad(40)):
                    options.append((a['support']*b['support']*agreement,direction))
        if not options:
            raise ValueError('Neither floor nor two supported wall directions establish vertical')
        vertical=max(options,key=lambda pair:pair[0])[1]
        vertical_source='intersection of supported wall planes; floor not observed'
    vertical *= 1 if np.dot(vertical, prior) > 0 else -1
    vertical /= np.linalg.norm(vertical)
    walls = [p for p in planes if abs(np.dot(p['normal'], vertical)) < 0.15]
    if len(walls) < 3:
        raise ValueError("Insufficient supported vertical walls")
    x = np.asarray(max(walls, key=lambda p: p['support'])['normal'], float)
    x -= vertical * np.dot(x, vertical)
    x /= np.linalg.norm(x)
    z = np.cross(x, vertical)
    basis = np.column_stack([x, vertical, z])
    aligned = np.asarray(points) @ basis
    centers = np.asarray(camera_centers) @ basis
    # Floor is the furthest supported horizontal plane below the capture path.
    levels = [-p['offset'] / np.dot(p['normal'], vertical) for p in candidates]
    below = [level for level in levels if level > np.median(centers[:, 1]) + 0.3]
    floor_observed=bool(below)
    slab_bound=max(below) if below else float(np.quantile(aligned[:,1],.99))
    return aligned, centers, basis, slab_bound, {'vertical_source':vertical_source,'floor_observed':floor_observed}


def _segments(points, planes, basis, floor, upper_height=3.0):
    """Finite support intervals: retain holes rather than extending infinite planes."""
    segments = []
    for plane in planes:
        n = np.asarray(plane['normal']) @ basis
        if abs(n[1]) > 0.15:
            continue
        axis = int(np.argmax(np.abs(n[[0, 2]])))
        component = [0, 2][axis]
        other = [2, 0][axis]
        if abs(n[component]) < np.cos(np.deg2rad(8)):
            continue
        support = points[(np.abs(points @ n + plane['offset']) < 0.035) &
                         (points[:, 1] < floor - 0.25) & (points[:, 1] > floor - upper_height)]
        if len(support) < 40 or np.ptp(support[:, 1]) < 0.45:
            continue
        location = float(np.median(support[:, component]))
        bins = np.unique(np.floor(support[:, other] / 0.05).astype(int))
        groups = np.split(bins, np.flatnonzero(np.diff(bins) > 3) + 1)
        for group in groups:
            subset = support[(support[:, other] >= group[0] * 0.05) & (support[:, other] < (group[-1] + 1) * 0.05)]
            if len(subset)<40:
                continue
            rms=float(np.sqrt(np.mean((subset[:, component]-location)**2)))
            if rms>0.03:
                continue
            lo, hi = np.quantile(subset[:, other], [0.002, 0.998])
            if hi - lo < 0.25:
                continue
            segments.append({'axis': axis, 'location': location, 'lo': float(lo), 'hi': float(hi),
                             'support': len(subset), 'rms_m': rms})
    # Duplicate planes can arise from furniture or successive RANSAC residuals.
    merged = []
    for s in sorted(segments, key=lambda s: -s['support']):
        match = next((m for m in merged if m['axis'] == s['axis'] and abs(m['location'] - s['location']) < 0.06
                      and min(m['hi'], s['hi']) >= max(m['lo'], s['lo']) - 0.12), None)
        if match is None:
            merged.append(s.copy())
        else:
            match['lo'], match['hi'] = min(match['lo'], s['lo']), max(match['hi'], s['hi'])
    return merged


def _line(s):
    if s['axis'] == 0:
        return LineString([(s['location'], s['lo']), (s['location'], s['hi'])])
    return LineString([(s['lo'], s['location']), (s['hi'], s['location'])])


def _observed_ceiling(poly, points, planes, basis, floor, camera_path):
    """Use broad horizontal plane support above this room, never a height prior."""
    if floor is None or not camera_path:
        return None, None
    inside_cameras=[c for c in camera_path if poly.buffer(.05).covers(Point(c[:2]))]
    if not inside_cameras:
        return None, None
    camera_y=float(np.median([c[2] for c in inside_cameras]))
    candidates=[]
    for plane in planes:
        normal=np.asarray(plane['normal'],dtype=float)@basis
        if abs(normal[1])<.97 or plane.get('rms_m',1)>.03:
            continue
        level=-float(plane['offset'])/normal[1]
        height=floor-level
        if not 1.8<=height<=5.0 or level>camera_y-.5:
            continue
        support=points[np.abs(points@normal+plane['offset'])<.035]
        support=support[(support[:,1]>level-.04)&(support[:,1]<level+.04)]
        support=support[[poly.buffer(.05).covers(Point(p[0],p[2])) for p in support]]
        if len(support)<100:
            continue
        spread=MultiPoint(support[:2000,[0,2]]).convex_hull.area
        coverage=min(spread/poly.area,1.)
        if coverage<.25:
            continue
        candidates.append((coverage,len(support),height,plane.get('rms_m')))
    if not candidates:
        return None,None
    coverage,count,height,rms=max(candidates)
    return float(height),dict(source='supported ceiling plane',support_points=count,
                              coverage_fraction=float(coverage),plane_rms_m=rms)


def extract_layout(points, planes, camera_centers, down=None, path_breaks=()):
    aligned, centers, basis, floor, orientation_evidence = floor_basis(points, planes, camera_centers, down)
    segments = _segments(aligned, planes, basis, floor)
    path = centers[:, [0, 2]]
    # Suppress a nearby duplicate face only when all cameras observed the same
    # side. Preserve distinct sides of a partition visited from different rooms.
    retained = []
    for s in sorted(segments, key=lambda s: -s['support']/max(s['rms_m'],0.003)):
        duplicate = False
        for other in retained:
            overlap = min(s['hi'],other['hi'])-max(s['lo'],other['lo'])
            same_side = np.all(path[:,s['axis']] < min(s['location'],other['location'])) or np.all(path[:,s['axis']] > max(s['location'],other['location']))
            if s['axis']==other['axis'] and abs(s['location']-other['location']) < 0.15 and overlap > 0.7*min(s['hi']-s['lo'],other['hi']-other['lo']) and same_side:
                duplicate = True
                break
        if not duplicate: retained.append(s)
    segments = retained
    traversals = [LineString([a, b]) for i,(a, b) in enumerate(zip(path[:-1], path[1:])) if i+1 not in path_breaks and np.linalg.norm(a-b) < 1.5]
    doors = []
    # Only close a doorway-size gap if the camera actually crossed it.
    doorway_segments = _segments(aligned, planes, basis, floor, upper_height=1.8)
    for i, a in enumerate(doorway_segments):
        for b in doorway_segments[i+1:]:
            if a['axis'] != b['axis'] or abs(a['location'] - b['location']) > 0.06:
                continue
            left, right = sorted([a, b], key=lambda s: s['lo'])
            gap = right['lo'] - left['hi']
            if not 0.55 <= gap <= 1.4:
                continue
            bridge = {'axis': a['axis'], 'location': (a['location']+b['location'])/2,
                      'lo': left['hi'], 'hi': right['lo'], 'support': 0, 'rms_m': None}
            same_wall = [s for s in segments if s['axis']==bridge['axis'] and abs(s['location']-bridge['location']) < 0.06]
            if same_wall:
                bridge['location'] = max(same_wall,key=lambda s:s['support'])['location']
            if any(t.crosses(_line(bridge)) for t in traversals):
                doors.append(bridge)
    network = [dict(s) for s in segments] + [dict(s,lo=s['lo']-0.01,hi=s['hi']+0.01) for s in doors]
    # Intersect nearby perpendicular endpoints, bounded to observed corner gaps.
    for a in network:
        for b in network:
            if a['axis'] == b['axis']:
                continue
            if a['lo'] - 0.15 <= b['location'] <= a['hi'] + 0.15 and b['lo'] - 0.15 <= a['location'] <= b['hi'] + 0.15:
                a['lo'], a['hi'] = min(a['lo'], b['location']), max(a['hi'], b['location'])
    polygons = list(polygonize(unary_union([_line(s) for s in network]))) if network else []
    polygons = [p.simplify(0.005, preserve_topology=True) for p in polygons
                if p.area >= 1 and not p.interiors and any(p.buffer(0.05).covers(Point(c)) for c in path)]
    polygons.sort(key=lambda p: (p.centroid.x, p.centroid.y))
    rooms = []
    for i, poly in enumerate(polygons):
        corners = list(poly.exterior.coords)[:-1]
        ceiling,ceiling_evidence=_observed_ceiling(poly,aligned,planes,basis,
                                                   floor if orientation_evidence['floor_observed'] else None,
                                                   centers[:,[0,2,1]].tolist())
        rooms.append({'id': f'room_{i}', 'label': f'Room {i+1}', 'corners': corners,
                      'local_corners': corners, 'placement': 'origin' if i == 0 else 'stitched',
                      'metric_status': 'sensor_scaled', 'ceiling_height_m': ceiling,
                      'ceiling_evidence':ceiling_evidence,'openings': []})
    connections = []
    for d in doors:
        line = _line(d)
        incident = [i for i, p in enumerate(polygons) if p.boundary.buffer(0.04).intersection(line).length >= line.length * 0.8]
        if len(incident) != 2:
            continue
        connections.append({'rooms': [rooms[i]['id'] for i in incident], 'width_m': line.length,
                            'segment': list(line.coords), 'evidence': 'observed gap and camera traversal'})
        for i in incident:
            corners = np.asarray(rooms[i]['corners'])
            for j, (a, b) in enumerate(zip(corners, np.roll(corners, -1, axis=0))):
                edge = LineString([a, b])
                if edge.buffer(0.04).intersection(line).length >= line.length * 0.8:
                    fractions = sorted(edge.project(Point(p), normalized=True) for p in line.coords)
                    rooms[i]['openings'].append({'edge_index': j, 'start_fraction': fractions[0],
                                                'end_fraction': fractions[1], 'height_m': None,
                                                'kind': 'doorway', 'evidence': 'traversal'})
                    break
    camera_coverage=float(np.mean([any(p.buffer(.10).covers(Point(c)) for p in polygons) for c in path]))
    return rooms, {'basis_columns_in_input': basis.tolist(), 'floor_level_m': floor if orientation_evidence['floor_observed'] else None,
                   'wall_sampling_slab_bound_m':floor, **orientation_evidence,
                   'wall_segments': segments, 'connections': connections,
                   'camera_path_2d': path.tolist(), 'camera_center_coverage_fraction':camera_coverage,
                   'unclosed_geometry': not bool(rooms) or camera_coverage<.9,
                   'path_breaks':list(path_breaks),
                   'assumptions': ['straight orthogonal walls within 8 degrees', 'floor normal within 40 degrees of supplied down or first-camera down',
                                   'small endpoint gaps <=15 cm may be joined', 'only traversed doorway gaps are closed']}


def render_layout_diagnostic(metadata, output: Path):
    """Show observed wall segments even when they cannot close a floor plan."""
    segments=metadata.get('wall_segments',[])
    path=metadata.get('camera_path_2d',[])
    endpoints=[]
    for segment in segments:
        if segment['axis']==0:
            endpoints.append(((segment['location'],segment['lo']),(segment['location'],segment['hi'])))
        else:
            endpoints.append(((segment['lo'],segment['location']),(segment['hi'],segment['location'])))
    all_points=[point for pair in endpoints for point in pair]+[tuple(p) for p in path]
    if not all_points:
        return None
    xs,zs=zip(*all_points)
    min_x,max_x=min(xs)-.5,max(xs)+.5
    min_z,max_z=min(zs)-.5,max(zs)+.5
    scale=min(740/(max_x-min_x),700/(max_z-min_z))
    def xy(point):
        return (40+(point[0]-min_x)*scale,740-(point[1]-min_z)*scale)
    lines=['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800">',
           '<rect width="800" height="800" fill="#fff"/>',
           '<text x="40" y="28" font-family="Arial" font-size="18">Observed geometry (metres)</text>']
    if len(path)>1:
        coords=' '.join(f'{x:.1f},{y:.1f}' for x,y in map(xy,path))
        lines.append(f'<polyline points="{coords}" fill="none" stroke="#bbb" stroke-width="2"/>')
    for left,right in endpoints:
        x1,y1=xy(left); x2,y2=xy(right)
        lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#135d99" stroke-width="4"/>')
        for x,y in ((x1,y1),(x2,y2)):
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#135d99"/>')
    lines.append('<text x="40" y="780" font-family="Arial" font-size="15" fill="#a33">Blue: supported walls. Grey: camera path. Gaps remain unclosed.</text>')
    lines.append('</svg>')
    output.write_text('\n'.join(lines),encoding='utf-8')
    return output


def export_layout(rooms, metadata, output: Path, metric_status='sensor_scaled', complete_capture=True):
    if not rooms:
        raise ValueError('No closed room supported by observed walls and camera coverage')
    for room in rooms:
        room['metric_status'] = metric_status
    complete_capture=complete_capture and not metadata.get('unclosed_geometry',False)
    rows = [_quantities(room) for room in rooms]
    plan = {'schema_version': 2, 'units': 'metres', 'rooms': rooms, 'quantities': rows,
            'connections': metadata.get('connections', []), 'provenance': metadata,
            'status': 'proposal_requires_review' if complete_capture else 'partial',
            'accuracy_validated': False}
    (output / 'plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    _svg(rooms, output / 'plan.svg')
    _dxf(rooms, output / 'plan.dxf')
    with (output / 'quantities.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return plan
