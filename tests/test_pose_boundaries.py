import numpy as np
import pytest

from floorplan.mapping import optimize_poses
from floorplan.pose_graph import consistent_edges,map_room_identities
from floorplan.rgbd import retained_path_breaks


def test_rejected_frames_preserve_breaks_and_do_not_create_traversals():
    assert retained_path_breaks([0,2,3,6],[1,4])==[1,3]
    assert retained_path_breaks([0,1,2],[1,2])==[1,2]
    assert retained_path_breaks([0,1,2])==[]


def test_independent_photo_poses_are_not_refined_with_sequential_constraints():
    poses=[np.eye(4) for _ in range(4)]
    for i,pose in enumerate(poses): pose[0,3]=i
    result,summary=optimize_poses([np.zeros((0,3))]*4,poses,path_breaks=[1,2,3])
    assert np.array_equal(result,poses)
    assert summary['verified_loops']==0
    assert len(summary['segments'])==4


def edge(a,b,x,inliers):
    transform=np.eye(4); transform[0,3]=x
    return dict(a=a,b=b,transform=transform,visual_inliers=inliers,fitness=.8)


def test_verified_cycle_consistency_rejects_false_link_and_retains_good_loop():
    records=[edge(1,0,2,100),edge(2,1,3,90),edge(2,0,5,80)]
    accepted,rejected=consistent_edges(3,records)
    assert len(accepted)==3 and not rejected
    assert accepted[-1]['cycle']
    records[-1]['transform'][0,3]=6
    accepted,rejected=consistent_edges(3,records)
    assert len(accepted)==2
    assert rejected[0]['cycle_translation_residual_m']==pytest.approx(1)
    assert rejected[0]['reason']=='inconsistent verified cycle'


def test_room_identity_association_does_not_lose_or_duplicate_folder_rooms():
    rooms=[dict(id='a',corners=[[0,0],[2,0],[2,2],[0,2]]),
           dict(id='b',corners=[[2,0],[4,0],[4,2],[2,2]])]
    sources={'capture_0:one':rooms[1]['corners'],'capture_1:two':rooms[0]['corners']}
    identities=map_room_identities(sources,rooms)
    assert identities['matches']['capture_0:one']['room_id']=='b'
    assert not identities['missing_source_rooms']
    sources['capture_2:lost']=[[9,0],[10,0],[10,1],[9,1]]
    assert map_room_identities(sources,rooms)['missing_source_rooms']==['capture_2:lost']


def test_historical_loop_verification_does_not_apply_consecutive_motion_bound(monkeypatch):
    import floorplan.rgbd as rgbd
    calls=[]
    def verified_loop(*args,**kwargs):
        calls.append(kwargs)
        return np.eye(4),dict(metric_inliers=80)
    monkeypatch.setattr(rgbd,'_relative_pose',verified_loop)
    rng=np.random.default_rng(9)
    # Nondegenerate identical 3D data exercise actual ICP and graph optimization.
    cloud=rng.uniform(-.5,.5,(350,3))
    poses=[np.eye(4) for _ in range(6)]
    _,summary=optimize_poses([cloud]*6,poses,[object()]*6,np.eye(3),keyframe_stride=1)
    assert calls and all(c.get('ordered_motion') is False for c in calls)
    assert summary['verified_loops']>0
