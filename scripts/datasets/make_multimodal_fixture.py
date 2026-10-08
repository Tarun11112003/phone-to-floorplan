"""Render a controlled two-room RGB/video/depth fixture with isolated references.

Synthetic sensor poses are explicitly provided only to the depth fixture. RGB
captures receive images and a simulated measured control, never poses or depth.
"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path
import numpy as np
import cv2
import imageio_ffmpeg


def make(output: Path, dense_backend='sgbm', ordered_photos=False):
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Use a fresh fixture directory; preserve previous benchmark inputs')
    output.mkdir(parents=True,exist_ok=True)
    rgb_dir=output/'rgb'; depth_dir=output/'depth'
    rgb_dir.mkdir(exist_ok=True); depth_dir.mkdir(exist_ok=True)
    # x/z floor coordinates; y points down; floor is y=1.5.
    a=[[0,0],[4,0],[4,2],[3,2],[3,4],[0,4]]
    b=[[4,0],[7,0],[7,2],[4,2]]
    walls=[([0,0],[7,0]),([7,0],[7,2]),([7,2],[3,2]),([3,2],[3,4]),([3,4],[0,4]),([0,4],[0,0]),
           ([4,0],[4,.5]),([4,1.5],[4,2])]
    width,height,fx=320,240,240.
    k=np.array([[fx,0,159.5],[0,fx,119.5],[0,0,1]])
    yy,xx=np.mgrid[:height,:width]
    rays=np.column_stack([(xx.ravel()-k[0,2])/fx,(yy.ravel()-k[1,2])/fx,np.ones(width*height)])
    trajectory=[]
    # Orbit inside each room and traverse the opening, with nearby overlapping views.
    for center in ([1.7,1.4],[5.5,1.]):
        for angle in np.linspace(0,2*np.pi,40,endpoint=False):
            pos=np.array([center[0]+.35*np.sin(angle),0,center[1]+.30*np.cos(angle)])
            trajectory.append((pos,angle))
        if center[0]<4:
            for x in np.linspace(2.0,5.2,17): trajectory.append((np.array([x,0,1.]),np.pi/2))
    rng=np.random.default_rng(930)
    textures=[]
    for _ in range(10):
        # 12.79 m texture period exceeds every wall and floor extent. The V2
        # 6.39 m period aliased a seven-metre wall, creating a false SfM loop.
        small=rng.integers(30,225,(1024,1024,3),dtype=np.uint8)
        textures.append(cv2.GaussianBlur(small,(3,3),.5))
    frames=[]; projections=[]
    controls=[np.array([1.5,.1,0]),np.array([2.,.1,0])]
    for index,(pos,angle) in enumerate(trajectory):
        forward=np.array([np.sin(angle)*np.cos(.25),np.sin(.25),np.cos(angle)*np.cos(.25)])
        right=np.array([np.cos(angle),0,-np.sin(angle)]); down=np.cross(forward,right)
        rotation=np.column_stack([right,down,forward]); directions=rays@rotation.T
        distance=np.full(len(rays),np.inf); surface=np.full(len(rays),-1)
        for sid,(start,end) in enumerate(walls):
            start=np.asarray(start); edge=np.asarray(end)-start
            normal=np.array([-edge[1],edge[0]])
            denominator=directions[:,[0,2]]@normal
            with np.errstate(divide='ignore',invalid='ignore'):
                t=((start-pos[[0,2]])@normal)/denominator
                hit=pos+t[:,None]*directions
                along=(hit[:,[0,2]]-start)@edge/(edge@edge)
            valid=(t>0)&(t<distance)&(along>=0)&(along<=1)&(hit[:,1]>=-1.2)&(hit[:,1]<=1.5)
            distance[valid]=t[valid]; surface[valid]=sid
        for level,sid in [(1.5,8),(-1.2,9)]:
            with np.errstate(divide='ignore',invalid='ignore'): t=(level-pos[1])/directions[:,1]
            valid=(t>0)&(t<distance); distance[valid]=t[valid]; surface[valid]=sid
        xyz=pos+distance[:,None]*directions
        colors=np.zeros((len(rays),3),dtype=np.uint8)
        for sid in range(10):
            mask=surface==sid; pts=xyz[mask]
            if sid<8:
                edge=np.asarray(walls[sid][1])-walls[sid][0]; edge=edge/np.linalg.norm(edge)
                u=pts[:,[0,2]]@edge; v=pts[:,1]
            else: u,v=pts[:,0],pts[:,2]
            mx=np.mod(u*80,1023).astype(np.float32).reshape(-1,1)
            my=np.mod(v*80,1023).astype(np.float32).reshape(-1,1)
            colors[mask]=np.concatenate([cv2.remap(textures[sid],mx[start:start+16000],my[start:start+16000],cv2.INTER_LINEAR).reshape(-1,3)
                                         for start in range(0,len(mx),16000)]) if len(mx) else np.empty((0,3),np.uint8)
        name=f'frame_{index+1:05d}.png'
        cv2.imwrite(str(rgb_dir/name),colors.reshape(height,width,3))
        cv2.imwrite(str(depth_dir/name),np.rint(np.minimum(distance,10)*1000).astype(np.uint16).reshape(height,width))
        pose=np.eye(4); pose[:3,:3]=rotation; pose[:3,3]=pos
        frames.append({'id':index,'timestamp_s':index/2,'rgb':f'rgb/{name}','depth':f'depth/{name}','camera_to_world':pose.tolist()})
        projected=[]
        for point in controls:
            camera=(point-pos)@rotation
            pixel=(camera@k.T)[:2]/camera[2] if camera[2]>0 else np.array([-1,-1])
            projected.append(pixel.tolist() if 4<pixel[0]<width-4 and 4<pixel[1]<height-4 else None)
        if all(p is not None for p in projected) and pos[0]<3:
            projections.append((name,projected))
    calibration=dict(width=width,height=height,fx=fx,fy=fx,cx=159.5,cy=119.5)
    sequence={'schema_version':1,'intrinsics':calibration,'depth_scale':1000,'pose_source':'sensor',
              'source':'controlled synthetic sensor simulation; exact simulated sensor poses','frames':frames}
    (output/'sequence.json').write_text(json.dumps(sequence,indent=2),encoding='utf-8')
    control={'length_m':float(np.linalg.norm(controls[0]-controls[1])),'a':[{'image':name,'pixel':p[0]} for name,p in projections],
             'b':[{'image':name,'pixel':p[1]} for name,p in projections],'excluded_evaluation_edges':[]}
    for tier in ('photos','video','lidar'):
        manifest={'schema_version':2,'tier':tier}
        if tier=='lidar': manifest.update(sequence='sequence.json',optimize_poses=False)
        else: manifest.update(source='rgb' if tier=='photos' else 'capture.mp4',camera_model='PINHOLE',
                              camera_params='240,240,159.5,119.5',max_frames=len(frames),fps=2,scale_references=[control],max_pairs=60,
                              dense_backend=dense_backend, ordered_capture=tier=='video' or ordered_photos)
        (output/f'{tier}.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    truth={'rooms':[{'id':'a','corners':a},{'id':'b','corners':b}],
           'connections':[{'rooms':['a','b'],'width_m':1}],
           'provenance':'Analytic scene definition; evaluation-only, never loaded by inference'}
    (output/'reference.json').write_text(json.dumps(truth,indent=2),encoding='utf-8')
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','error','-y','-framerate','2','-i',str(rgb_dir/'frame_%05d.png'),
                    '-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(output/'capture.mp4')],check=True)
    suite={'cases':[{'id':tier,'capture':f'{tier}.json','reference':'reference.json','category':'synthetic_simulated_sensor' if tier=='lidar' else 'synthetic_rgb'} for tier in ('lidar','photos','video')]}
    (output/'suite.json').write_text(json.dumps(suite,indent=2),encoding='utf-8')
    return {'frames':len(frames),'controls_views':len(projections),'suite':str(output/'suite.json')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('output',type=Path)
    parser.add_argument('--dense-backend', choices=['sgbm','openmvs'], default='sgbm')
    parser.add_argument('--ordered-photos', action='store_true', help='Declare continuous capture order in photo filenames')
    args=parser.parse_args(); print(json.dumps(make(args.output,args.dense_backend,args.ordered_photos),indent=2))
