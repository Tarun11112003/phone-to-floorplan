"""Create independently framed overlapping captures from the synthetic fixture."""
import argparse
import json
from pathlib import Path
import numpy as np


def make(source,output):
    sequence=json.loads(source.read_text())
    if 'controlled synthetic' not in sequence.get('source',''): raise ValueError('Controlled fixture required')
    transform=np.array([[0.,0,1,8],[0,1,0,0],[-1,0,0,-3],[0,0,0,1]])
    for name,subset,change in [('first',sequence['frames'][:65],np.eye(4)),('second',sequence['frames'][35:],transform)]:
        folder=output/name; folder.mkdir(parents=True,exist_ok=True)
        frames=[]
        for original in subset:
            frame=dict(original)
            for key in ('rgb','depth'): frame[key]=str((source.parent/frame[key]).resolve())
            frame['camera_to_world']=(change@np.asarray(frame['camera_to_world'])).tolist()
            frames.append(frame)
        capture=dict(sequence,frames=frames,down_direction=change[:3,1].tolist())
        (folder/'sequence.json').write_text(json.dumps(capture,indent=2),encoding='utf-8')
        (folder/'capture.json').write_text(json.dumps({'schema_version':2,'tier':'lidar','sequence':'sequence.json','optimize_poses':False},indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('sequence',type=Path); p.add_argument('output',type=Path)
    a=p.parse_args(); make(a.sequence,a.output)
