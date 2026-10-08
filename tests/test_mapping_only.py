import copy
import sqlite3
from types import SimpleNamespace

import numpy as np
import pytest
from scripts.experiments.experimental_mapping_only import (apply_mapping_intrinsics,
    map_without_frontend, require_pose_free_database, require_retained_tables, require_same_options)
from scripts.experiments.experimental_video_bridge import baseline_digest


def database(tmp_path):
    pycolmap = pytest.importorskip('pycolmap')
    path = tmp_path/'features.db'
    with pycolmap.Database.open(path): pass
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO cameras VALUES(13,2,1920,1440,?,0)',
                   (np.array([2304.,960.,720.,0.]).tobytes(),))
        db.execute("INSERT INTO images(image_id,name,camera_id) VALUES(42,'a.png',13)")
        for pair, rows in ((123, 0), (124, 17)):
            db.execute('INSERT INTO two_view_geometries(pair_id,rows,cols,data,config,F,E,H) '
                       'VALUES(?,?,2,?,3,?,?,?)',
                       (pair, rows, np.arange(rows*2,dtype=np.uint32).tobytes(),
                        np.eye(3).tobytes(), (np.eye(3)*2).tobytes(), (np.eye(3)*3).tobytes()))
    return path


def view():
    return dict(image='a.png', width=1920, height=1440, fx=1597.5, fy=1597.5, cx=955.2, cy=717.3)


def test_mapping_only_calibration_preserves_every_frontend_row_and_matrix(tmp_path):
    path = database(tmp_path); before = baseline_digest(path)
    expected = apply_mapping_intrinsics(path, [view()])
    after = baseline_digest(path)
    assert all(require_retained_tables(before, after).values())
    assert before['cameras'] != after['cameras']
    with sqlite3.connect(path) as db:
        params, prior = db.execute('SELECT params,prior_focal_length FROM cameras').fetchone()
        np.testing.assert_array_equal(np.frombuffer(params,dtype=np.float64), expected[13])
        assert prior == 1
        assert db.execute('SELECT rows FROM two_view_geometries ORDER BY pair_id').fetchall() == [(0,), (17,)]


@pytest.mark.parametrize('column', ['qvec','tvec','camera1','camera2'])
def test_cached_pose_or_camera_blob_is_rejected(tmp_path, column):
    path = database(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute(f'UPDATE two_view_geometries SET {column}=? WHERE pair_id=124', (b'cached',))
    with pytest.raises(ValueError, match='cached poses/cameras'): require_pose_free_database(path)


def test_sensor_prior_rejected_before_intrinsics_are_changed(tmp_path):
    path = database(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO pose_priors(pose_prior_id,corr_data_id,corr_sensor_id,'
                   'corr_sensor_type,coordinate_system) VALUES(1,42,13,0,0)')
    before = baseline_digest(path)
    with pytest.raises(ValueError, match='pose priors'): apply_mapping_intrinsics(path,[view()])
    assert baseline_digest(path) == before


def test_failed_camera_update_rolls_back_transaction(tmp_path):
    path = database(tmp_path); before = baseline_digest(path)
    wrong = dict(view(), image='absent.png')
    with pytest.raises(ValueError, match='dimensions'): apply_mapping_intrinsics(path,[view(),wrong])
    assert baseline_digest(path) == before


@pytest.mark.parametrize('table', ['matches','keypoints','two_view_geometries'])
def test_any_frontend_change_is_rejected(table):
    before = {k:'digest' for k in ('images','keypoints','descriptors','matches','two_view_geometries')}
    changed = dict(before); changed[table] = 'different'
    with pytest.raises(ValueError, match='frozen frontend'): require_retained_tables(before,changed)


def test_mapping_recipe_must_equal_preceding_fixed_control():
    previous = dict(mapping=dict(min_num_matches=15, constant_cameras=[13]), verification=dict(max_error=4))
    require_same_options(previous,copy.deepcopy(previous))
    changed = copy.deepcopy(previous); changed['mapping']['min_num_matches'] = 10
    with pytest.raises(ValueError, match='recipe differs'): require_same_options(previous,changed)


def test_mapping_only_native_entrypoint_never_calls_matching_or_verification():
    called = []
    def forbidden(*args,**kwargs): pytest.fail('Frontend must not run in mapping-only ablation')
    def mapping(*args,**kwargs): called.append((args,kwargs)); return {'model':'saved'}
    native = SimpleNamespace(incremental_mapping=mapping,verify_matches=forbidden,
                             match_exhaustive=forbidden,extract_features=forbidden)
    mapper = object()
    assert map_without_frontend(native,'db','images','sparse',mapper) == {'model':'saved'}
    assert called == [(('db','images','sparse'),dict(options=mapper))]


def test_adjacent_comparison_uses_identical_pairs_in_all_models():
    from scripts.evaluation.evaluate_mapping_only import common_adjacent_metrics
    def row(a,b,error):
        return dict(image_a=a,image_b=b,relative_rotation_error_deg=error,
                    translation_direction_error_deg=error*2,relative_length_ratio=1.)
    audits = dict(free=dict(adjacent=[row('a','b',2),row('b','d',999)]),
                  fixed=dict(adjacent=[row('a','b',1),row('b','c',888),row('c','d',777)]))
    result = common_adjacent_metrics(audits)
    assert result['free']['spans'] == result['fixed']['spans'] == 1
    assert result['free']['rotation_error_deg']['median'] == 2
    assert result['fixed']['rotation_error_deg']['median'] == 1


def test_absent_reference_cannot_produce_pose_comparison():
    from scripts.evaluation.evaluate_mapping_only import pair_metrics, common_adjacent_metrics
    absent = dict(unavailable_reason='No reference pair')
    assert pair_metrics(absent) == []
    assert common_adjacent_metrics(dict(candidate=absent)) == {}
