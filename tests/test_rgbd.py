import numpy as np
import pytest
import json
from PIL import Image

from floorplan.evaluation import dimension_metrics
from floorplan.rgbd import _backproject, _relative_pose, rectangle_from_planes, reconstruct_rgbd


def test_evaluation_preserves_scale_error_and_rejects_non_rectangles():
    metrics = dimension_metrics(np.array([[0, 0], [4.1, 0], [4.1, 3], [0, 3]]), np.array([4.0, 3.0]))
    assert metrics["max_dimension_error_m"] == pytest.approx(0.1)
    assert not metrics["dimension_target_met_on_this_case"]
    with pytest.raises(ValueError):
        dimension_metrics(np.array([[0, 0], [4, 0], [3, 3], [0, 3]]), np.array([4.0, 3.0]))


def test_wall_proposal_requires_observed_opposing_planes():
    walls = [
        {"normal": [1, 0, 0], "offset": 2.0, "support": 500},
        {"normal": [1, 0, 0], "offset": -3.0, "support": 600},
        {"normal": [0, 0, 1], "offset": 1.0, "support": 500},
        {"normal": [0, 0, 1], "offset": -3.0, "support": 500},
    ]
    corners, _ = rectangle_from_planes(walls)
    lengths = np.linalg.norm(np.roll(corners, -1, axis=0) - corners, axis=1)
    assert sorted(lengths) == pytest.approx([4, 4, 5, 5])
    with pytest.raises(ValueError):
        rectangle_from_planes(walls[:3])


def test_rgbd_pose_recovers_metric_camera_motion():
    cv2 = pytest.importorskip("cv2")
    rng = np.random.default_rng(71)
    k = np.array([[480, 0, 320], [0, 480, 240], [0, 0, 1]], dtype=float)
    xyz = rng.uniform([-1.0, -0.7, 2.0], [1.0, 0.7, 5.0], (100, 3))
    rotation, _ = cv2.Rodrigues(np.array([0.01, -0.03, 0.015]))
    translation = np.array([0.12, -0.02, 0.05])
    target = xyz @ rotation.T + translation
    def project(points):
        projected = points @ k.T
        return projected[:, :2] / projected[:, 2:]
    descriptors = rng.normal(size=(100, 128)).astype(np.float32)
    before = (project(xyz), descriptors, xyz[:, 2])
    after = (project(target), descriptors.copy(), target[:, 2])
    recovered, quality = _relative_pose(before, after, k, cv2)
    assert quality["metric_inliers"] == 100
    assert np.allclose(recovered[:3, :3], rotation, atol=1e-5)
    assert recovered[:3, 3] == pytest.approx(translation, abs=1e-5)
    assert np.allclose(_backproject(before[0], before[2], k), xyz)


def test_featureless_capture_reports_failure_and_emits_no_plan(tmp_path):
    pytest.importorskip("cv2")
    Image.fromarray(np.full((64, 64, 3), 128, dtype=np.uint8)).save(tmp_path / "rgb.png")
    Image.fromarray(np.full((64, 64), 5000, dtype=np.uint16)).save(tmp_path / "depth.png")
    manifest = {"intrinsics": {"width": 64, "height": 64, "fx": 60, "fy": 60, "cx": 32, "cy": 32}, "depth_scale": 5000, "frames": [{"id": i, "rgb": "rgb.png", "depth": "depth.png"} for i in range(2)]}
    source = tmp_path / "sequence.json"
    source.write_text(json.dumps(manifest), encoding="utf-8")
    result = reconstruct_rgbd(source, tmp_path / "result")
    assert result["status"] == "no_tracking"
    assert result["tracked_frames"] == 0
    assert not (tmp_path / "result" / "plan.json").exists()


def test_tracking_recovers_after_blank_frame_without_integrating_it(tmp_path):
    pytest.importorskip('cv2')
    rng = np.random.default_rng(321)
    Image.fromarray(rng.integers(0,256,(192,192,3),dtype=np.uint8)).save(tmp_path/'textured.png')
    Image.fromarray(np.full((192,192,3),128,dtype=np.uint8)).save(tmp_path/'blank.png')
    Image.fromarray(np.full((192,192),5000,dtype=np.uint16)).save(tmp_path/'depth.png')
    manifest = dict(intrinsics=dict(width=192,height=192,fx=180,fy=180,cx=96,cy=96), depth_scale=5000,
                    frames=[dict(id=i,rgb=name,depth='depth.png') for i,name in enumerate(['textured.png','blank.png','textured.png'])])
    source = tmp_path/'sequence.json'
    source.write_text(json.dumps(manifest),encoding='utf-8')
    result = reconstruct_rgbd(source,tmp_path/'result')
    assert result['tracked_frames'] == 2
    assert result['tracking_failure'] is None
    assert result['skipped_frames'][0]['frame_id'] == 1
    assert result['tracking_quality'][0]['recovered_after_skipped_frames'] == 1
    poses = json.loads((tmp_path/'result/trajectory.json').read_text())
    assert [p['frame_id'] for p in poses] == [0,2]
