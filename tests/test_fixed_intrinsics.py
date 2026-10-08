import copy
import json
import sqlite3
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest
from floorplan.provenance import sha256
from scripts.experimental_fixed_intrinsics import (apply_intrinsics, check_saved_intrinsics,
    export_calibration, fixed_options, option_diff, serialize, validate_calibration)


def calibration():
    return dict(schema='isolated-optical-intrinsics-v1', source_sha256='source',
                alignment_audit_sha256='timing', views=[dict(image='a.png', sensor_frame=42,
                width=1920, height=1440, fx=1597.5, fy=1597.5, cx=955.2, cy=717.3)])


@pytest.mark.parametrize('extra', ['camera_to_world', 'qx', 'position', 'imu'])
def test_mapping_calibration_rejects_pose_or_other_undeclared_fields(extra):
    record = calibration(); record['views'][0][extra] = [1, 2, 3]
    with pytest.raises(ValueError, match='undeclared fields'):
        validate_calibration(record, ['a.png'])


@pytest.mark.parametrize('field,value', [('fx', float('nan')), ('fy', 1600), ('cx', 3000),
                                       ('sensor_frame', -1), ('height', 0)])
def test_invalid_or_incompatible_intrinsics_rejected(field, value):
    record = calibration(); record['views'][0][field] = value
    with pytest.raises(ValueError): validate_calibration(record, ['a.png'])


def test_export_does_not_parse_or_emit_odometry_poses(tmp_path):
    source = tmp_path/'odometry.csv'
    source.write_text('frame, fx, fy, cx, cy, x, y, z, qx, qy, qz, qw\n'
                      '0, 1597.5, 1597.5, 955.2, 717.3, INVALID, INVALID, INVALID, INVALID, INVALID, INVALID, INVALID\n')
    Image.new('RGB', (1920,1440)).save(tmp_path/'a.png')
    audit = tmp_path/'audit.json'
    audit.write_text(json.dumps(dict(input_sha256={str(source.resolve()):sha256(source)},
                        pixel_witnesses=[dict(pixels_exact=True)],
                        alignment=dict(views=[dict(image='a.png',sensor_frame=0)]))))
    result = export_calibration(source, audit, tmp_path, tmp_path/'calibration.json')
    assert set(result['views'][0]) == {'image','sensor_frame','width','height','fx','fy','cx','cy'}
    assert result['views'][0]['fx'] == 1597.5
    with pytest.raises(ValueError, match='already exists'):
        export_calibration(source, audit, tmp_path, tmp_path/'calibration.json')


def test_intrinsic_policy_changes_only_allowed_native_options():
    pycolmap = pytest.importorskip('pycolmap')
    verification = pycolmap.TwoViewGeometryOptions(); verification.ransac.random_seed = 7
    mapper = pycolmap.IncrementalPipelineOptions(num_threads=1, random_seed=7)
    mapper.mapper.num_threads=1; mapper.mapper.random_seed=7; mapper.triangulation.random_seed=7
    baseline = dict(options=dict(features={'unchanged':True}, matching={'unchanged':True},
                                 verification=serialize(verification), mapping=serialize(mapper)))
    original = copy.deepcopy(baseline)
    verify, fixed, options, changes = fixed_options(pycolmap, baseline, [13,16])
    assert baseline == original
    assert serialize(verify) == baseline['options']['verification']
    assert fixed.constant_cameras == {13,16} and fixed.mapper.constant_cameras == {13,16}
    assert not fixed.ba_refine_focal_length and not fixed.ba_refine_extra_params
    assert not fixed.mapper.abs_pose_refine_focal_length and not fixed.mapper.abs_pose_refine_extra_params
    assert not fixed.use_prior_position and not fixed.ba_refine_principal_point
    assert len(changes) == 6
    bad = copy.deepcopy(options); bad['mapping']['min_num_matches'] = 10
    with pytest.raises(ValueError, match='guards'): option_diff(baseline['options'], bad)
    bad = copy.deepcopy(options); bad['verification']['ransac']['max_error'] = 8
    with pytest.raises(ValueError, match='guards'): option_diff(baseline['options'], bad)
    bad = copy.deepcopy(options); bad['mapping']['use_prior_position'] = True
    with pytest.raises(ValueError, match='guards'): option_diff(baseline['options'], bad)


def database(tmp_path):
    path = tmp_path/'features.db'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE cameras(camera_id INT,model INT,width INT,height INT,params BLOB,prior_focal_length INT);'
                         'CREATE TABLE images(image_id INT,name TEXT,camera_id INT);'
                         'CREATE TABLE pose_priors(pose_prior_id INT);CREATE TABLE rig_sensors(sensor_id INT);'
                         'CREATE TABLE two_view_geometries(pair_id INT);')
        db.execute('INSERT INTO cameras VALUES(13,2,1920,1440,?,0)',(np.array([2304,960,720,0.]).tobytes(),))
        db.execute("INSERT INTO images VALUES(42,'a.png',13)")
        db.execute('INSERT INTO two_view_geometries VALUES(123)')
    return path


def test_calibration_updates_only_intrinsics_and_clears_stale_geometry(tmp_path):
    path = database(tmp_path)
    result = apply_intrinsics(path, calibration()['views'])
    assert result == {13:[1597.5,955.2,717.3,0.]}
    with sqlite3.connect(path) as db:
        params, prior = db.execute('SELECT params,prior_focal_length FROM cameras').fetchone()
        np.testing.assert_array_equal(np.frombuffer(params,dtype=np.float64),result[13])
        assert prior == 1 and db.execute('SELECT COUNT(*) FROM two_view_geometries').fetchone()[0] == 0
        assert db.execute('SELECT * FROM images').fetchall() == [(42,'a.png',13)]


def test_control_rejects_sensor_pose_priors(tmp_path):
    path = database(tmp_path)
    with sqlite3.connect(path) as db: db.execute('INSERT INTO pose_priors VALUES(1)')
    with pytest.raises(ValueError, match='sensor pose'): apply_intrinsics(path,calibration()['views'])


def test_native_model_intrinsics_must_remain_exact():
    params = np.array([1597.5,955.2,717.3,0.])
    camera = SimpleNamespace(model_name='SIMPLE_RADIAL',params=params,camera_id=13)
    model = SimpleNamespace(cameras={13:camera})
    assert check_saved_intrinsics(model,{13:params.tolist()})['maximum_parameter_change'] == 0
    camera.params = params + np.array([.00001,0,0,0])
    with pytest.raises(ValueError, match='changed fixed'): check_saved_intrinsics(model,{13:params.tolist()})


def test_before_after_comparison_cannot_invent_a_missing_joint_span():
    from scripts.evaluate_fixed_intrinsics import matched_pair_comparison
    point = dict(image_a='frame_00024.png', image_b='frame_00027.png',
                 relative_rotation_error_deg=24.77, translation_direction_error_deg=34.6,
                 relative_length_ratio=1.496, candidate_length_model_units=6.78, sensor_length_m=.566)
    old = dict(selected_pairs=[point], transition_anchor_comparisons=[], adjacent=[])
    missing = dict(selected_pairs=[], transition_anchor_comparisons=[], adjacent=[])
    assert matched_pair_comparison(old,missing) == []
    new = copy.deepcopy(old); new['selected_pairs'][0]['relative_rotation_error_deg'] = 5.2
    result = matched_pair_comparison(old,new)
    assert result[0]['before']['relative_rotation_error_deg'] == 24.77
    assert result[0]['after']['relative_rotation_error_deg'] == 5.2


@pytest.mark.parametrize('encoding', ['utf-8','utf-16'])
def test_solver_warning_count_accepts_both_windows_and_native_logs(tmp_path, encoding):
    from scripts.evaluate_fixed_intrinsics import solver_warning_count
    path = tmp_path/'native.log'
    path.write_text('info\nLinear solver failure.\nmore info\nLinear solver failure.\n',encoding=encoding)
    assert solver_warning_count(path) == 2
