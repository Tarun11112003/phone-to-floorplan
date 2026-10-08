"""Compare frozen bridge trials and trace native matcher support before RANSAC."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np

from floorplan.provenance import sha256
from scripts.experiments.experimental_video_bridge import baseline_digest


def compare(baseline, first, repeat, out):
    import pycolmap
    baseline,first,repeat,out=(Path(p).resolve() for p in (baseline,first,repeat,out))
    read=lambda folder,name:json.loads((folder/name).read_text(encoding='utf-8'))
    e1,e2=(read(p,'experiment.json') for p in (first,repeat))
    a1,a2=(read(p,'component_audit/audit.json') for p in (first,repeat))
    before=read(baseline,'audit.json')
    if e1['input_sha256']!=e2['input_sha256'] or e1['image_sha256']!=e2['image_sha256'] or e1['options']!=e2['options']:
        raise ValueError('Repeat trial does not hold inputs and options constant')
    input_files=[p/name for p in (first,repeat) for name in ('experiment.json','features.db','component_audit/audit.json')]+[baseline/'audit.json']
    hashes={str(p):sha256(p) for p in input_files}
    for audit in (before,a1,a2):
        if any(sha256(Path(p))!=h for p,h in audit['input_sha256'].items()):
            raise ValueError('Frozen audited database/model artifact changed')
    rows1,rows2=(baseline_digest(p/'features.db') for p in (first,repeat))
    semantic_exact={table:rows1[table]==rows2[table] for table in rows1}
    model_comparison=[]
    models2={tuple(m['image_names']):m for m in a2['models']}
    for model1 in a1['models']:
        key=tuple(model1['image_names']);model2=models2.get(key)
        record=dict(registered_images=model1['registered_images'],image_names=model1['image_names'],matching_model_found=model2 is not None)
        if model2:
            p1,p2=(Path(m['directory']) for m in (model1,model2))
            b1={p.name:sha256(p) for p in p1.glob('*.bin')};b2={p.name:sha256(p) for p in p2.glob('*.bin')}
            m1,m2=map(pycolmap.Reconstruction,(p1,p2))
            centers1={i.name:i.projection_center() for i in m1.images.values() if i.has_pose}
            centers2={i.name:i.projection_center() for i in m2.images.values() if i.has_pose}
            record.update(binary_model_files_exact=b1==b2,model1_sha256=b1,model2_sha256=b2,
                          maximum_camera_center_raw_coordinate_difference=float(max(np.max(np.abs(centers1[n]-centers2[n])) for n in centers1)),
                          sparse_points=[model1['sparse_points'],model2['sparse_points']],
                          mean_reprojection_error_px=[model1['mean_reprojection_error_px'],model2['mean_reprojection_error_px']])
        model_comparison.append(record)
    # SQLite stores empty matches for some sub-threshold pairs. Replay the pinned
    # native matcher without database writes to recover pre-verification counts.
    options=pycolmap.FeatureMatchingOptions(num_threads=1)
    if json.loads(json.dumps(options.todict(),default=str))!=e1['options']['matching']:
        raise ValueError('Native matcher options differ from the trial')
    matcher=pycolmap.FeatureMatcher.create(options=options,device=pycolmap.Device.cpu)
    window=[dict(image='frame_00024.png',source_timestamp_s=11.55),
            dict(image='frame_00025.png',source_timestamp_s=12.066667),
            dict(image='frame_00026.png',source_timestamp_s=12.566667),
            dict(image='frame_00027.png',source_timestamp_s=13.066667)]
    window += [row for row in e1['extraction'] if row['accepted']]
    window.sort(key=lambda row:(row['source_timestamp_s'],row['image']))
    trace=[];features={};stored={};verified={}
    with sqlite3.connect((first/'features.db').as_uri()+'?mode=ro',uri=True) as conn:
        ids=dict((name,identifier) for identifier,name in conn.execute('SELECT image_id,name FROM images'))
        for row in window:
            n,c,data=conn.execute('SELECT rows,cols,data FROM descriptors WHERE image_id=?',(ids[row['image']],)).fetchone()
            descriptors=pycolmap.FeatureDescriptors(type=pycolmap.FeatureExtractorType.SIFT,
                                                  data=np.frombuffer(data,dtype=np.uint8).reshape(n,c).copy())
            features[row['image']]=descriptors
        stored=dict(conn.execute('SELECT pair_id,rows FROM matches'))
        verified=dict((p,(n,c)) for p,n,c in conn.execute('SELECT pair_id,rows,config FROM two_view_geometries'))
    for row1,row2 in itertools.combinations(window,2):
        a,b=sorted((ids[row1['image']],ids[row2['image']]))
        pid=a*2147483647+b
        native=matcher.match(pycolmap.FeatureKeypoints(),features[row1['image']],
                             pycolmap.FeatureKeypoints(),features[row2['image']])
        trace.append(dict(image_a=row1['image'],image_b=row2['image'],
                          delta_source_time_s=row2['source_timestamp_s']-row1['source_timestamp_s'],
                          keypoints_a=len(features[row1['image']].data),keypoints_b=len(features[row2['image']].data),
                          native_preverification_matches=len(native),stored_matches=stored.get(pid),
                          verified_inliers=verified.get(pid,(0,None))[0],geometry_configuration=verified.get(pid,(0,None))[1],
                          fewer_than_existing_minimum_inliers=len(native)<e1['options']['verification']['min_num_inliers']))
    adjacent=[row for row in trace if (row['image_a'],row['image_b']) in
              [(a['image'],b['image']) for a,b in zip(window[:-1],window[1:])]]
    summary=dict(experiment='repeat_and_preverification_bridge_audit',input_sha256=hashes,script_sha256=sha256(Path(__file__)),
                 same_input_images_and_options=True,semantic_database_tables_exact=semantic_exact,
                 same_verified_pairs=e1['diagnostics']['added_view_verified_pairs']==e2['diagnostics']['added_view_verified_pairs'],
                 same_components=a1['pair_components']==a2['pair_components'],model_comparison=model_comparison,
                 baseline=dict(input_views=before['input_images'],verified_pairs=before['verified_pairs'],
                               component_sizes=[c['images'] for c in before['pair_components']],models=before['models']),
                 trial=dict(input_views=a1['input_images'],verified_pairs=a1['verified_pairs'],
                            component_sizes=[c['images'] for c in a1['pair_components']],models=a1['models'],
                            target_groups_connected=e1['diagnostics']['target_groups_connected'],
                            added_view_pairs=e1['diagnostics']['added_view_verified_pair_count']),
                 temporal_window=window,adjacent_pairs=adjacent,all_window_pairs=trace,
                 official_reference='https://github.com/colmap/colmap/blob/main/src/colmap/controllers/feature_matching_utils.cc',
                 production_policy_changed=False,accuracy_validated=False,
                 limitations=['Native matcher replay diagnoses correspondence support, not physical scene identity',
                              'Exact repeat of the same captures is not independent physical repeatability',
                              'Current upstream source is a conceptual reference; actual replay uses installed pycolmap 4.2.1'])
    if hashes!={str(p):sha256(p) for p in input_files}:
        raise ValueError('Frozen trials changed during comparison')
    out.mkdir(parents=True,exist_ok=False)
    (out/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:summary[key] for key in ('same_input_images_and_options','semantic_database_tables_exact','same_verified_pairs','same_components','adjacent_pairs')},indent=2))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','first','repeat','out'):
        parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();compare(args.baseline,args.first,args.repeat,args.out)
