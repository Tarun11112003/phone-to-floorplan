"""Evaluation-only furniture rejection on an audited supplied LiDAR cloud.

Uses sensor depth/poses for visibility: this is NOT an RGB-only video trial.
Model terms: https://github.com/NVlabs/SegFormer/blob/master/LICENSE (research/evaluation).
No semantic or dimension ground truth is fabricated. Production is unchanged.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.layout import extract_layout,export_layout
from floorplan.rgbd import _fit_planes
from floorplan.provenance import sha256

MODEL='nvidia/segformer-b0-finetuned-ade-512-512'
REVISION='489d5cd81a0b59fab9b7ea758d3548ebe99677da'
WEIGHTS_SHA256='6ae39addd01de6b1b8bde2cf677d43a5cd733424b8d186de3f95d1c51fee23f9'
FURNITURE={'bed','cabinet','table','chair','sofa','shelf','armchair','seat','desk',
    'wardrobe','chest of drawers','counter','refrigerator','cushion','pillow',
    'bookcase','coffee table','stove','washer','television receiver','computer',
    'swivel chair','microwave','oven','dishwasher'}


def removal_mask(furniture_votes,visible_views):
    votes,visible=np.asarray(furniture_votes),np.asarray(visible_views)
    return (votes>=2)&(votes>.6*visible)


def upright_turns(pose,world_down):
    """Rotate only model input; inverse-rotate labels into the sensor camera."""
    down=np.asarray(pose)[:3,:3].T@np.asarray(world_down,float)
    if np.linalg.norm(down[:2])<.2: return 0  # Looking along gravity: roll is ambiguous.
    if abs(down[0])>abs(down[1]): return -1 if down[0]>0 else 1
    return 2 if down[1]<0 else 0


def compare(run,out,max_views=18):
    import cv2
    import torch
    from PIL import Image
    from huggingface_hub import snapshot_download
    from transformers import SegformerImageProcessor,SegformerForSemanticSegmentation
    if not 2<=max_views<=60: raise ValueError('Bounded semantic trial requires 2-60 views')
    run,out=Path(run).resolve(),Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    cache=Path(__file__).resolve().parents[1]/'.tools/hf_cache/hub'
    snapshot=Path(snapshot_download(MODEL,revision=REVISION,cache_dir=str(cache),
        allow_patterns=['config.json','preprocessor_config.json','model.safetensors']))
    if sha256(snapshot/'model.safetensors')!=WEIGHTS_SHA256:
        raise ValueError('Semantic model weight checksum differs before deserialization')
    torch.set_num_threads(4);torch.manual_seed(7);torch.use_deterministic_algorithms(True)
    processor=SegformerImageProcessor.from_pretrained(snapshot,local_files_only=True)
    model=SegformerForSemanticSegmentation.from_pretrained(snapshot,local_files_only=True,use_safetensors=True).eval()
    names={int(i):name for i,name in model.config.id2label.items()}
    furniture_ids=[i for i,name in names.items() if name in FURNITURE]
    if not furniture_ids: raise ValueError('Pinned semantic model has no expected furniture labels')
    artifact=run/'artifacts'; points=np.load(artifact/'cloud.npz')['points'].astype(float)
    planes=json.loads((artifact/'rgbd_summary.json').read_text())['planes']
    sequence=json.loads((run/'normalized_sequence.json').read_text())
    trajectory=json.loads((artifact/'trajectory.json').read_text())
    matrices={str(p['frame_id']):np.asarray(p['camera_to_first']) for p in trajectory}
    world_down=json.loads((run/'run.json').read_text())['configuration'].get('down_direction')
    if world_down is None: raise ValueError('Semantic roll normalization needs explicit gravity; camera down is not gravity')
    frames=[f for f in sequence['frames'] if str(f['id']) in matrices]
    selected=[frames[i] for i in np.unique(np.linspace(0,len(frames)-1,min(max_views,len(frames))).astype(int))]
    votes=np.zeros(len(points),np.uint16);visible=np.zeros(len(points),np.uint16)
    records=[];hashes={};started=time.perf_counter(); previews=out/'frames';previews.mkdir()
    for index,frame in enumerate(selected):
        rgb_path,depth_path=Path(frame['rgb']),Path(frame['depth'])
        confidence_path=Path(frame['confidence']) if frame.get('confidence') else None
        for path in [rgb_path,depth_path]+([confidence_path] if confidence_path else []): hashes[str(path)]=sha256(path)
        with Image.open(rgb_path) as source: rgb=source.convert('RGB');pixels=np.array(rgb)
        pose=matrices[str(frame['id'])]; turns=upright_turns(pose,world_down)
        model_rgb=Image.fromarray(np.rot90(pixels,turns).copy())
        begun=time.perf_counter()
        with torch.inference_mode():
            logits=model(**processor(images=model_rgb,return_tensors='pt')).logits
            logits=torch.nn.functional.interpolate(logits,size=(model_rgb.height,model_rgb.width),mode='bilinear',align_corners=False)
            certainty,labels=logits.softmax(1).max(1)
        labels=np.rot90(labels[0].numpy(),-turns);certainty=np.rot90(certainty[0].numpy(),-turns)
        depth=cv2.imread(str(depth_path),cv2.IMREAD_UNCHANGED).astype(float)/sequence.get('depth_scale',1000)
        confidence=cv2.imread(str(confidence_path),cv2.IMREAD_UNCHANGED) if confidence_path else None
        if depth.shape!=labels.shape: raise ValueError('Semantic/depth dimensions differ')
        k=frame.get('intrinsics',sequence['intrinsics'])
        local=(points-pose[:3,3])@pose[:3,:3]; z=local[:,2]
        ids=np.flatnonzero((z>.2)&(z<10))
        x=np.rint(k['fx']*local[ids,0]/z[ids]+k['cx']).astype(int)
        y=np.rint(k['fy']*local[ids,1]/z[ids]+k['cy']).astype(int)
        good=(x>=0)&(x<rgb.width)&(y>=0)&(y<rgb.height);ids,x,y=ids[good],x[good],y[good]
        good=(depth[y,x]>.2)&(np.abs(depth[y,x]-z[ids])<=.08)
        if confidence is not None: good&=confidence[y,x]>=sequence.get('minimum_confidence',1)
        ids,x,y=ids[good],x[good],y[good];visible[ids]+=1
        furniture=np.isin(labels[y,x],furniture_ids)&(certainty[y,x]>=.6)
        votes[ids[furniture]]+=1
        overlay=pixels.copy()
        for name,color in [('wall',[0,190,255]),('floor',[20,220,70]),('ceiling',[230,220,20])]:
            mask=np.isin(labels,[i for i,label in names.items() if label==name])
            overlay[mask]=(.55*pixels[mask]+.45*np.array(color)).astype(np.uint8)
        mask=np.isin(labels,furniture_ids)&(certainty>=.6)
        overlay[mask]=(.55*pixels[mask]+.45*np.array([240,30,30])).astype(np.uint8)
        Image.fromarray(np.concatenate([pixels,overlay],axis=1)).save(previews/f'{index:03d}_{frame["id"]}.png')
        records.append(dict(frame_id=frame['id'],model_input_quarter_turns=turns,visible_cloud_points=len(ids),furniture_votes=int(furniture.sum()),
            inference_s=time.perf_counter()-begun,class_pixel_counts={names[int(i)]:int(count) for i,count in zip(*np.unique(labels,return_counts=True))}))
        print(f'Semantic diagnostic {index+1}/{len(selected)}: {len(ids)} visible, {furniture.sum()} furniture votes',flush=True)
    removed=removal_mask(votes,visible);filtered=points[~removed]
    np.savez_compressed(out/'visibility_votes.npz',visible_views=visible,furniture_votes=votes,removed=removed)
    np.savez_compressed(out/'filtered_cloud.npz',points=filtered.astype(np.float32))
    down=world_down
    frozen=json.loads((artifact/'layout_evidence.json').read_text());rows=[]
    refit=_fit_planes(points)
    candidate_seeds=_fit_planes(filtered) if removed.any() else refit
    for name,cloud,seeds in [('frozen_planes',points,planes),('unfiltered_refit',points,refit),
                             ('semantic_candidate',filtered,candidate_seeds)]:
        directory=out/name;directory.mkdir();begin=time.perf_counter()
        try:
            rooms,evidence=extract_layout(cloud,seeds,np.array(list(matrices.values()))[:,:3,3],down,path_breaks=frozen.get('path_breaks',()))
            (directory/'layout_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
            if rooms:export_layout(rooms,evidence,directory,complete_capture=False)
            rows.append(dict(method=name,rooms=len(rooms),coverage=evidence['camera_center_coverage_fraction'],
                unclosed=evidence['unclosed_geometry'],stages=evidence['boundary_stages'],runtime_s=time.perf_counter()-begin))
        except ValueError as exc:rows.append(dict(method=name,status='incomplete_geometry',reason=str(exc)))
    hashes.update({str(p):sha256(p) for p in [run/'run.json',run/'normalized_sequence.json',artifact/'cloud.npz',artifact/'trajectory.json']})
    result=dict(experiment='supplied_lidar_semantic_furniture_rejection',model=MODEL,revision=REVISION,weights_sha256=WEIGHTS_SHA256,
        terms='NVIDIA SegFormer: research/evaluation only; not a commercial production adoption',
        input_sha256=hashes,script_sha256=sha256(Path(__file__)),frames=records,source_points=len(points),
        removed_points=int(removed.sum()),unseen_points=int((visible==0).sum()),comparisons=rows,
        runtime_s=time.perf_counter()-started,uses_sensor_depth_and_poses=True,accuracy_validated=False,production_adopted=False,
        development_thresholds=dict(model_confidence=.6,minimum_furniture_views=2,dominant_visible_fraction=.6,visibility_tolerance_m=.08),
        limitations=['Uncalibrated semantic scores; no independently annotated segmentation truth',
                     'Unknown/unseen points are retained; two visible frames are not independent field repeats',
                     'Reconstruction remains partial; proxies cannot prove semantic rooms or measured accuracy'])
    (out/'comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'input_sha256','frames'}},indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path)
    parser.add_argument('--out',required=True,type=Path);parser.add_argument('--max-views',type=int,default=18)
    args=parser.parse_args();compare(args.run,args.out,args.max_views)
