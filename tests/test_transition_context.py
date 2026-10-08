import sqlite3
from pathlib import Path
import numpy as np
import pytest

from scripts.experiments.experimental_transition_context import CONTEXT, context_window, copy_context_database, group_model_status
from scripts.evaluation.compare_transition_context import group_track_status, immutable_trial_files


def test_context_keeps_every_transition_view_and_adds_only_declared_anchors():
    retained=[dict(image=f'bridge_{i:05d}.png',source_timestamp_s=11+i/16) for i in range(24)]
    original=[dict(image=n,source_timestamp_s=i) for i,n in enumerate(CONTEXT)]
    window=context_window(retained,original)
    assert len(window)==32
    assert {r['image'] for r in window}=={r['image'] for r in retained}|set(CONTEXT)
    assert [r['source_timestamp_s'] for r in window]==sorted(r['source_timestamp_s'] for r in window)
    with pytest.raises(ValueError,match='Missing or duplicate'):
        context_window(retained,original[:-1])


def test_group_presence_requires_members_from_both_original_groups():
    groups=[['right1','right2'],['left1','left2']]
    assert not group_model_status(['left1','left2'],groups)['both_target_groups_registered']
    assert group_model_status(['left2','right1'],groups)['both_target_groups_registered']


@pytest.mark.parametrize('sift',[False,True])
def test_context_database_withholds_poses_and_excludes_unselected_images(tmp_path,sift):
    import pycolmap
    source=(tmp_path/'source.db').resolve();target=(tmp_path/'target.db').resolve()
    names=list(CONTEXT)+[f'bridge_{i:05d}.png' for i in range(24)]
    with pycolmap.Database.open(source): pass
    with sqlite3.connect(source) as db:
        db.execute('INSERT INTO cameras VALUES (1,2,1920,1440,?,0)',(np.array([2304.,960.,720.,0.]).tobytes(),))
        db.execute('INSERT INTO rigs VALUES (1,1,0)')
        for i,n in enumerate(names+['excluded.png'],1):
            db.execute('INSERT INTO images VALUES (?,?,1)',(i,n))
            db.execute('INSERT INTO frames VALUES (?,1)',(i,))
            db.execute('INSERT INTO frame_data VALUES (?,?,1,0)',(i,i))
        db.execute('INSERT INTO pose_priors (pose_prior_id,corr_data_id,corr_sensor_id,corr_sensor_type,coordinate_system) VALUES (1,1,1,0,0)')
        for i in (1,33):
            db.execute('INSERT INTO keypoints VALUES (?,1,2,?)',(i,np.zeros((1,2),np.float32).tobytes()))
        for b in (2,33):
            db.execute('INSERT INTO matches VALUES (?,1,2,?)',(2147483647+b,np.zeros((1,2),np.uint32).tobytes()))
    copy_context_database(source,target,names,sift,pycolmap)
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT COUNT(*) FROM images').fetchone()[0]==32
        assert db.execute('SELECT COUNT(*) FROM pose_priors').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM keypoints').fetchone()[0]==int(sift)
        assert db.execute('SELECT COUNT(*) FROM matches').fetchone()[0]==int(sift)


def test_context_database_refuses_incomplete_selection(tmp_path):
    with pytest.raises(ValueError,match='32 unique'):
        copy_context_database(tmp_path/'unused.db',tmp_path/'unused_target.db',list(CONTEXT),False,None)


def test_group_track_check_keeps_transitive_conflicts_explicit():
    tracks=[[('left',0),('right',0)], [('left',1),('left',2),('right',1)], [('left',3),('mid',0)]]
    assert group_track_status(tracks,[['left'],['right']])==dict(group_spanning_tracks=2,clean_group_spanning_tracks=1)


def test_trial_integrity_retains_wal_data_but_excludes_mutable_shm(tmp_path):
    for name in ('features.db','features.db-wal','features.db-shm','experiment.json'):
        (tmp_path/name).write_bytes(b'initial')
    frozen=immutable_trial_files([tmp_path])
    assert {Path(p).name for p in frozen}=={'features.db','features.db-wal','experiment.json'}
    (tmp_path/'features.db-shm').write_bytes(b'new read marks')
    assert immutable_trial_files([tmp_path])==frozen
    (tmp_path/'features.db-wal').write_bytes(b'changed actual rows')
    assert immutable_trial_files([tmp_path])!=frozen
