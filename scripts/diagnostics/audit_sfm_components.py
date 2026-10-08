"""Inspect frozen verified-pair connectivity and sparse models without remapping."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from floorplan.provenance import sha256


def connected_components(nodes, pairs):
    neighbors = {node: set() for node in nodes}
    for a, b in pairs:
        if a not in neighbors or b not in neighbors:
            raise ValueError('Pair references an unknown image')
        neighbors[a].add(b); neighbors[b].add(a)
    unseen = set(nodes); result = []
    while unseen:
        seed = min(unseen); pending = [seed]; component = set()
        while pending:
            node = pending.pop()
            if node in component:
                continue
            component.add(node); pending.extend(neighbors[node] - component)
        unseen -= component; result.append(sorted(component))
    return sorted(result, key=lambda row: (-len(row), row))


def audit(sfm, out):
    import pycolmap
    sfm, out = Path(sfm).resolve(), Path(out).resolve()
    summary = json.loads((sfm/'sfm_summary.json').read_text(encoding='utf-8'))
    database = sfm/'features.db'
    model_paths = sorted((sfm/'sparse').glob('*/images.bin'))
    inputs = [database, sfm/'sfm_summary.json']
    inputs += [p for model in model_paths for p in model.parent.iterdir() if p.is_file()]
    hashes = {str(p): sha256(p) for p in inputs}
    with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as conn:
        names = dict(conn.execute('SELECT image_id, name FROM images'))
        rows = conn.execute('SELECT pair_id, rows, config FROM two_view_geometries WHERE rows > 0').fetchall()
    pairs = [(pair_id//2147483647, pair_id%2147483647) for pair_id, _, _ in rows]
    components = connected_components(names, pairs)
    models = []; union = set()
    for path in model_paths:
        model = pycolmap.Reconstruction(path.parent)
        registered = sorted(image.name for image in model.images.values() if image.has_pose)
        union.update(registered)
        models.append(dict(directory=str(path.parent), registered_images=len(registered), image_names=registered,
                           sparse_points=model.num_points3D(), mean_reprojection_error_px=model.compute_mean_reprojection_error()))
    best_names = max(models, key=lambda row: row['registered_images'])['image_names'] if models else []
    result = dict(experiment='frozen_sfm_connectivity_and_models', sfm_directory=str(sfm),
                  input_sha256=hashes, script_sha256=sha256(Path(__file__)), pycolmap_version=pycolmap.__version__,
                  input_images=len(names), verified_pairs=len(pairs),
                  pair_components=[dict(images=len(c), names=[names[n] for n in c]) for c in components],
                  calibrated_pair_count=sum(config == 2 for _, _, config in rows),
                  models=models, selected_model_registered_images=summary['registered_images'],
                  union_registered_images=len(union),
                  verified_graph_images_not_in_selected_model=sorted({names[n] for c in components if len(c)>1 for n in c} - set(best_names)),
                  geometry_changed=False, accuracy_validated=False,
                  limitations=['Verified-pair connectivity does not imply triangulable parallax or reliable camera poses',
                               'Disconnected model union is a diagnostic count, not a common-coordinate property reconstruction',
                               'Mean reprojection error is internal consistency, not metric accuracy'])
    if hashes != {str(p): sha256(p) for p in inputs}:
        raise ValueError('Frozen SfM files changed during audit')
    out.mkdir(parents=True, exist_ok=False)
    (out/'audit.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sfm', type=Path); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); result = audit(args.sfm, args.out)
    print(json.dumps({key:value for key,value in result.items() if key != 'input_sha256'}, indent=2))
