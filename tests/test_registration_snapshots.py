import copy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scripts.experiments.experimental_registration_snapshots import (native_snapshot_mapping,
    require_diagnostic_options, require_final_baseline)
from scripts.diagnostics.audit_registration_snapshots import snapshot_log_events, observation_residuals


def options(tmp_path):
    before=dict(mapping=dict(snapshot_path='.',snapshot_frames_freq=0,min_num_matches=15,
        mapper=dict(abs_pose_min_num_inliers=30),constant_cameras=[1,2]),verification=dict(max_error=4))
    after=copy.deepcopy(before)
    after['mapping'].update(snapshot_path=str((tmp_path/'snapshots').resolve()),snapshot_frames_freq=1)
    return before,after


def test_snapshot_fields_are_the_only_permitted_option_changes(tmp_path):
    before,after=options(tmp_path)
    assert len(require_diagnostic_options(before,after,tmp_path/'snapshots'))==2
    after['mapping']['mapper']['abs_pose_min_num_inliers']=29
    with pytest.raises(ValueError,match='only native snapshot'): require_diagnostic_options(before,after,tmp_path/'snapshots')


@pytest.mark.parametrize('change',['frequency','verification','path'])
def test_incomplete_or_different_snapshot_controls_are_rejected(tmp_path,change):
    before,after=options(tmp_path)
    if change=='frequency': after['mapping']['snapshot_frames_freq']=2
    if change=='verification': after['verification']['max_error']=5
    if change=='path': after['mapping']['snapshot_path']='elsewhere'
    with pytest.raises(ValueError,match='only native snapshot'): require_diagnostic_options(before,after,tmp_path/'snapshots')


def model():
    return dict(model_id=0,image_names=['a','b'],registered_images=2,sparse_points=20,
                mean_reprojection_error_px=1.48,binary_sha256={'images.bin':'original'})


@pytest.mark.parametrize('change',['binary_sha256','sparse_points','mean_reprojection_error_px','database'])
def test_intermediate_interpretation_requires_exact_final_reproduction(change):
    baseline=[model()]; actual=copy.deepcopy(baseline); tables={'matches':'retained'}; after=dict(tables)
    require_final_baseline(baseline,actual,tables,after)
    if change=='database': after['matches']='altered'
    else: actual[0][change]={'images.bin':'different'} if change=='binary_sha256' else 0
    with pytest.raises(ValueError,match='baseline|database'):
        require_final_baseline(baseline,actual,tables,after)


def test_snapshot_replay_does_not_run_frontend_or_supply_saved_poses():
    calls=[]
    def forbidden(*args,**kwargs): pytest.fail('Frontend and saved poses must remain withheld')
    def mapping(*args,**kwargs): calls.append((args,kwargs)); return {'saved':True}
    native=SimpleNamespace(incremental_mapping=mapping,verify_matches=forbidden,match_exhaustive=forbidden)
    mapper=object()
    assert native_snapshot_mapping(native,'db','rgb','sparse',mapper)=={'saved':True}
    assert calls==[(('db','rgb','sparse'),{'options':mapper})]


def test_native_log_association_preserves_failed_attempts_and_final_refinement():
    text='\n'.join(['Registering image #8 (num_reg_frames=2)',
        '=> Could not register, trying another image.',
        'Registering image #4 (num_reg_frames=2)',
        'Retriangulation and Global bundle adjustment','Linear solver failure',
        'Creating snapshot','Registering image #5 (num_reg_frames=3)',
        'Creating snapshot','Retriangulation and Global bundle adjustment'])
    snapshots,tail=snapshot_log_events(text)
    assert len(snapshots)==2
    assert snapshots[0]['last_registration_attempt']['image_id']==4
    assert snapshots[0]['global_refinements']==1 and snapshots[0]['solver_warnings']==1
    assert snapshots[1]['last_registration_attempt']['image_id']==5
    assert snapshots[1]['global_refinements']==0
    assert tail==[{'kind':'global_refinement','line':9}]


def test_snapshot_residuals_are_recomputed_from_observations_not_stale_point_error():
    class Observation:
        point3D_id=10
        xy=np.array([1.,1.])
        def has_point3D(self): return True
    pose=SimpleNamespace(rotation=SimpleNamespace(matrix=lambda:np.eye(3)),translation=np.zeros(3))
    image=SimpleNamespace(has_pose=True,points2D=[Observation()],camera_id=1,cam_from_world=lambda:pose)
    camera=SimpleNamespace(img_from_cam=lambda xyz:xyz[:,:2]/xyz[:,2,None])
    fixture=SimpleNamespace(images={1:image},points3D={10:SimpleNamespace(xyz=np.array([0.,0.,2.]),error=999.)},cameras={1:camera})
    metrics=observation_residuals(fixture)
    assert metrics['mean_observation_residual_px']==pytest.approx(np.sqrt(2))
    assert metrics['observations']==1 and metrics['nonpositive_depth']==0
