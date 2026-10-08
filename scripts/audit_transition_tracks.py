"""Read-only track/safety audit of the frozen 24-view matcher experiments.

Diagnostics never remove matches, alter guards, register views or merge models.
Conflicting transitive tracks flag incompatibility, not which match is incorrect.
"""
from __future__ import annotations

import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from PIL import Image, ImageDraw
from floorplan.provenance import sha256
from scripts.compare_transition_matchers import compare
from scripts.experimental_video_bridge import shortest_bridge

MAX_ID = 2147483647
ENDPOINTS = ('frame_00024.png', 'frame_00027.png')


def track_components(edges):
    """Union feature identities without suppressing incompatible observations."""
    parent = {}

    def root(node):
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for a, b, matches in edges:
        for ia, ib in matches:
            x, y = root((a, int(ia))), root((b, int(ib)))
            if x != y:
                parent[y] = x
    tracks = {}
    for node in parent:
        tracks.setdefault(root(node), []).append(node)
    return list(tracks.values())


def track_spread(nodes, coordinates):
    """Largest within-image axis range, a lower bound on pixel separation."""
    by_image = {}
    for name, index in nodes:
        by_image.setdefault(name, []).append(coordinates[name][index])
    return max((float(np.ptp(points, axis=0).max()) for points in by_image.values() if len(points)>1), default=0.)


def track_audit(edges, endpoints=ENDPOINTS, coordinates=None):
    """Retain conflicts; optionally distinguish separated locations from duplicates."""
    tracks = track_components(edges)
    rows = []
    for nodes in tracks:
        counts = Counter(n[0] for n in nodes)
        rows.append(dict(observations=len(nodes), views=len(counts),
                         conflicting=any(n > 1 for n in counts.values()),
                         both_endpoints=set(endpoints).issubset(counts)))
    result = dict(tracks=len(rows), observations=sum(len(n) for n in tracks),
                conflicting_tracks=sum(r['conflicting'] for r in rows),
                observations_in_conflicting_tracks=sum(r['observations'] for r in rows if r['conflicting']),
                clean_tracks_at_least_three_views=sum(not r['conflicting'] and r['views'] >= 3 for r in rows),
                endpoint_spanning_tracks=sum(r['both_endpoints'] for r in rows),
                clean_endpoint_spanning_tracks=sum(r['both_endpoints'] and not r['conflicting'] for r in rows),
                maximum_views=max((r['views'] for r in rows), default=0))
    if coordinates is not None:
        spreads = [track_spread(nodes, coordinates) for nodes in tracks]
        result.update(conflicting_tracks_separated_over_4px=sum(s>4 for s in spreads),
                      conflicting_tracks_separated_over_12px=sum(s>12 for s in spreads),
                      maximum_same_image_separation_lower_bound_px=max(spreads, default=0.),
                      endpoint_track_conflict_details=[dict(views=r['views'], observations=r['observations'],
                          conflicting=r['conflicting'], same_image_separation_lower_bound_px=s)
                          for r,s in zip(rows,spreads) if r['both_endpoints']])
    return result


def triangle_audit(edges):
    """Count exact keypoint-ID cycle agreement where all three pair edges exist."""
    maps = {}
    for a, b, matches in edges:
        if len(set(map(int, matches[:, 0]))) != len(matches) or len(set(map(int, matches[:, 1]))) != len(matches):
            raise ValueError('Verified pair is not one-to-one')
        maps[a, b] = dict((int(x), int(y)) for x, y in matches)
        maps[b, a] = dict((int(y), int(x)) for x, y in matches)
    rows = []
    for a, b, c in itertools.combinations(sorted({n for pair in maps for n in pair}), 3):
        if not all(p in maps for p in ((a, b), (b, c), (a, c))):
            continue
        ab, bc, ac = maps[a, b], maps[b, c], maps[a, c]
        composed = {x: bc[y] for x, y in ab.items() if y in bc}
        tested = set(composed) & set(ac)
        agrees = sum(composed[x] == ac[x] for x in tested)
        rows.append(dict(images=[a, b, c], composed=len(composed),
                         directly_testable=len(tested), agreeing=agrees, conflicting=len(tested)-agrees))
    return dict(triangles=len(rows), directly_testable=sum(r['directly_testable'] for r in rows),
                agreeing=sum(r['agreeing'] for r in rows), conflicting=sum(r['conflicting'] for r in rows),
                triangles_with_conflicts=sum(r['conflicting'] > 0 for r in rows), rows=rows)


def spatial_support(points, size):
    width, height = size
    points = np.asarray(points, dtype=np.float32)
    if not np.isfinite(points).all() or (points < 0).any() or (points[:, 0] >= width).any() or (points[:, 1] >= height).any():
        raise ValueError('Invalid verified pixel coordinates')
    cells = np.minimum((points / [width, height] * 8).astype(int), 7)
    hull = float(cv2.contourArea(cv2.convexHull(points))) if len(points) >= 3 else 0.
    return dict(hull_image_fraction=hull/(width*height), occupied_8x8_cells=len(set(map(tuple, cells))))


def draw_pair(trial, a, b, pa, pb, target):
    scale = .4
    ims = [Image.open(trial/'images'/n).convert('RGB') for n in (a, b)]
    ims = [im.resize((int(im.width*scale), int(im.height*scale))) for im in ims]
    canvas = Image.new('RGB', (sum(im.width for im in ims), ims[0].height+35), 'white')
    canvas.paste(ims[0], (0, 35)); canvas.paste(ims[1], (ims[0].width, 35))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 8), f'{a} -> {b}: {len(pa)} verified inliers (display only)', fill='black')
    selected = np.unique(np.linspace(0, len(pa)-1, min(80, len(pa))).astype(int))
    for index in selected:
        x, y = pa[index]*scale; xx, yy = pb[index]*scale
        color = (int((index*73)%180+60), int((index*97)%180+60), int((index*131)%180+60))
        draw.line((x, y+35, xx+ims[0].width, yy+35), fill=color, width=1)
        for p, q in ((x, y+35), (xx+ims[0].width, yy+35)):
            draw.ellipse((p-3, q-3, p+3, q+3), outline=color, width=2)
            if len(pa)<=30: draw.text((p+3, q+3), str(index), fill=color)
    canvas.save(target)


def audit_trial(trial, out):
    import pycolmap
    record = json.loads((trial/'experiment.json').read_text())
    names = [r['image'] for r in record['temporal_window']]
    edges = []; pair_rows = []; coordinates = {}; sizes = {}
    candidates = {frozenset((r['image_a'], r['image_b'])): r['candidate_matches'] for r in record['graph']['pairs']}
    with sqlite3.connect((trial/'features.db').as_uri()+'?mode=ro', uri=True) as db:
        ids = dict(db.execute('SELECT image_id,name FROM images'))
        for i, name in ids.items():
            n, c, blob = db.execute('SELECT rows,cols,data FROM keypoints WHERE image_id=?', (i,)).fetchone()
            coordinates[name] = np.frombuffer(blob, np.float32).reshape(n, c)[:, :2]
            with Image.open(trial/'images'/name) as im: sizes[name] = im.size
        for pid, count, config, blob in db.execute('SELECT pair_id,rows,config,data FROM two_view_geometries WHERE rows>0 ORDER BY pair_id'):
            a, b = ids[pid//MAX_ID], ids[pid%MAX_ID]
            matches = np.frombuffer(blob, np.uint32).reshape(count, 2)
            edges.append((a, b, matches))
            pa, pb = coordinates[a][matches[:, 0]], coordinates[b][matches[:, 1]]
            pair_rows.append(dict(image_a=a, image_b=b, inliers=count, config=config,
                                  candidates=candidates[frozenset((a, b))],
                                  spatial_a=spatial_support(pa, sizes[a]), spatial_b=spatial_support(pb, sizes[b])))
    expected = {(frozenset((p['image_a'], p['image_b'])), p['verified_inliers'], p['geometry_config'])
                for p in record['graph']['pairs'] if p['verified_inliers']}
    if expected != {(frozenset((a, b)), len(m), row['config']) for (a, b, m), row in zip(edges, pair_rows)}:
        raise ValueError('Frozen pair report and database disagree')
    path = shortest_bridge(names, [(a, b) for a, b, _ in edges], {ENDPOINTS[0]}, {ENDPOINTS[1]})
    path_rows = []
    tracks = track_components(edges)
    conflicts = {node:track_spread(nodes, coordinates) for nodes in tracks
                 if len({n[0] for n in nodes}) != len(nodes) for node in nodes}
    for a, b in zip(path[:-1], path[1:]):
        index = next(i for i, (x, y, _) in enumerate(edges) if {x, y} == {a, b})
        x, y, matches = edges[index]
        row = dict(pair_rows[index]); row['disconnects_endpoints_if_removed'] = not bool(shortest_bridge(
            names, [(x, y) for i, (x, y, _) in enumerate(edges) if i != index], {ENDPOINTS[0]}, {ENDPOINTS[1]}))
        row['inliers_in_conflicting_tracks'] = sum((x,int(i)) in conflicts for i in matches[:,0])
        row['inliers_in_tracks_with_separated_conflicts_over_12px'] = sum(conflicts.get((x,int(i)),0)>12 for i in matches[:,0])
        row['indexed_pixel_matches'] = [dict(index=i, pixel_a=pa.tolist(), pixel_b=pb.tolist())
            for i,(pa,pb) in enumerate(zip(coordinates[x][matches[:,0]],coordinates[y][matches[:,1]]))] if len(matches)<=30 else []
        image = out/f'{record["mode"]}_{a}_{b}.jpg'
        draw_pair(trial, x, y, coordinates[x][matches[:, 0]], coordinates[y][matches[:, 1]], image)
        row['visualization'] = image.name; path_rows.append(row)
    models = []
    for saved in record['models']:
        model = pycolmap.Reconstruction(trial/'sparse'/str(saved['model_id']))
        lengths = [p.track.length() for p in model.points3D.values()]
        models.append(dict(images=saved['image_names'], points=len(lengths),
                           track_length_histogram=dict(Counter(lengths)),
                           mean_reprojection_px=model.compute_mean_reprojection_error(),
                           both_endpoints_registered=set(ENDPOINTS).issubset(saved['image_names'])))
    return dict(mode=record['mode'], pairs=len(edges), endpoint_path=path, path_pairs=path_rows,
                tracks=track_audit(edges, coordinates=coordinates), cycles=triangle_audit(edges), models=models, all_pairs=pair_rows)


def audit(root, out):
    root, out = root.resolve(), out.resolve()
    old = json.loads((root/'comparison/comparison.json').read_text())
    summary = json.loads(Path('docs/results/phase3_transition_matcher_summary.json').read_text())
    for p, h in summary['artifacts'].items():
        if sha256(p) != h: raise ValueError('Previously recorded evidence changed')
    folders = [root/n for n in ('sift4', 'sift5', 'lightglue_thread4_1', 'lightglue_thread4_2')]
    frozen = {str(p): sha256(p) for folder in folders for p in folder.rglob('*') if p.is_file()}
    production = {str(p): sha256(p) for p in Path('floorplan').glob('*.py')}
    for folder, native in ((folders[0], 'sift_initialization'), (folders[2], 'learned_initialization')):
        prior = json.loads((root/native/'audit.json').read_text())
        if sha256(folder/'features.db') != prior['input_database_sha256']:
            raise ValueError('Database changed since native guard audit')
    out.mkdir(parents=True, exist_ok=False)
    comparison = compare(*folders, out/'reverified_comparison')
    if comparison['repeats'] != old['repeats']:
        raise ValueError('Repeatability evidence differs from retained baseline')
    runs = [audit_trial(folder, out) for folder in (folders[0], folders[2])]
    groups = json.loads(Path('demo/phase3_video_bridge/dense_trial1/experiment.json').read_text())['diagnostics']['target_groups']
    retained = set(json.loads((folders[0]/'experiment.json').read_text())['image_sha256'])
    if frozen != {p: sha256(p) for p in frozen} or production != {p: sha256(p) for p in production}:
        raise ValueError('Audit changed retained inputs or production code')
    result = dict(experiment='retained_24_view_track_safety_audit', runs=runs,
                  original_target_groups=groups, retained_target_members=[sorted(set(g)&retained) for g in groups],
                  artifact_sha256=frozen, production_code_sha256=production, script_sha256=sha256(__file__),
                  repeats_reverified=True, frozen_inputs_unchanged=True, production_unchanged=True,
                  production_adoption=False, physical_accuracy_validated=False,
                  limitations=['Cycle/track consistency is diagnostic, not a new acceptance gate',
                               'A duplicate image in a transitive track proves incompatible correspondence identities, not which edge is wrong',
                               'No independent match labels, physical poses or dimensional truth are available',
                               'Only one original member per target group is retained; full groups have not been jointly mapped'])
    (out/'audit.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps([dict(mode=r['mode'], tracks=r['tracks'], cycles={k:v for k,v in r['cycles'].items() if k!='rows'},
                           path_pairs=r['path_pairs'], models=r['models']) for r in runs], indent=2))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path('demo/phase3_transition_matchers'))
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); audit(a.root, a.out)
