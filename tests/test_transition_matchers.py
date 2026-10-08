import json
import sqlite3

import numpy as np
import pytest

from scripts.experiments.experimental_transition_matchers import ANCHORS, colmap_keypoints, copy_database, frozen_options, pair_belongs
from scripts.evaluation.compare_transition_matchers import compare


def test_learned_keypoints_convert_original_pixel_centers_without_rescaling():
    points=np.array([[0.,0.],[1919.,1439.],[127.25,90.75]])
    assert np.array_equal(colmap_keypoints(points), points+.5)
    assert np.array_equal(points, [[0.,0.],[1919.,1439.],[127.25,90.75]])


@pytest.mark.parametrize('points', [np.zeros((2,3)), [[np.nan,1.]], [1.,2.]])
def test_invalid_learned_feature_coordinates_fail_closed(points):
    with pytest.raises(ValueError,match='Nx2'):
        colmap_keypoints(points)


def test_subset_pair_must_have_both_retained_images():
    assert pair_belongs(21*2147483647+24,{21,24})
    assert not pair_belongs(21*2147483647+25,{21,24})


def test_experiment_rejects_any_downstream_guard_change():
    import pycolmap
    verify=pycolmap.TwoViewGeometryOptions();verify.ransac.random_seed=7
    mapper=pycolmap.IncrementalPipelineOptions(num_threads=1,random_seed=7)
    mapper.mapper.num_threads=1;mapper.mapper.random_seed=7;mapper.triangulation.random_seed=7
    record={'options':json.loads(json.dumps({'verification':verify.todict(),'mapping':mapper.todict()},default=str))}
    frozen_options(pycolmap,record)
    record['options']['verification']['min_num_inliers']=14
    with pytest.raises(ValueError,match='verification options differ'):
        frozen_options(pycolmap,record)
    record['options']['verification']['min_num_inliers']=15
    record['options']['mapping']['mapper']['init_min_tri_angle']=1.5
    with pytest.raises(ValueError,match='mapping options differ'):
        frozen_options(pycolmap,record)


def test_learned_database_preserves_camera_priors_without_inheriting_matches_or_poses(tmp_path):
    import pycolmap
    source=(tmp_path/'source.db').resolve();target=(tmp_path/'learned.db').resolve()
    names=ANCHORS+[f'bridge_{i:05d}.png' for i in range(20)]
    with pycolmap.Database.open(source): pass
    params=np.array([2304.,960.,720.,0.],np.float64).tobytes()
    with sqlite3.connect(source) as conn:
        conn.execute('INSERT INTO cameras VALUES (1,2,1920,1440,?,0)',(params,))
        conn.execute('INSERT INTO rigs VALUES (1,1,0)')
        for i,name in enumerate(names,1):
            conn.execute('INSERT INTO images VALUES (?,?,1)',(i,name))
            conn.execute('INSERT INTO frames VALUES (?,1)',(i,))
            conn.execute('INSERT INTO frame_data VALUES (?,?,1,0)',(i,i))
        conn.execute('INSERT INTO keypoints VALUES (1,1,2,?)',(np.ones((1,2),np.float32).tobytes(),))
        conn.execute('INSERT INTO matches VALUES (?,0,2,?)',(2147483649,b''))
        conn.execute('INSERT INTO pose_priors (pose_prior_id,corr_data_id,corr_sensor_id,corr_sensor_type,coordinate_system) VALUES (1,1,1,0,0)')
    ids=copy_database(source,target,names,False,pycolmap)
    assert len(ids)==24
    with sqlite3.connect(source) as old, sqlite3.connect(target) as new:
        for table in ('cameras','images','rigs','frames','frame_data'):
            assert old.execute(f'SELECT * FROM {table}').fetchall()==new.execute(f'SELECT * FROM {table}').fetchall()
        for table in ('keypoints','descriptors','matches','two_view_geometries','pose_priors'):
            assert new.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==0


@pytest.mark.parametrize('field',['image_sha256','options','script_sha256'])
def test_comparison_rejects_different_inputs_or_recipe(tmp_path,field):
    folders=[]
    for index,mode in enumerate(('sift','sift','lightglue','lightglue')):
        folder=tmp_path/str(index);folder.mkdir();folders.append(folder)
        record=dict(mode=mode,image_sha256={},input_sha256={},options={},production_code_sha256={},
                    temporal_window=[],script_sha256='same')
        if index==2: record[field]='different'
        (folder/'experiment.json').write_text(json.dumps(record))
    with pytest.raises(ValueError,match=field):
        compare(*folders,tmp_path/'out')
