"""Simulate an independent measured reference from two ICL depth samples.

Depth is used only to prepare this explicitly disclosed calibration control;
the RGB pipeline receives the distance and image observations, never depth maps.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import cv2
import pycolmap


def prepare(model_path,sequence_path,output,video=False):
    model=pycolmap.Reconstruction(model_path)
    sequence=json.loads(sequence_path.read_text())
    frames=sequence['frames']; cameras=sequence['intrinsics']
    k=np.array([[cameras['fx'],0,cameras['cx']],[0,cameras['fy'],cameras['cy']],[0,0,1.]])
    # Existing ICL video encodes at 6fps and is sampled at 3fps. Confirm the
    # exact source frame photometrically to account for FFmpeg sampling phase.
    def depth_for(image):
        if video:
            index=(int(Path(image.name).stem.split('_')[-1])-1)*2
            observed=cv2.imread(str(model_path.parents[1]/'frames'/image.name),0)
            if observed is None: raise ValueError('Missing sampled video frame')
            observed=cv2.resize(observed,(160,120)).astype(float)
            choices=[]
            for candidate in range(max(0,index-2),min(len(frames),index+3)):
                source=cv2.imread(str(sequence_path.parent/frames[candidate]['rgb']),0)
                score=np.mean(abs(cv2.resize(source,(160,120)).astype(float)-observed))
                choices.append((score,candidate))
            score,index=min(choices)
            if score>8: raise ValueError('Video frame does not match expected ICL source')
            return sequence_path.parent/frames[index]['depth']
        return sequence_path.parent/'depth'/Path(image.name).name
    control=None
    for image in sorted(model.images.values(),key=lambda i:-i.num_points3D):
        depth=cv2.imread(str(depth_for(image)),-1)
        if depth is None: continue
        candidates=[]
        for point in image.points2D:
            if not point.has_point3D(): continue
            p=model.points3D[point.point3D_id]
            if p.track.length()<5 or p.error>.5: continue
            x,y=np.rint(point.xy).astype(int)
            if min(x,y)<2 or x>=depth.shape[1]-2 or y>=depth.shape[0]-2: continue
            patch=depth[y-1:y+2,x-1:x+2].astype(float)/sequence['depth_scale']
            if patch.min()<.3 or np.ptp(patch)>.015: continue
            local=np.linalg.inv(k)@np.r_[point.xy,1]*np.median(patch)
            candidates.append((p,local))
        for p,a in candidates[:100]:
            for q,b in candidates[:100]:
                length=np.linalg.norm(a-b)
                if not .7<length<1.2: continue
                def observations(point):
                    return [{'image':model.images[e.image_id].name,'pixel':model.images[e.image_id].points2D[e.point2D_idx].xy.tolist()} for e in point.track.elements]
                control={'length_m':float(length),'a':observations(p),'b':observations(q),'excluded_evaluation_edges':[],
                         'preparation_provenance':{'type':'simulated measured control from two sensor depth patches','source_image':image.name,
                           'depth_used_for_reconstruction':False,'depth_used_for_scale_control':True}}
                break
            if control: break
        if control: break
    if control is None: raise ValueError('No stable independent control found')
    output.write_text(json.dumps([control],indent=2),encoding='utf-8')
    return {'control_length_m':control['length_m'],'endpoint_view_counts':[len(control['a']),len(control['b'])]}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('model',type=Path); p.add_argument('sequence',type=Path); p.add_argument('output',type=Path); p.add_argument('--video',action='store_true')
    a=p.parse_args(); print(prepare(a.model,a.sequence,a.output,a.video))
