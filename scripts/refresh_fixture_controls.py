"""Simulate re-measuring a control in the controlled fixture, without rerendering.
This is fixture preparation only; reconstruction never reads simulation poses.
"""
import argparse
import json
from pathlib import Path
import numpy as np


def refresh(root,cache):
    sequence=json.loads((root/'sequence.json').read_text())
    if 'controlled synthetic' not in sequence.get('source',''): raise ValueError('Only controlled synthetic fixture supported')
    camera=sequence['intrinsics']; k=np.array([[camera['fx'],0,camera['cx']],[0,camera['fy'],camera['cy']],[0,0,1.]])
    control={'length_m':.5,'a':[],'b':[],'excluded_evaluation_edges':[]}
    for frame in sequence['frames']:
        pose=np.asarray(frame['camera_to_world']); center=pose[:3,3]
        if center[0]>=3: continue
        observations=[]
        for point in ([1.5,.1,0],[2.,.1,0]):
            local=(np.asarray(point)-center)@pose[:3,:3]
            if local[2]<=0: break
            uv=(k@local)[:2]/local[2]
            if not (4<uv[0]<camera['width']-4 and 4<uv[1]<camera['height']-4): break
            observations.append({'image':Path(frame['rgb']).name,'pixel':uv.tolist()})
        if len(observations)==2:
            control['a'].append(observations[0]); control['b'].append(observations[1])
    for tier in ('photos','video'):
        manifest=json.loads((root/f'{tier}.json').read_text())
        manifest['scale_references']=[control]
        manifest['sfm_cache']=str((cache/tier).resolve())
        (root/f'{tier}_calibrated.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    suite={'cases':[{'id':tier,'capture':f'{tier}_calibrated.json','reference':'reference.json','category':'synthetic_rgb_remeasured_control'} for tier in ('photos','video')]}
    (root/'calibrated_suite.json').write_text(json.dumps(suite,indent=2),encoding='utf-8')
    return {'control_views':len(control['a'])}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('root',type=Path); p.add_argument('cache',type=Path)
    args=p.parse_args(); print(refresh(args.root,args.cache))
