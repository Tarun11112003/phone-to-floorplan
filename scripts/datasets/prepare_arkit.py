"""Selectively acquire ARKitScenes mobile inputs; keep laser references separate."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile

import numpy as np
from scipy.spatial.transform import Rotation

BASE = 'https://docs-assets.developer.apple.com/ml-research/datasets/arkitscenes/v1'


def download(url, target):
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        temporary = target.with_suffix(target.suffix+'.part')
        print(f'Downloading {url}',flush=True)
        with urllib.request.urlopen(url,timeout=60) as response, temporary.open('wb') as file:
            while chunk := response.read(1024*1024): file.write(chunk)
        temporary.replace(target)
    digest = hashlib.sha256()
    with target.open('rb') as file:
        while chunk := file.read(1024*1024): digest.update(chunk)
    return {'url':url,'file':str(target),'bytes':target.stat().st_size,'sha256':digest.hexdigest()}


def acquire(output: Path, count=1):
    if not 1<=count<=10:
        raise ValueError('Select 1–10 scenes for this bounded local demo')
    record = download(BASE+'/raw/metadata.csv',output/'metadata.csv')
    rows = list(csv.DictReader((output/'metadata.csv').open(encoding='utf-8')))
    chosen, visits = [], set()
    for row in sorted(rows,key=lambda r:int(float(r['video_id']))):
        visit = row.get('visit_id')
        if row.get('has_laser_scanner_point_clouds','').lower() not in {'true','1'} or visit in visits:
            continue
        chosen.append(row); visits.add(visit)
        if len(chosen) == count: break
    if not chosen: raise ValueError('No scenes with laser references in metadata')
    records = [record]
    for index,row in enumerate(chosen):
        video = str(int(float(row['video_id'])))
        split = row.get('fold',row.get('split','Training'))
        folder = output/video
        for asset in ('lowres_wide','lowres_depth','confidence','lowres_wide_intrinsics','lowres_wide.traj'):
            name = asset if asset.endswith('.traj') else asset+'.zip'
            path = folder/name
            records.append(download(f'{BASE}/raw/{split}/{video}/{name}',path))
            if name.endswith('.zip'):
                with zipfile.ZipFile(path) as archive:
                    for info in archive.infolist():
                        relative = PurePosixPath(info.filename)
                        if relative.is_absolute() or '..' in relative.parts or ':' in info.filename:
                            raise ValueError('Unsafe archive path')
                        target = folder.joinpath(*relative.parts)
                        if info.is_dir(): continue
                        if not target.exists():
                            target.parent.mkdir(parents=True,exist_ok=True)
                            target.write_bytes(archive.read(info))
        prepare(folder,folder/'prepared')
        row['role'] = 'development' if index == 0 else 'held_out'
    provenance = {'dataset':'ARKitScenes','scenes':chosen,'assets':records,
                  'license':'https://github.com/apple/ARKitScenes/blob/main/LICENSE',
                  'reference_status':'Laser geometry available remotely; not fed to inference or automatically annotated.'}
    (output/'SOURCE.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    return provenance


def prepare(source: Path,output: Path,max_frames=180):
    output.mkdir(parents=True,exist_ok=True)
    rows = np.loadtxt(source/'lowres_wide.traj',ndmin=2)
    def stamp(path): return float(path.stem.rsplit('_',1)[1])
    calibration_files = sorted((source/'lowres_wide_intrinsics').glob('*.pincam'),key=stamp)
    calibration_times = np.asarray([stamp(p) for p in calibration_files])
    depths = sorted((source/'lowres_depth').glob('*.png'),key=stamp)
    depth_times = np.asarray([stamp(p) for p in depths])
    synchronized = sorted({int(np.argmin(abs(depth_times-t))) for t in rows[:,0]
                           if len(depth_times) and np.min(abs(depth_times-t)) <= 0.005})
    indices = np.asarray(synchronized)[np.unique(np.linspace(0,len(synchronized)-1,min(len(synchronized),max_frames)).astype(int))]
    frames, skipped = [], []
    for index in indices:
        depth = depths[index]; time = stamp(depth)
        pose_id = np.argmin(abs(rows[:,0]-time)); calibration_id = np.argmin(abs(calibration_times-time))
        rgb = source/'lowres_wide'/depth.name
        confidence = source/'confidence'/depth.name
        if abs(rows[pose_id,0]-time) > 0.005 or abs(calibration_times[calibration_id]-time)>0.005 or not rgb.exists() or not confidence.exists():
            skipped.append(depth.name); continue
        width,height,fx,fy,cx,cy = np.loadtxt(calibration_files[calibration_id])
        camera = dict(width=int(width),height=int(height),fx=fx,fy=fy,cx=cx,cy=cy)
        extrinsic = np.eye(4)
        extrinsic[:3,:3] = Rotation.from_rotvec(rows[pose_id,1:4]).as_matrix()
        extrinsic[:3,3] = rows[pose_id,4:7]
        pose = np.linalg.inv(extrinsic)
        frames.append({'id':depth.stem,'timestamp_s':time,'rgb':str(rgb.resolve()),'depth':str(depth.resolve()),
                       'confidence':str(confidence.resolve()),'intrinsics':camera,'camera_to_world':pose.tolist()})
    if len(frames)<2: raise ValueError('Too few synchronized ARKitScenes frames')
    # Dataset world frame can vary; initialize gravity prior from first camera.
    down = np.asarray(frames[0]['camera_to_world'])[:3,1].tolist()
    sequence = {'schema_version':1,'intrinsics':frames[0]['intrinsics'],'depth_scale':1000,'pose_source':'sensor',
                'down_direction':down,'minimum_confidence':1,'frames':frames,'skipped_unsynchronized':skipped,
                'source':'ARKitScenes lowres mobile LiDAR; native traj inverted to camera-to-world'}
    (output/'sequence.json').write_text(json.dumps(sequence,indent=2),encoding='utf-8')
    (output/'capture.json').write_text(json.dumps({'schema_version':2,'tier':'lidar','sequence':'sequence.json',
                                                'optimize_poses':True,'down_direction':down},indent=2),encoding='utf-8')
    return {'frames':len(frames),'skipped':len(skipped),'capture':str(output/'capture.json')}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path); parser.add_argument('--source',type=Path)
    parser.add_argument('--count',type=int,default=1)
    args=parser.parse_args()
    print(json.dumps(prepare(args.source,args.output) if args.source else acquire(args.output,args.count),indent=2))
