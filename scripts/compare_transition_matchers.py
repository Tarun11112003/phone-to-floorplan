"""Read-only comparison of retained SIFT and repeated pinned LightGlue trials."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.provenance import sha256
from scripts.experimental_video_bridge import baseline_digest


def compare(sift, sift_repeat, learned, learned_repeat, out):
    import pycolmap
    folders=[Path(p).resolve() for p in (sift,sift_repeat,learned,learned_repeat)]
    records=[json.loads((p/'experiment.json').read_text()) for p in folders]
    if [r['mode'] for r in records]!=['sift','sift','lightglue','lightglue']:
        raise ValueError('Expected baseline/repeat followed by learned/repeat')
    for r in records:
        for field in ('image_sha256','input_sha256','options','production_code_sha256','temporal_window','script_sha256'):
            if r[field]!=records[0][field]: raise ValueError(f'{field} differs across trials')
        if any(sha256(p)!=h for p,h in r['input_sha256'].items()):
            raise ValueError('Frozen input changed after inference')
    results=[]; repeats=[]
    for path,r in zip(folders,records):
        graph=r['graph'];pairs=graph['pairs']
        adjacent=[]
        for a,b in zip(r['temporal_window'][:-1],r['temporal_window'][1:]):
            pair=next(p for p in pairs if {p['image_a'],p['image_b']}=={a['image'],b['image']})
            adjacent.append(dict(**pair,source_a_s=a['source_timestamp_s'],source_b_s=b['source_timestamp_s']))
        candidates=np.array([p['candidate_matches'] for p in pairs])
        residuals=[p for p in graph['sampson_residuals'] if p['available']]
        with sqlite3.connect((path/'features.db').as_uri()+'?mode=ro',uri=True) as conn:
            initial_cameras={str(row[0]):list(row[:4])+[row[4].hex(),row[5]] for row in conn.execute('SELECT * FROM cameras')}
            assert conn.execute('SELECT COUNT(*) FROM pose_priors').fetchone()[0]==0
        if results and initial_cameras!=results[0]['initial_cameras']:
            raise ValueError('Camera priors differ across matchers')
        results.append(dict(mode=r['mode'],directory=str(path),verified_pairs=graph['verified_pairs'],
                            component_sizes=[len(c) for c in graph['components']],isolated_views=graph['isolated_views'],
                            target_connected=graph['target_connected'],endpoint_path=graph['verified_endpoint_path'],
                            joint_endpoint_model=r['joint_endpoint_model'],models=r['models'],
                            maximum_registered_images=r['maximum_registered_images'],
                            geometry_configurations=r['matching_diagnostics']['verified_geometry_configurations'],
                            candidates=dict(minimum=int(candidates.min()),median=float(np.median(candidates)),
                                            maximum=int(candidates.max()),below_15=int((candidates<15).sum()),
                                            total=int(candidates.sum()),pairs=len(pairs)),
                            adjacent_pairs=adjacent,sampson_pairs_available=len(residuals),
                            maximum_sampson_px=max((p['max_px'] for p in residuals),default=None),
                            runtime_s=r['runtime_s'],initial_cameras=initial_cameras))
    for first,repeat,r1,r2 in [(folders[0],folders[1],records[0],records[1]),(folders[2],folders[3],records[2],records[3])]:
        tables1,tables2=map(lambda p:baseline_digest(p/'features.db'),(first,repeat))
        table_exact={table:tables1[table]==tables2[table] for table in tables1}
        repeated_models=[]
        for m1 in r1['models']:
            m2=next((m for m in r2['models'] if m['image_names']==m1['image_names']),None)
            row=dict(images=m1['image_names'],repeat_model_found=m2 is not None)
            if m2:
                p1,p2=(folder/'sparse'/str(m['model_id']) for folder,m in ((first,m1),(repeat,m2)))
                hash1={p.name:sha256(p) for p in p1.glob('*.bin')};hash2={p.name:sha256(p) for p in p2.glob('*.bin')}
                if hash1!=m1['binary_sha256'] or hash2!=m2['binary_sha256']:
                    raise ValueError('Saved model changed after inference')
                model1,model2=map(pycolmap.Reconstruction,(p1,p2))
                c1={i.name:i.projection_center() for i in model1.images.values() if i.has_pose}
                c2={i.name:i.projection_center() for i in model2.images.values() if i.has_pose}
                row.update(binary_exact=hash1==hash2,
                           max_camera_center_difference=float(max(np.max(np.abs(c1[n]-c2[n])) for n in c1)))
            repeated_models.append(row)
        repeats.append(dict(mode=r1['mode'],database_tables_exact=table_exact,
                            matcher_identity_exact={k:v for k,v in r1['identity'].items() if k!='feature_sha256'}
                                =={k:v for k,v in r2['identity'].items() if k!='feature_sha256'},
                            feature_outputs_exact=r1['identity'].get('feature_sha256')==r2['identity'].get('feature_sha256'),
                            full_diagnostics_exact=r1['graph']==r2['graph'],
                            verified_components_exact=r1['graph']['components']==r2['graph']['components'],
                            verified_pair_rows_exact=[(p['image_a'],p['image_b'],p['verified_inliers'],p['geometry_config']) for p in r1['graph']['pairs']]
                                ==[(p['image_a'],p['image_b'],p['verified_inliers'],p['geometry_config']) for p in r2['graph']['pairs']],
                            actual_or_replayed_candidate_counts_exact=[p['candidate_matches'] for p in r1['graph']['pairs']]
                                ==[p['candidate_matches'] for p in r2['graph']['pairs']],models=repeated_models,
                            all_model_memberships_reproduced=len(r1['models'])==len(r2['models']) and all(m['repeat_model_found'] for m in repeated_models)))
    baseline,candidate=results[0],results[2]
    result=dict(experiment='same_24_rgb_matcher_comparison',runs=results,repeats=repeats,
                input_sha256=records[0]['input_sha256'],image_sha256=records[0]['image_sha256'],
                report_sha256={str(p/'experiment.json'):sha256(p/'experiment.json') for p in folders},
                verified_pair_delta=candidate['verified_pairs']-baseline['verified_pairs'],
                endpoint_connection_improved=candidate['target_connected'] and not baseline['target_connected'],
                joint_mapping_improved=candidate['joint_endpoint_model'] and not baseline['joint_endpoint_model'],
                matching_candidate_scope='LightGlue actual imported candidates; SIFT fresh diagnostic replay alongside unchanged historical verified pairs',
                downstream_guards_identical=True,physical_accuracy_validated=False,
                production_adoption_demonstrated=False,
                limitations=['More correspondences or graph connectivity alone are insufficient for adoption',
                             'Bounded matcher success still requires full-video validation before production integration',
                             'No physical truth or metric scale is inferred from reprojection/epipolar residuals'])
    target=Path(out).resolve();target.mkdir(parents=True,exist_ok=False)
    (target/'comparison.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(verified_pair_delta=result['verified_pair_delta'],
                         endpoint_connection_improved=result['endpoint_connection_improved'],
                         joint_mapping_improved=result['joint_mapping_improved'],repeats=repeats),indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('sift','sift-repeat','learned','learned-repeat','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();compare(a.sift,a.sift_repeat,a.learned,a.learned_repeat,a.out)
