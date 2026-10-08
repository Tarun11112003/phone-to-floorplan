"""Trace an aligned exterior strip from sensor pixels to frozen wall proposals.

Diagnostic only. Bounds select observations for inspection, never a wall prior.
"""
from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import cv2
import numpy as np

import floorplan.layout as layout
from floorplan.provenance import sha256
from floorplan.rgbd import _backproject
from scripts.diagnostics.audit_floor_boundary import fit_omitted_seed


def strip_mask(aligned, floor, x=-2.73, half_width=.12, z_bounds=(4., 5.9)):
    return ((np.abs(aligned[:, 0]-x)<half_width)
            & (aligned[:, 2]>=z_bounds[0]) & (aligned[:, 2]<=z_bounds[1])
            & (aligned[:, 1]<floor-.25) & (aligned[:, 1]>floor-3.))


def seed_histogram(points, basis, floor, axis, target):
    q=points@basis
    band=points[(q[:, 1]<floor-.25)&(q[:, 1]>floor-3.)]
    values=band@basis[:, axis]
    edges=np.arange(np.floor(values.min()/.025)*.025-.05, values.max()+.075, .025)
    counts,_=np.histogram(values, edges)
    peaks=[i for i in range(1, len(counts)-1)
           if counts[i]>=250 and counts[i]>=counts[i-1] and counts[i]>=counts[i+1]]
    ranked=sorted(peaks, key=lambda i:(-int(counts[i]), i))[:48]
    selected=int(np.argmin(np.abs((edges[:-1]+edges[1:])/2-target)))
    rows=[dict(location_m=float((edges[i]+edges[i+1])/2), points=int(counts[i]),
               eligible_seed=i in peaks, rank=ranked.index(i)+1 if i in ranked else None)
          for i in range(max(0, selected-4), min(len(counts), selected+5))]
    return dict(eligible_modes=len(peaks), target_bins=rows), band


def trace(run, source, out):
    run,source,out=map(lambda p:Path(p).resolve(), (run, source, out))
    out.mkdir(parents=True, exist_ok=False)
    read=lambda n:json.loads((run/n).read_text(encoding='utf-8'))
    ledger=read('run.json');meta=read('artifacts/layout_evidence.json')
    sequence=read('normalized_sequence.json');summary=read('artifacts/rgbd_summary.json')
    artifact_names=['artifacts/'+n for n in
                    ('cloud.npz', 'trajectory.json', 'rgbd_summary.json', 'layout_evidence.json')]
    if any(ledger['geometry_artifact_sha256'][n]!=sha256(run/n) for n in artifact_names):
        raise ValueError('Frozen artifacts changed')
    code={p.name:sha256(p) for p in Path(layout.__file__).parent.glob('*.py')}
    if any(code.get(n)!=h for n,h in ledger['code_sha256'].items()):
        raise ValueError('Trace requires the frozen reconstruction producer')
    if any(sha256(Path(n))!=h for n,h in ledger['inputs'].items()):
        raise ValueError('Sensor input hashes differ from the baseline')
    trajectory={p['frame_id']:np.asarray(p['camera_to_first'])
                for p in read('artifacts/trajectory.json')}
    basis=np.asarray(meta['basis_columns_in_input']);floor=meta['wall_sampling_slab_bound_m']
    clouds=[];weights=[];colors=[];rows=[];source_hashes={}
    for frame in sequence['frames']:
        fid=frame['id'];pose=trajectory[fid]
        kdata=frame.get('intrinsics', sequence['intrinsics'])
        k=np.array([[kdata['fx'],0,kdata['cx']], [0,kdata['fy'],kdata['cy']], [0,0,1]])
        depth_path=run/Path(frame['depth']);confidence_path=run/Path(frame['confidence'])
        raw=cv2.imread(str(depth_path), cv2.IMREAD_UNCHANGED)
        confidence=cv2.imread(str(confidence_path), cv2.IMREAD_UNCHANGED)
        original_depth=source/'depth'/f'{fid:06d}.png'
        original_confidence=source/'confidence'/f'{fid:06d}.png'
        identical=(sha256(original_depth)==sha256(depth_path)
                   and sha256(original_confidence)==sha256(confidence_path))
        if not identical:raise ValueError(f'Sensor payload extraction changed frame {fid}')
        source_hashes[str(original_depth)]=sha256(original_depth)
        source_hashes[str(original_confidence)]=sha256(original_confidence)
        depth=raw.astype(float)/sequence['depth_scale']
        yy,xx=np.indices(depth.shape)
        positive=np.isfinite(depth)&(depth>0)
        pixels=np.column_stack([xx[positive], yy[positive]])
        xyz=_backproject(pixels, depth[positive], k)
        world=xyz@pose[:3,:3].T+pose[:3,3]
        region=strip_mask(world@basis, floor)
        valid_range=(depth[positive]>=.2)&(depth[positive]<=sequence.get('depth_max_m',8.))
        confident=confidence[positive]>=sequence.get('minimum_confidence',1)
        subsampled=(pixels[:,0]%8==0)&(pixels[:,1]%8==0)
        ids=region&valid_range&confident
        raw_pose=np.asarray(frame['camera_to_world'])
        raw_region=strip_mask((xyz@raw_pose[:3,:3].T+raw_pose[:3,3])@basis,floor)
        row=dict(frame_id=fid,timestamp_s=frame.get('timestamp_s'),
                 positive_depth_strip_pixels=int(region.sum()),
                 range_valid_strip_pixels=int((region&valid_range).sum()),
                 confident_strip_pixels=int(ids.sum()),
                 confidence_0_strip_pixels=int((region&valid_range&(confidence[positive]==0)).sum()),
                 confidence_1_strip_pixels=int((region&valid_range&(confidence[positive]==1)).sum()),
                 confidence_2_strip_pixels=int((region&valid_range&(confidence[positive]==2)).sum()),
                 stride8_strip_points=int((ids&subsampled).sum()),
                 raw_pose_confident_strip_pixels=int((raw_region&valid_range&confident).sum()),
                 sensor_payload_identical=identical)
        rows.append(row)
        sampled=valid_range&confident&subsampled
        clouds.append(world[sampled])
        z=depth[positive][sampled]
        weights.append((confidence[positive][sampled].astype(float)+1)/np.maximum(z,.5)**2)
        rgb=cv2.imread(str(run/Path(frame['rgb'])))
        colors.append(rgb[pixels[sampled,1], pixels[sampled,0], ::-1])
    sampled_cloud=np.concatenate(clouds)
    replay,_,_=layout.weighted_voxels(sampled_cloud, np.concatenate(colors), np.concatenate(weights))
    cloud=np.load(run/'artifacts/cloud.npz')['points']
    if replay.shape!=cloud.shape:raise ValueError('Replayed fusion changed cloud dimensions')
    delta=float(np.max(np.abs(replay-cloud)))
    if not np.array_equal(replay, cloud):
        raise ValueError(f'Pixel-to-fusion replay is not exact: max difference {delta}')
    aligned=cloud@basis;region=strip_mask(aligned, floor)
    planes=summary['planes']+meta.get('wall_seed_planes',[])
    visits=[]
    function=layout._projection_wall_proposals
    lines,start=inspect.getsourcelines(function)
    seed_line=start+next(i for i,line in enumerate(lines) if 'location=float((edges[index]' in line)
    def tracer(frame,event,arg):
        if frame.f_code is function.__code__ and event=='line' and frame.f_lineno==seed_line:
            local=frame.f_locals
            visits.append(dict(axis=int(local['axis']),accepted_limit=int(local['accepted_limit']),
                               seed_location_m=float((local['edges'][local['index']]+local['edges'][local['index']+1])/2)))
        return tracer
    previous=sys.gettrace();sys.settrace(tracer)
    try:proposals=layout._supported_wall_proposals(cloud,planes,basis,floor)
    finally:sys.settrace(previous)
    if json.loads(json.dumps(proposals))!=meta['wall_plane_proposals']:
        raise ValueError('Proposal replay differs from frozen geometry')
    initial=layout._projection_wall_proposals(cloud,planes,basis,floor)
    remaining=np.ones(len(cloud), bool);removals=[]
    for i,p in enumerate(planes+initial):
        hit=np.abs(cloud@np.asarray(p['normal'])+p['offset'])<.035
        vertical=float(abs(np.asarray(p['normal'])@basis[:,1]))
        removals.append(dict(plane_id=i,proposal_source=p.get('proposal_source','global plane'),
                             vertical_dot=vertical,strip_hits=int((hit&region).sum()),
                             first_removed_strip_points=int((remaining&hit&region).sum()),
                             centroid_aligned_m=(np.asarray(p['centroid'])@basis).tolist()))
        remaining &=~hit
    target=-2.7375
    original_bins,original_band=seed_histogram(cloud,basis,floor,0,target)
    residual_bins,residual_band=seed_histogram(cloud[remaining],basis,floor,0,target)
    fits={label:fit_omitted_seed(band,basis[:,0],basis[:,1],target,planes+initial)
          for label,band in [('original',original_band),('residual',residual_band)]}
    # Attribute fused voxels back to frames using the exact production grouping.
    # Frame contribution counts overlap; they are not independent voxel totals.
    _,voxel_ids=np.unique(np.floor(sampled_cloud/.02).astype(np.int64),axis=0,return_inverse=True)
    fit=fits['residual']
    target_band=(remaining & (aligned[:,1]<floor-.25) & (aligned[:,1]>floor-3.)
                 & (np.abs(cloud@np.asarray(fit['normal'])+fit['offset'])<.025))
    offset=0
    for row,frame_cloud in zip(rows,clouds):
        ids=np.unique(voxel_ids[offset:offset+len(frame_cloud)]);offset+=len(frame_cloud)
        row['fused_strip_voxels_contributed']=int(region[ids].sum())
        row['residual_strip_voxels_contributed']=int((region[ids]&remaining[ids]).sum())
        row['residual_target_plane_band_voxels_contributed']=int(target_band[ids].sum())
    horizontal_removed=sum(p['first_removed_strip_points'] for p in removals if p['vertical_dot']>.97)
    totals={k:sum(r[k] for r in rows) for k in rows[0] if k.endswith('_pixels') or k.endswith('_points')}
    present=any(abs((np.asarray(p['centroid'])@basis)[0]+2.73)<.04
                and 4.<(np.asarray(p['centroid'])@basis)[2]<5.9 for p in proposals)
    result=dict(experiment='exterior_strip_sensor_to_seed_trace',run=str(run),source=str(source),
                strip_query=dict(x_m=-2.73,half_width_m=.12,z_bounds_m=[4.,5.9],
                                 floor_sampling_bound_m=floor,query_is_not_ground_truth=True),
                input_sha256={n:sha256(run/n) for n in ['run.json','plan.json','normalized_sequence.json']+artifact_names},
                raw_sensor_sha256=source_hashes,script_sha256=sha256(Path(__file__)),
                code_sha256=code,reconstruction_unchanged=code=={p.name:sha256(p) for p in Path(layout.__file__).parent.glob('*.py')},
                frames=len(rows),frames_with_confident_strip_pixels=sum(r['confident_strip_pixels']>0 for r in rows),
                frames_with_stride8_strip_points=sum(r['stride8_strip_points']>0 for r in rows),
                frames_contributing_residual_target_plane_band=sum(r['residual_target_plane_band_voxels_contributed']>0 for r in rows),
                residual_target_final_plane_band_points=int(target_band.sum()),
                all_sensor_payloads_identical=all(r['sensor_payload_identical'] for r in rows),
                totals=totals,per_frame=rows,fusion_replay_exact=True,fusion_max_difference_m=delta,
                fused_strip_points=int(region.sum()),residual_strip_points=int((remaining&region).sum()),
                horizontal_first_removed_strip_points=horizontal_removed,plane_removals=removals,
                original_seed_histogram=original_bins,residual_seed_histogram=residual_bins,
                diagnostic_target_fits=fits,actual_seed_visits=visits,
                audited_surface_proposal_present=present,
                camera_coverage_fraction=meta['camera_center_coverage_fraction'],
                root_cause='Original quota and residual-bin dilution omit sufficient consensus; bounded original-seed retry recovers the audited proposal' if present else 'Original accepted-plane quota skips a valid seed; residual masking lowers its histogram peak below the seed threshold while sufficient residual consensus remains',
                software_fixable_proposal_omission=True,whole_enclosure_evidence_available=False,
                accuracy_validated=False,limitations=[
                    'Depth/confidence and supplied poses are inference inputs, not independent measurement truth',
                    'Strip bounds and targeted diagnostic fit do not establish semantic wall identity',
                    'Counts before voxel fusion are repeated sensor observations, not independent samples',
                    'Per-frame voxel contributions overlap; final plane-band membership can differ from the last iterative fit consensus',
                    'This trace covers selected pipeline frames; it does not score all unsampled sensor frames',
                    'Recovering this plane does not prove adjoining surfaces close a room',
                    'Ceiling coverage and prior 0.703 m boundary change remain unvalidated'])
    (out/'trace.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(11,7))
    for key,label in [('confident_strip_pixels','Confident full-resolution pixels'),('stride8_strip_points','Stride-8 points')]:
        axes[0].plot([r['frame_id'] for r in rows],[r[key] for r in rows],label=label)
    axes[0].set(xlabel='Sensor frame ID',ylabel='Repeated observation count');axes[0].legend()
    for key,label in [(region&remaining,'Residual'),(region&~remaining,'Masked')]:
        axes[1].scatter(aligned[key,2], floor-aligned[key,1],s=3,label=label)
    axes[1].set(xlabel='Aligned z (m)',ylabel='Height above sampling bound (m)');axes[1].legend()
    fig.suptitle('Sensor-to-seed strip trace; no surveyed ground truth');fig.tight_layout()
    fig.savefig(out/'trace.png',dpi=140);plt.close(fig)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path);parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();result=trace(args.run,args.source,args.out)
    print(json.dumps({k:v for k,v in result.items() if k not in
                     ('per_frame','code_sha256','input_sha256','raw_sensor_sha256','actual_seed_visits','plane_removals')},indent=2))
