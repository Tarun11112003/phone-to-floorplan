"""Conservative CPU wall-segment polygonization; no reference geometry inputs."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from shapely import union_all
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import polygonize, polygonize_full

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
    levels = [-p['offset'] / np.dot(p['normal'], vertical) for p in candidates]
    below = [level for level in levels if level > np.median(np.asarray(camera_centers)@vertical) + 0.3]
    wall_seeds=[]
    walls = [p for p in planes if abs(np.dot(p['normal'], vertical)) < 0.15]
    if not walls and below:
        # Global plane selection can contain only horizontal surfaces even when
        # the cloud has observed walls. Reserve a bounded secondary fit for the
        # actual above-floor band; do not assume a wall orientation or extent.
        from .rgbd import _fit_planes
        points=np.asarray(points,float)
        heights=max(below)-points@vertical
        band=points[(heights>.25)&(heights<3.)]
        if len(band)>=500:
            sample_fraction=min(18000,len(points))/len(points)
            for plane in _fit_planes(band):
                normal=np.asarray(plane['normal'])
                if abs(normal@vertical)>=.15 or plane['rms_m']>.025: continue
                observed=band[np.abs(band@normal+plane['offset'])<.025]
                if len(observed)*sample_fraction<250: continue
                if np.ptp(np.quantile(observed@vertical,[.05,.95]))<.45: continue
                wall_seeds.append({**plane,'support':int(len(observed)*sample_fraction),
                    'raw_support_points':len(observed),
                    'support_basis':'equivalent count in the global <=18000 point sample',
                    'proposal_source':'above observed floor band RANSAC; global fit omitted all wall directions'})
            walls=wall_seeds
    # One supported wall and a supported vertical establish the projection
    # frame. Boundary completeness is checked after finite wall extraction;
    # a global RANSAC budget is not evidence that other walls were unobserved.
    if not walls:
        raise ValueError("Insufficient supported vertical walls")
    x = np.asarray(max(walls, key=lambda p: p['support'])['normal'], float)
    x -= vertical * np.dot(x, vertical)
    x /= np.linalg.norm(x)
    z = np.cross(x, vertical)
    basis = np.column_stack([x, vertical, z])
    aligned = np.asarray(points) @ basis
    centers = np.asarray(camera_centers) @ basis
    # Floor is the furthest supported horizontal plane below the capture path.
    floor_observed=bool(below)
    slab_bound=max(below) if below else float(np.quantile(aligned[:,1],.99))
    return aligned, centers, basis, slab_bound, {'vertical_source':vertical_source,'floor_observed':floor_observed,
                                               'wall_seed_planes':wall_seeds}


def _projection_wall_proposals(points, planes, basis, floor, *, support_policy='local_spatial', accepted_limit=12,
                               seed_points=None, exterior_only=False):
    """Find omitted wall modes, then refit actual 3D support without gap filling.

    Global RANSAC can spend its plane budget on furniture/horizontal surfaces.
    Projection modes are proposals only: raw plane residual, two-dimensional
    support are required. Local acceptance must not depend on unrelated property
    surfaces. Global-equivalent counts remain comparable plane-ranking weights.
    The historical policy is retained for controlled identical-cloud comparisons.
    """
    points=np.asarray(points,float)
    if support_policy not in {'local_spatial','global_equivalent'}:
        raise ValueError('Unknown wall support policy')
    aligned=points@basis
    band=points[(aligned[:,1]<floor-.25)&(aligned[:,1]>floor-3.)]
    if len(band)<250: return []
    seed_band=band
    if seed_points is not None:
        seed_points=np.asarray(seed_points,float)
        seed_aligned=seed_points@basis
        seed_band=seed_points[(seed_aligned[:,1]<floor-.25)&(seed_aligned[:,1]>floor-3.)]
    sample_fraction=min(18000,len(points))/len(points)
    acceptance_fraction=sample_fraction if support_policy=='global_equivalent' else 1.
    proposals=[]
    for axis in (0,2):
        direction=basis[:,axis]; values=band@direction
        seed_values=seed_band@direction
        lo,hi=float(seed_values.min()),float(seed_values.max())
        if hi-lo<.025: continue
        # Bound memory as well as the number of candidate fits.
        if (hi-lo)/.025>20000: continue
        # Empty border bins let genuine extrema be local maxima too.
        edges=np.arange(np.floor(lo/.025)*.025-.05,hi+.075,.025)
        counts,_=np.histogram(seed_values,edges)
        maxima=[i for i in range(1,len(counts)-1)
                if counts[i]>=250 and counts[i]>=counts[i-1] and counts[i]>=counts[i+1]]
        selected=[]
        represented=[float(np.asarray(p['centroid'])@direction) for p in planes
                     if abs(np.asarray(p['normal'])@direction)>=np.cos(np.deg2rad(8))]
        axis_start=len(proposals)
        # Rejecting furniture is not finding a wall. Retain the original cap
        # accepted quota for this stage, with a bounded reserve search.
        fit_budget=12 if support_policy=='global_equivalent' else 48
        for index in sorted(maxima,key=lambda i:(-int(counts[i]),i))[:fit_budget]:
            if len(proposals)-axis_start>=accepted_limit: break
            location=float((edges[index]+edges[index+1])/2)
            # Original modes may propose unexplained outer surfaces. Replaying
            # interior modes can add competing partitions to existing cells.
            # This is a search restriction, not assumed exterior geometry.
            if exterior_only and represented and min(represented)-.05<=location<=max(represented)+.05:
                continue
            if any(abs(location-p)<.05 for p in selected): continue
            selected.append(location)
            subset=band[np.abs(values-location)<.035]
            for _ in range(3):
                center=subset.mean(axis=0)
                _,_,vt=np.linalg.svd(subset-center,full_matrices=False)
                normal=vt[-1]; offset=-float(normal@center)
                subset=band[np.abs(band@normal+offset)<.025]
                if len(subset)*acceptance_fraction<250: break
            if len(subset)*acceptance_fraction<250: continue
            # Refit the final consensus instead of reporting a stale seed fit.
            center=subset.mean(axis=0)
            _,singular,vt=np.linalg.svd(subset-center,full_matrices=False)
            normal=vt[-1]; offset=-float(normal@center)
            rms=float(np.sqrt(np.mean((subset@normal+offset)**2)))
            if singular[1]<1e-8 or rms>.025 or abs(normal@basis[:,1])>.15:
                continue
            if abs(normal@direction)<np.cos(np.deg2rad(8)): continue
            tangent=np.cross(basis[:,1],normal); tangent/=np.linalg.norm(tangent)
            height_span=float(np.ptp(np.quantile(subset@basis[:,1],[.05,.95])))
            length_span=float(np.ptp(np.quantile(subset@tangent,[.05,.95])))
            if height_span<.9 or length_span<.6: continue
            cells=np.floor(np.column_stack([subset@tangent,subset@basis[:,1]])/.10).astype(np.int64)
            occupied_cells=len(np.unique(cells,axis=0))
            if support_policy=='local_spatial' and occupied_cells<40: continue
            if any(abs(np.asarray(p['normal'])@normal)>.998 and
                   abs(np.asarray(p['centroid'])@normal+offset)<.02
                   for p in planes+proposals): continue
            proposals.append(dict(normal=normal.tolist(),offset=offset,
                support=int(len(subset)*sample_fraction),raw_support_points=len(subset),
                support_basis='equivalent count in the global <=18000 point sample',
                centroid=center.tolist(),rms_m=rms,observed_height_span_m=height_span,
                observed_length_span_m=length_span,
                support_policy=support_policy,occupied_10cm_cells=occupied_cells,
                acceptance_minimum_raw_points=250 if support_policy=='local_spatial' else None,
                acceptance_minimum_10cm_cells=40 if support_policy=='local_spatial' else None,
                proposal_source='wall projection mode; raw 3D plane consensus'))
    return proposals


def _supported_wall_proposals(points, planes, basis, floor, *, support_policy='local_spatial', residual_search=True,
                              original_seed_search=True):
    """Retain initial planes; discover omitted surfaces from unexplained points.

    Reusing already explained observations for every seed creates near-duplicate
    planes that can change existing cells. A second bounded stage uses only raw
    points outside the existing 35 mm plane-support band. It retains every
    initial proposal and all original support thresholds, with at most eight
    additional proposals per axis. Unused quota can retry original supported
    outer modes against the same residual consensus: bin dilution alone must
    not erase sufficient raw support. Interior original-mode replay is withheld.
    Historical global-equivalent behavior stays unchanged for comparisons.
    """
    initial=_projection_wall_proposals(points,planes,basis,floor,support_policy=support_policy)
    if support_policy!='local_spatial' or not residual_search:
        return initial
    if not any(sum(abs(np.asarray(p['normal'])@basis[:,axis])>=np.cos(np.deg2rad(8))
                   for p in initial)>=12 for axis in (0,2)):
        return initial
    points=np.asarray(points,float)
    remaining=np.ones(len(points),dtype=bool)
    for plane in planes+initial:
        remaining &= np.abs(points@np.asarray(plane['normal'])+plane['offset'])>=.035
    additions=_projection_wall_proposals(points[remaining],planes+initial,basis,floor,
                                         support_policy=support_policy,accepted_limit=8)
    # Keep ranking counts in the original cloud's sampling domain. Residual
    # clouds must not inflate a new surface's weight over an existing fit.
    fraction=min(18000,len(points))/len(points)
    for plane in additions:
        plane['support']=int(plane['raw_support_points']*fraction)
        plane['proposal_source']='wall projection mode; unexplained raw 3D plane consensus'
    current=initial+additions
    if not original_seed_search:
        return current
    quota={axis:8-sum(abs(np.asarray(p['normal'])@basis[:,axis])>=np.cos(np.deg2rad(8))
                     for p in additions) for axis in (0,2)}
    if max(quota.values())<=0:
        return current
    retries=_projection_wall_proposals(points[remaining],planes+current,basis,floor,
        support_policy=support_policy,accepted_limit=max(quota.values()),seed_points=points,exterior_only=True)
    for plane in retries:
        axis=max((0,2),key=lambda a:abs(np.asarray(plane['normal'])@basis[:,a]))
        if quota[axis]<=0:
            continue
        quota[axis]-=1
        plane['support']=int(plane['raw_support_points']*fraction)
        plane['proposal_source']='wall projection mode; original seed with unexplained raw 3D plane consensus'
        current.append(plane)
    return current


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
        # Axis projection spread includes sensor noise. Use the fitted plane's
        # lateral displacement across its full support to resolve inclination.
        # Keep this choice identical across wall fragments and doorway bridges.
        inclination_span=float(abs(n[other]/n[component])*np.ptp(support[:,other]))
        resolved_inclination=inclination_span>.006
        bins = np.unique(np.floor(support[:, other] / 0.05).astype(int))
        groups = np.split(bins, np.flatnonzero(np.diff(bins) > 3) + 1)
        for group in groups:
            subset = support[(support[:, other] >= group[0] * 0.05) & (support[:, other] < (group[-1] + 1) * 0.05)]
            if len(subset)<40:
                continue
            # A coplanar short furniture face must not inherit the height span
            # of a distant wall elsewhere in the same plane consensus.
            if np.ptp(subset[:,1])<.45:
                continue
            rms=float(np.sqrt(np.mean((subset@n+plane['offset'])**2)))
            if rms>0.03:
                continue
            lo, hi = np.quantile(subset[:, other], [0.002, 0.998])
            if hi - lo < 0.25:
                continue
            segments.append({'axis': axis, 'location': location, 'lo': float(lo), 'hi': float(hi),
                             'support': len(subset), 'rms_m': rms,
                             'plane_line':[float(n[0]),float(n[2]),float(plane['offset']+n[1]*floor)],
                             'plane_line_resolved':resolved_inclination,
                             'fitted_inclination_span_m':inclination_span,
                             'axis_projection_rms_m':float(np.sqrt(np.mean((subset[:,component]-location)**2)))})
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
    if s.get('network_endpoints') is not None:
        return LineString(s['network_endpoints'])
    if s.get('plane_line') is not None and s.get('plane_line_resolved',s.get('axis_projection_rms_m',1)>.003):
        nx,nz,offset=s['plane_line']
        if s['axis']==0:
            return LineString([((-offset-nz*t)/nx,t) for t in (s['lo'],s['hi'])])
        return LineString([(t,(-offset-nx*t)/nz) for t in (s['lo'],s['hi'])])
    if s['axis'] == 0:
        return LineString([(s['location'], s['lo']), (s['location'], s['hi'])])
    return LineString([(s['lo'], s['location']), (s['hi'], s['location'])])


def _bounded_corner_network(network,max_gap_m=.15):
    """Intersect observed finite lines without snapping their entire wall planes."""
    endpoints=[np.asarray(_line(segment).coords,float) for segment in network]
    proposals=[[[],[]] for _ in network]
    # Evaluate every intersection against immutable observations. Updating lines
    # during the search can chain 15 cm extensions and tear previous junctions.
    # Canonical pair order also keeps floating-point solves independent of the
    # order in which equally supported wall fragments were supplied.
    order=sorted(range(len(endpoints)),key=lambda i:tuple(endpoints[i].ravel()))
    for position,i in enumerate(order):
        a=endpoints[i]
        for j in order[:position]:
            b=endpoints[j]
            da=a[1]-a[0]; db=b[1]-b[0]
            la,lb=np.linalg.norm(da),np.linalg.norm(db)
            if min(la,lb)<1e-8: continue
            ua,ub=da/la,db/lb
            if abs(np.linalg.det(np.column_stack([ua,ub])))<.2: continue
            t,s=np.linalg.solve(np.column_stack([ua,-ub]),b[0]-a[0])
            if not -max_gap_m<=t<=la+max_gap_m or not -max_gap_m<=s<=lb+max_gap_m: continue
            corner=a[0]+t*ua
            if abs(t)<=max_gap_m: proposals[i][0].append((t,corner))
            elif abs(t-la)<=max_gap_m: proposals[i][1].append((t,corner))
            if abs(s)<=max_gap_m: proposals[j][0].append((s,corner))
            elif abs(s-lb)<=max_gap_m: proposals[j][1].append((s,corner))
    for points,candidates in zip(endpoints,proposals):
        # Keep all eligible intersections along the finite wall. Choosing an
        # inner junction can disconnect another supported crossing near the
        # same endpoint. Both extrema are still bounded by the original extent.
        if candidates[0]: points[0]=min(candidates[0],key=lambda c:c[0])[1]
        if candidates[1]: points[1]=max(candidates[1],key=lambda c:c[0])[1]
    for segment,points in zip(network,endpoints): segment['network_endpoints']=points.tolist()
    return network


def _horizontal_support(poly,points,normal,offset):
    support=points[np.abs(points@normal+offset)<.035]
    support=support[[poly.buffer(.05).covers(Point(p[0],p[2])) for p in support]]
    if len(support)<100: return len(support),0.
    from shapely.geometry import box
    cell_m=.20
    cells=np.unique(np.floor(support[:,[0,2]]/cell_m).astype(int),axis=0)
    area=sum(poly.intersection(box(x*cell_m,z*cell_m,(x+1)*cell_m,(z+1)*cell_m)).area for x,z in cells)
    return len(support),min(area/poly.area,1.)


def _observed_floor(poly,points,planes,basis,camera_path,reference_floor=None):
    """A floor measured in another room is not this room's floor observation."""
    cameras=[c for c in camera_path if poly.buffer(.05).covers(Point(c[:2]))]
    if not cameras: return None,None
    camera_y=float(np.median([c[2] for c in cameras])); candidates=[]
    x,z=poly.centroid.coords[0]
    for plane in planes:
        normal=np.asarray(plane['normal'],float)@basis
        if abs(normal[1])<.97 or plane.get('rms_m',1)>.03: continue
        level=-(plane['offset']+normal[0]*x+normal[2]*z)/normal[1]
        if level<=camera_y+.3: continue
        # The footprint is expressed on the observed storey floor datum. A
        # table/bed below the camera cannot replace it. Different floor levels
        # need separate geometry support rather than a borrowed room height.
        if reference_floor is not None and abs(level-reference_floor)>.04: continue
        count,coverage=_horizontal_support(poly,points,normal,plane['offset'])
        if coverage<.25: continue
        candidates.append((level,coverage,count,plane.get('rms_m')))
    if not candidates: return None,None
    level,coverage,count,rms=max(candidates)
    return float(level),dict(source='supported per-room floor plane',support_points=count,
        coverage_fraction=float(coverage),coverage_method='occupied 20 cm cells clipped to room',
        plane_rms_m=rms,evaluation_location_xz=[x,z])


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
        x,z=poly.centroid.coords[0]
        # Evaluate the plane locally. The global-origin intercept changes under
        # a horizontal gauge shift when the observed plane is slightly tilted.
        level=-(float(plane['offset'])+normal[0]*x+normal[2]*z)/normal[1]
        height=floor-level
        if not 1.8<=height<=5.0 or level>camera_y-.5:
            continue
        count,coverage=_horizontal_support(poly,points,normal,plane['offset'])
        if coverage<.25:
            continue
        corners=np.asarray(poly.exterior.coords)
        heights=floor+(plane['offset']+normal[0]*corners[:,0]+normal[2]*corners[:,1])/normal[1]
        candidates.append((coverage,count,height,plane.get('rms_m'),float(heights.min()),float(heights.max())))
    if not candidates:
        return None,None
    coverage,count,height,rms,minimum,maximum=max(candidates)
    # A resolved slope needs an agreed height definition before scalar scoring.
    # Three centimetres is the declared development resolution for this guard,
    # not a relaxed accuracy gate. Preserve the observed range and centroid.
    sloped=maximum-minimum>.03
    return None if sloped else float(height),dict(source='supported ceiling plane',support_points=count,
        coverage_fraction=float(coverage),coverage_method='occupied 20 cm cells clipped to room',plane_rms_m=rms,
        height_at_centroid_m=float(height),height_range_m=[minimum,maximum],
        evaluation_location_xz=list(poly.centroid.coords[0]),
        height_definition='unavailable: resolved slope needs external scoring definition' if sloped else 'observed plane at room centroid')


def extract_layout(points, planes, camera_centers, down=None, path_breaks=(), *, wall_support_policy='local_spatial'):
    stages={'global_planes':len(planes)}
    aligned, centers, basis, floor, orientation_evidence = floor_basis(points, planes, camera_centers, down)
    stages['secondary_wall_planes']=len(orientation_evidence['wall_seed_planes'])
    planes=planes+orientation_evidence['wall_seed_planes']
    proposals=_supported_wall_proposals(points,planes,basis,floor,support_policy=wall_support_policy)
    planes=planes+proposals
    segments = _segments(aligned, planes, basis, floor)
    stages.update(wall_proposals=len(proposals),segments_before_face_filter=len(segments))
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
    stages['retained_wall_segments']=len(segments)
    traversals = [LineString([a, b]) for i,(a, b) in enumerate(zip(path[:-1], path[1:])) if i+1 not in path_breaks and np.linalg.norm(a-b) < 1.5]
    doors = []
    # Only close a doorway-size gap if the camera actually crossed it.
    doorway_segments = _segments(aligned, planes, basis, floor, upper_height=1.8)
    stages.update(lower_band_segments=len(doorway_segments),door_gap_candidates=0,
                  rejected_untraversed_gaps=0)
    for i, a in enumerate(doorway_segments):
        for b in doorway_segments[i+1:]:
            if a['axis'] != b['axis'] or abs(a['location'] - b['location']) > 0.06:
                continue
            left, right = sorted([a, b], key=lambda s: s['lo'])
            gap = right['lo'] - left['hi']
            if not 0.55 <= gap <= 1.4:
                continue
            stages['door_gap_candidates']+=1
            bridge = {'axis': a['axis'], 'location': (a['location']+b['location'])/2,
                      'lo': left['hi'], 'hi': right['lo'], 'support': 0, 'rms_m': None}
            same_wall = [s for s in segments if s['axis']==bridge['axis'] and abs(s['location']-bridge['location']) < 0.06]
            if same_wall:
                strongest=max(same_wall,key=lambda s:s['support'])
                bridge['location'] = strongest['location']
                if strongest.get('plane_line') is not None:
                    bridge['plane_line']=strongest['plane_line']
                    bridge['axis_projection_rms_m']=strongest['axis_projection_rms_m']
                    bridge['plane_line_resolved']=strongest['plane_line_resolved']
            if any(t.crosses(_line(bridge)) for t in traversals):
                doors.append(bridge)
            else:
                stages['rejected_untraversed_gaps']+=1
    network = [dict(s) for s in segments] + [dict(s,lo=s['lo']-0.01,hi=s['hi']+0.01) for s in doors]
    network=_bounded_corner_network(network)
    # GEOS must node interior crossings and endpoints in the same numerical
    # domain. Independently solved corners can differ by ~1e-16 m and leave an
    # otherwise supported partition disconnected. This is a 1 nanometre grid,
    # not a wall-gap tolerance or sensor-accuracy claim; observed fits stay raw.
    union=union_all([_line(s) for s in network],grid_size=1e-9)
    polygons = list(polygonize(union)) if network else []
    _,cuts,dangles,invalid=polygonize_full(union)
    rejected=[]
    for p in polygons:
        reasons=[]
        if p.area<1: reasons.append('area_below_existing_1m2_guard')
        if p.interiors: reasons.append('interior_rings')
        if not any(p.buffer(.05).covers(Point(c)) for c in path): reasons.append('no_camera_inside')
        if reasons:
            rejected.append(dict(area_m2=float(p.area),reasons=reasons,
                                 corners=[list(c) for c in p.exterior.coords]))
    stages.update(door_bridges=len(doors),network_segments=len(network),
                  raw_polygons=len(polygons),cut_edges=len(cuts.geoms),
                  dangles=len(dangles.geoms),invalid_rings=len(invalid.geoms))
    polygons = [p.simplify(0.005, preserve_topology=True) for p in polygons
                if p.area >= 1 and not p.interiors and any(p.buffer(0.05).covers(Point(c)) for c in path)]
    polygons.sort(key=lambda p: (p.centroid.x, p.centroid.y))
    stages['accepted_observed_polygons']=len(polygons)
    from .supported_cells import propose_supported_cells
    inferred,fallback_evidence=propose_supported_cells(segments,path,occupied_cells=polygons)
    # Keep observed cell IDs/order and evidence unchanged. Partial hypotheses
    # may fill separately visited regions but cannot replace observed geometry.
    boundary_evidence=[None]*len(polygons)+fallback_evidence
    polygons=polygons+inferred
    stages['inferred_fallback_cells']=len(fallback_evidence)
    rooms = []
    for i, poly in enumerate(polygons):
        corners = list(poly.exterior.coords)[:-1]
        room_floor,floor_evidence=_observed_floor(poly,aligned,planes,basis,centers[:,[0,2,1]].tolist(),
            floor if orientation_evidence['floor_observed'] else None)
        ceiling,ceiling_evidence=_observed_ceiling(poly,aligned,planes,basis,
                                                   room_floor,
                                                   centers[:,[0,2,1]].tolist())
        rooms.append({'id': f'room_{i}', 'label': f'Room {i+1}', 'corners': corners,
                      'local_corners': corners, 'placement': 'origin' if i == 0 else 'stitched',
                      'metric_status': 'sensor_scaled', 'ceiling_height_m': ceiling,
                      'floor_observed':room_floor is not None,'floor_level_m':room_floor,'floor_evidence':floor_evidence,
                      'ceiling_evidence':ceiling_evidence,'openings': []})
        if boundary_evidence[i] is not None:
            rooms[-1]['boundary_evidence']=boundary_evidence[i]
            rooms[-1]['requires_boundary_review']=True
    connections = []
    for d in doors:
        line = _line(d)
        incident = [i for i, p in enumerate(polygons) if p.boundary.buffer(0.04).intersection(line).length >= line.length * 0.8]
        if len(incident) != 2 or any(boundary_evidence[i] is not None for i in incident):
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
                   'boundary_stages':stages,
                   'corner_join_policy':'simultaneous original finite support; maximum endpoint displacement 0.15 m',
                   'polygonization_precision_grid_m':1e-9,
                   'boundary_network':[dict(s,source_kind='observed_wall' if i<len(segments) else 'traversed_gap')
                                       for i,s in enumerate(network)],
                   'polygonization_diagnostics':dict(
                       cut_edges=[list(g.coords) for g in cuts.geoms],
                       dangles=[list(g.coords) for g in dangles.geoms],
                       invalid_rings=[list(g.coords) for g in invalid.geoms],
                       rejected_polygons=rejected),
                   'wall_plane_proposals':proposals,
                   'wall_support_policy':wall_support_policy,
                   'wall_proposal_limits':dict(maximum_candidate_bins_per_axis=144 if wall_support_policy=='local_spatial' else 12,
                                               maximum_candidate_bins_per_axis_per_stage=48 if wall_support_policy=='local_spatial' else 12,
                                               maximum_search_stages=3 if wall_support_policy=='local_spatial' else 1,
                                               maximum_accepted_proposals_per_axis=20 if wall_support_policy=='local_spatial' else 12,
                                               initial_accepted_proposals_per_axis=12,
                                               residual_accepted_proposals_per_axis=8 if wall_support_policy=='local_spatial' else 0,
                                               residual_exclusion_distance_m=.035 if wall_support_policy=='local_spatial' else None,
                                               original_seed_replay='outside represented axis-family centroid span plus 5 cm; residual consensus only; unused residual quota' if wall_support_policy=='local_spatial' else None),
                   'camera_path_2d': path.tolist(), 'camera_center_coverage_fraction':camera_coverage,
                   'unclosed_geometry': not bool(rooms) or camera_coverage<.9 or bool(fallback_evidence),
                   'inferred_room_boundaries':fallback_evidence,
                   'partial_cell_policy':'append nonoverlapping supported hypotheses from uncovered camera samples; observed cells retained; inferred edges cannot establish adjacency',
                   'path_breaks':list(path_breaks),
                   'assumptions': ['straight wall families within 8 degrees of dominant axes; fitted finite plane lines retained', 'floor normal within 40 degrees of supplied down or first-camera down',
                                   'small endpoint gaps <=15 cm may be joined', 'only traversed doorway gaps are closed']}


def render_layout_diagnostic(metadata, output: Path):
    """Show observed wall segments even when they cannot close a floor plan."""
    segments=metadata.get('wall_segments',[])
    path=metadata.get('camera_path_2d',[])
    endpoints=[]
    for segment in segments:
        endpoints.append(tuple(_line(segment).coords))
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
