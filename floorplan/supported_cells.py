"""Bounded room hypotheses from measured wall fragments, with explicit gaps."""
from __future__ import annotations

from itertools import combinations

import numpy as np
from shapely import covers, points as geometry_points
from shapely.geometry import Polygon


def _groups(segments, axis, tolerance=.18):
    groups=[]
    for segment in sorted((s for s in segments if s['axis']==axis),key=lambda s:s['location']):
        group=next((g for g in groups if segment['location']-g[0]['location']<=tolerance),None)
        if group is None:
            groups.append([segment])
        else:
            group.append(segment)
    result=[]
    for group in groups:
        weights=np.asarray([s['support'] for s in group],float)
        location=float(np.average([s['location'] for s in group],weights=weights))
        result.append(dict(location=location,segments=group,
                           max_location_shift_m=max(abs(s['location']-location) for s in group)))
    return result


def _edge_evidence(group, lo, hi):
    intervals=sorted((max(lo,s['lo']),min(hi,s['hi'])) for s in group['segments']
                     if min(hi,s['hi'])>max(lo,s['lo']))
    merged=[]
    for left,right in intervals:
        if merged and left<=merged[-1][1]:
            merged[-1][1]=max(merged[-1][1],right)
        else:
            merged.append([left,right])
    gaps=[]
    cursor=lo
    for left,right in merged:
        if left-cursor>.01: gaps.append([cursor,left])
        cursor=max(cursor,right)
    if hi-cursor>.01: gaps.append([cursor,hi])
    coverage=sum(right-left for left,right in merged)/(hi-lo)
    return dict(supported_fraction=float(coverage),observed_intervals_m=merged,
                inferred_gaps_m=gaps,max_gap_m=max((b-a for a,b in gaps),default=0.),
                max_location_shift_m=group['max_location_shift_m'],
                opening_classification='unresolved; gaps may be occlusion or openings')


def propose_supported_cells(segments, camera_path, minimum_support=.60, max_gap_m=1.20,
                            *, occupied_cells=()):
    """Infer only cells bounded on all four sides by observed wall groups.

    This is a rectangular fallback, not a complete-property reconstruction.
    Missing spans are explicitly inferred, and never emitted as detected doors.
    Existing observed cells are immutable exclusions. Only camera samples not
    already covered by them can support an additional hypothesis.
    """
    xgroups,zgroups=_groups(segments,0),_groups(segments,1)
    if len(xgroups)>20 or len(zgroups)>20:
        return [],[]  # Bound runtime; complex scenes need a different room solver.
    cameras=geometry_points(np.asarray(camera_path,float).reshape(-1,2))
    available=np.ones(len(cameras),dtype=bool)
    for cell in occupied_cells:
        available &= ~covers(cell.buffer(.10),cameras)
    cameras=cameras[available]
    if len(cameras)<2:
        return [],[]
    edge_cache={}
    def edge(group,lo,hi):
        key=(id(group),lo,hi)
        if key not in edge_cache:
            edge_cache[key]=_edge_evidence(group,lo,hi)
        return edge_cache[key]
    candidates=[]
    for left,right in combinations(xgroups,2):
        x0,x1=left['location'],right['location']
        if not .8<=x1-x0<=15: continue
        for bottom,top in combinations(zgroups,2):
            z0,z1=bottom['location'],top['location']
            if not .8<=z1-z0<=15: continue
            # Match polygon edge order: bottom, right, top, left.
            evidence=[edge(bottom,x0,x1),edge(right,z0,z1),
                      edge(top,x0,x1),edge(left,z0,z1)]
            if any(e['supported_fraction']<minimum_support or e['max_gap_m']>max_gap_m for e in evidence):
                continue
            polygon=Polygon([(x0,z0),(x1,z0),(x1,z1),(x0,z1)])
            if any(polygon.intersection(cell).area>.01 for cell in occupied_cells):
                continue
            # Evaluate the same rounded 5 cm buffer as before, once per cell.
            occupancy=int(np.count_nonzero(covers(polygon.buffer(.05),cameras)))
            if occupancy<2: continue
            candidates.append((occupancy,float(np.mean([e['supported_fraction'] for e in evidence])),
                               polygon,evidence))
    selected=[]; evidence=[]
    for occupancy,support,polygon,edges in sorted(candidates,key=lambda c:(c[0],c[1]),reverse=True):
        if any(polygon.intersection(other).area>.01 for other in selected): continue
        selected.append(polygon)
        evidence.append(dict(method='supported rectangular cell; partial inference',
                             camera_samples_inside=int(occupancy),mean_supported_fraction=support,
                             edges=edges,accuracy_validated=False))
    return selected,evidence
