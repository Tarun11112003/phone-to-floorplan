"""Convert stock phone captures into auditable capture manifests."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageOps
from scipy.spatial.transform import Rotation


PHOTO_EXTENSIONS = {'.jpg','.jpeg','.png','.heic','.heif'}
VIDEO_EXTENSIONS = {'.mp4','.mov','.m4v'}


def _fresh(path):
    path=Path(path).resolve()
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f'Use an empty fresh intake directory: {path}')
    path.mkdir(parents=True,exist_ok=True)
    return path


def _hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def _write(output, manifest, mapping):
    (output/'capture.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (output/'intake.json').write_text(json.dumps(mapping,indent=2),encoding='utf-8')
    return output/'capture.json'


def prepare_photos(source, output):
    source=Path(source).resolve(); output=_fresh(output)
    rooms=sorted(p for p in source.iterdir() if p.is_dir())
    if not rooms:
        raise ValueError('Expected one subfolder per room, each containing 2–8 photos')
    normalized=output/'images'; normalized.mkdir()
    mapping=[]
    for room in rooms:
        if not re.fullmatch(r'[A-Za-z0-9_-]+',room.name):
            raise ValueError(f'Room folder needs a simple unique ID: {room.name}')
        photos=sorted(p for p in room.iterdir() if p.is_file() and p.suffix.lower() in PHOTO_EXTENSIONS)
        if not 2<=len(photos)<=8:
            raise ValueError(f'Room {room.name} has {len(photos)} photos; assignment requires 2–8')
        for index,path in enumerate(photos):
            if path.suffix.lower() in {'.heic','.heif'}:
                try:
                    from pillow_heif import register_heif_opener
                    register_heif_opener()
                except ImportError as exc:
                    raise RuntimeError('Install capture extra for HEIC: pip install -e ".[capture]"') from exc
            name=f'{room.name}__{index:02d}.png'
            with Image.open(path) as image:
                normalized_image=ImageOps.exif_transpose(image).convert('RGB')
                normalized_image.save(normalized/name)
            mapping.append(dict(room_id=room.name,source=str(path),source_sha256=_hash(path),
                                normalized=f'images/{name}',width=normalized_image.width,
                                height=normalized_image.height))
    return _write(output,dict(schema_version=2,tier='photos',source='images',max_frames=max(5,len(mapping)),
                              matching='exhaustive',dense_backend='openmvs',
                              capture_structure='per_room_folders',
                              unsupported_required_capabilities=['automatic room-folder stitching','metric scale without supplied evidence']),
                  dict(format='native_camera_room_folders',rooms=[r.name for r in rooms],images=mapping,
                       note='No measured scale, depth or poses were inferred from source files'))


def prepare_video(source, output):
    source=Path(source).resolve(); output=_fresh(output)
    if source.suffix.lower() not in VIDEO_EXTENSIONS or not source.is_file():
        raise ValueError('Expected an existing MOV/MP4/M4V video')
    try:
        frames,duration=imageio_ffmpeg.count_frames_and_secs(str(source))
    except Exception as exc:
        raise ValueError('Phone video could not be decoded by FFmpeg') from exc
    if frames<5 or duration<=0:
        raise ValueError('Walkthrough clip is too short for reconstruction')
    return _write(output,dict(schema_version=2,tier='video',source=str(source),fps=2,
                              max_frames=min(180,max(5,int(duration*2))),dense_backend='openmvs',
                              unsupported_required_capabilities=['metric scale without supplied evidence']),
                  dict(format='native_camera_video',source=str(source),source_sha256=_hash(source),
                       decoded_frames=frames,duration_s=duration))


def prepare_stray_scanner(source, output):
    source=Path(source).resolve(); output=_fresh(output)
    required=[source/'odometry.csv',source/'rgb.mp4',source/'depth']
    if any(not p.exists() for p in required):
        raise ValueError('Expected Stray Scanner odometry.csv, rgb.mp4 and depth/')
    with (source/'odometry.csv').open(newline='',encoding='utf-8-sig') as stream:
        rows=list(csv.DictReader(stream))
    keys={'timestamp','frame','x','y','z','qx','qy','qz','qw','fx','fy','cx','cy'}
    if not rows or not keys.issubset(rows[0]):
        raise ValueError('Stray Scanner odometry header is incomplete')
    frames_dir=output/'frames'; frames_dir.mkdir()
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','error','-noautorotate','-i',str(source/'rgb.mp4'),
             '-vsync','0','-start_number','0',str(frames_dir/'rgb_%06d.png')]
    subprocess.run(command,capture_output=True,text=True,check=True)
    import cv2
    records=[]
    origin_time=None
    seen_frames=set()
    for row in rows:
        number=int(row['frame']); depth=source/'depth'/f'{number:06d}.png'
        if number in seen_frames:
            raise ValueError(f'Duplicate frame ID {number}')
        seen_frames.add(number)
        rgb=frames_dir/f'rgb_{number:06d}.png'
        if not depth.is_file() or not rgb.is_file():
            raise ValueError(f'RGB/depth pair missing for frame {number}; no silent synchronization')
        depth_image=cv2.imread(str(depth),cv2.IMREAD_UNCHANGED)
        rgb_image=cv2.imread(str(rgb),cv2.IMREAD_UNCHANGED)
        if depth_image is None or depth_image.dtype!=np.uint16 or depth_image.ndim!=2:
            raise ValueError(f'Depth frame {number} must be 16-bit millimetres')
        if rgb_image is None:
            raise ValueError(f'RGB frame {number} cannot be decoded')
        rgb_height,rgb_width=rgb_image.shape[:2]
        depth_height,depth_width=depth_image.shape
        if abs(rgb_width/rgb_height-depth_width/depth_height)>1e-3:
            raise ValueError(f'RGB/depth aspect ratios differ at {number}; calibrated registration is required')
        distortion=source/'distortion'/f'{number:06d}.bin'
        if distortion.exists():
            raise ValueError('Capture has a distortion lookup table; calibrated rectification must be implemented before inference')
        confidence=source/'confidence'/f'{number:06d}.png'
        if confidence.parent.exists() and not confidence.exists():
            raise ValueError(f'Confidence frame missing at {number}')
        if confidence.exists():
            confidence_image=cv2.imread(str(confidence),cv2.IMREAD_UNCHANGED)
            if confidence_image is None or confidence_image.shape!=depth_image.shape or not np.isin(confidence_image,[0,1,2]).all():
                raise ValueError(f'Confidence frame {number} must match depth with values 0, 1 or 2')
        sx,sy=depth_width/rgb_width,depth_height/rgb_height
        camera=dict(width=depth_width,height=depth_height,
                    fx=float(row['fx'])*sx,fy=float(row['fy'])*sy,
                    cx=float(row['cx'])*sx,cy=float(row['cy'])*sy)
        if min(camera['fx'],camera['fy'])<=0 or not 0<=camera['cx']<camera['width'] or not 0<=camera['cy']<camera['height']:
            raise ValueError(f'Invalid intrinsics for frame {number}')
        if (rgb_height,rgb_width)!=(depth_height,depth_width):
            registered=frames_dir/f'registered_{number:06d}.png'
            cv2.imwrite(str(registered),cv2.resize(rgb_image,(depth_width,depth_height),interpolation=cv2.INTER_AREA))
            rgb=registered
        quaternion=np.array([float(row[k]) for k in ('qx','qy','qz','qw')])
        if abs(np.linalg.norm(quaternion)-1)>.01:
            raise ValueError(f'Non-unit camera quaternion at frame {number}')
        pose=np.eye(4)
        pose[:3,:3]=Rotation.from_quat(quaternion/np.linalg.norm(quaternion)).as_matrix() @ np.diag([1,-1,-1])
        pose[:3,3]=[float(row[k]) for k in ('x','y','z')]
        timestamp=float(row['timestamp'])
        if origin_time is None: origin_time=timestamp
        record=dict(id=number,timestamp_s=timestamp-origin_time,rgb=str(rgb),depth=str(depth),
                    intrinsics=camera,camera_to_world=pose.tolist())
        if confidence.exists(): record['confidence']=str(confidence)
        records.append(record)
    if len(records)<2 or any(b['timestamp_s']<=a['timestamp_s'] for a,b in zip(records,records[1:])):
        raise ValueError('At least two synchronized frames with strictly increasing timestamps required')
    sequence=dict(schema_version=1,intrinsics=records[0]['intrinsics'],depth_scale=1000,
                  pose_source='sensor',minimum_confidence=1,frames=records,
                  source='Stray Scanner odometry, raw RGB/depth/confidence',
                  coordinate_conversion='ARKit camera right/up/back to OpenCV right/down/forward')
    (output/'sequence.json').write_text(json.dumps(sequence,indent=2),encoding='utf-8')
    return _write(output,dict(schema_version=2,tier='lidar',sequence='sequence.json',
                              optimize_poses=True,down_direction=[0,-1,0]),
                  dict(format='stray_scanner',version_tested='format.md as read 2026-10-06; device untested',
                       source=str(source),source_sha256={str(p):_hash(p) for p in required[:2]},frames=len(records),
                       note='RGB resampled to depth resolution with scaled per-frame intrinsics; optical registration and sensor coordinates require physical verification'))


def prepare_capture(tier, source, output):
    if tier=='photos': return prepare_photos(source,output)
    if tier=='video': return prepare_video(source,output)
    if tier=='lidar': return prepare_stray_scanner(source,output)
    raise ValueError('tier must be photos, video or lidar')
