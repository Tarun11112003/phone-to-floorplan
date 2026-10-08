import cv2
import numpy as np
import pytest

from floorplan.rgbd import _relative_pose,pose_against_registered


def views():
    rng=np.random.default_rng(17)
    xyz=rng.uniform([-.8,-.7,3],[.8,.7,6],size=(80,3))
    k=np.array([[250.,0,320],[0,250,240],[0,0,1]])
    angle=np.deg2rad(70)
    rotation=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]])
    translation=np.array([1.5,0,0]); target=xyz@rotation.T+translation
    def project(points): return (points@k.T)[:,:2]/points[:,2,None]
    descriptors=rng.normal(size=(80,32)).astype(np.float32)
    return (project(xyz),descriptors,xyz[:,2]),(project(target),descriptors.copy(),target[:,2]),k


def test_unordered_photos_use_verified_metric_geometry_without_video_motion_prior():
    a,b,k=views(); cv2.setRNGSeed(7)
    with pytest.raises(ValueError,match='large inter-frame'):
        _relative_pose(a,b,k,cv2,k)
    relative,quality=_relative_pose(a,b,k,cv2,k,ordered_motion=False)
    assert quality['metric_inliers']==80
    assert np.linalg.norm(relative[:3,3])==pytest.approx(1.5,abs=1e-6)
    pose,quality=pose_against_registered(b,k,[a,None],[k,k],[np.eye(4),np.eye(4)],cv2)
    assert np.allclose(pose,np.linalg.inv(relative),atol=1e-6)
    assert quality['reference_registered_index']==0


def test_pnp_success_cannot_override_inconsistent_target_depth():
    a,b,k=views()
    incompatible=(b[0],b[1],b[2]*2)
    with pytest.raises(ValueError,match='metric-depth'):
        _relative_pose(a,incompatible,k,cv2,k,ordered_motion=False)


def test_rgbd_can_initialize_after_an_unusable_first_view(tmp_path,monkeypatch):
    import json
    import floorplan.rgbd as rgbd
    camera=dict(width=64,height=48,fx=50,fy=50,cx=31.5,cy=23.5)
    frames=[]
    for i in range(3):
        cv2.imwrite(str(tmp_path/f'{i}.png'),np.full((48,64,3),i*60,np.uint8))
        np.save(tmp_path/f'{i}.npy',np.full((48,64),2,np.float32))
        frames.append(dict(id=i,rgb=f'{i}.png',depth=f'{i}.npy'))
    sequence=tmp_path/'sequence.json'
    sequence.write_text(json.dumps(dict(intrinsics=camera,depth_scale=1,frames=frames,pose_source='estimated',layout='polygons')))
    def features(gray,*args):
        if gray[0,0]==0: raise ValueError('No visual features in frame')
        return ('fixture','fixture','fixture')
    monkeypatch.setattr(rgbd,'_features',features)
    monkeypatch.setattr(rgbd,'_relative_pose',lambda *args,**kwargs:(np.eye(4),{'metric_inliers':30}))
    result=rgbd.reconstruct_rgbd(sequence,tmp_path/'result')
    assert result['tracked_frames']==2
    assert result['skipped_frames'][0]['frame_id']==0
    assert result['tracking_quality'][0]['recovered_after_skipped_frames']==1
    assert not result['floor_plan_ready']


def test_reconstructed_world_uses_camera_down_prior_in_the_same_gauge(tmp_path,monkeypatch):
    import json
    import floorplan.layout as layout
    import floorplan.rgbd as rgbd
    camera=dict(width=64,height=48,fx=50,fy=50,cx=31.5,cy=23.5)
    cv2.imwrite(str(tmp_path/'rgb.png'),np.full((48,64,3),120,np.uint8))
    np.save(tmp_path/'depth.npy',np.full((48,64),2,np.float32))
    pose=np.eye(4); pose[:3,:3]=[[1,0,0],[0,0,-1],[0,1,0]]
    frames=[dict(id=i,rgb='rgb.png',depth='depth.npy',camera_to_world=pose.tolist()) for i in range(3)]
    sequence=tmp_path/'sequence.json'
    sequence.write_text(json.dumps(dict(intrinsics=camera,depth_scale=1,frames=frames,
        pose_source='rgb_reconstruction',layout='polygons')))
    actual=layout.extract_layout; observed=[]
    def inspect_prior(*args,**kwargs):
        observed.append(np.asarray(args[3])); return actual(*args,**kwargs)
    monkeypatch.setattr(layout,'extract_layout',inspect_prior)
    result=rgbd.reconstruct_rgbd(sequence,tmp_path/'result')
    assert observed and np.array_equal(observed[0],[0,0,1])
    assert not result['floor_plan_ready']  # Flat depth alone is not a room.
