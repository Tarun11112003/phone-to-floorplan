import json
from pathlib import Path
from xml.etree import ElementTree

import ezdxf
import numpy as np
import pytest

from floorplan.cli import _evaluate
from floorplan.demo import make_demo
from floorplan.geometry import Camera, GeometryError, rigid_alignment, transform_points
from floorplan.pipeline import run_project


def test_floor_projection_and_horizon():
    camera = Camera(1000, 800, 700, 700, 500, 400, 1.6)
    point = (1.2, 5.0)
    pixel = camera.project_floor(point)
    assert camera.floor_point(pixel) == pytest.approx(point)
    with pytest.raises(GeometryError):
        camera.floor_point((500, 100))


def test_alignment_is_rigid_and_reports_conflict():
    source = [[0, 0], [0, 2], [1, 0]]
    target = [[4, 1], [4, 3], [5, 1]]
    rotation, translation, error = rigid_alignment(source, target)
    assert error < 1e-12
    assert np.allclose(transform_points(source, rotation, translation), target)
    bad_target = [[4, 1], [4, 3], [7, 1]]
    _, _, bad_error = rigid_alignment(source, bad_target)
    assert bad_error > 0.05


def test_full_image_video_and_export_demo(tmp_path: Path):
    manifest = make_demo(tmp_path / "capture")
    output = tmp_path / "result"
    plan = run_project(manifest, output)
    assert len(plan["rooms"]) == 2
    assert [row["area_m2"] for row in plan["quantities"]] == pytest.approx([12, 9])
    assert [row["net_wall_area_m2"] for row in plan["quantities"]] == pytest.approx([35.7, 30.3])
    metrics = _evaluate(output / "plan.json", manifest.parent / "ground_truth.json")
    assert metrics["max_corner_error_m"] < 1e-9
    assert metrics["p95_dimension_error_m"] < 1e-9
    assert (output / "room_b_frame.png").is_file()
    assert (output / "room_b_evidence.png").is_file()
    assert (output / "plan.svg").is_file()
    assert (output / "plan.dxf").is_file()
    ElementTree.parse(output / "plan.svg")
    dxf = ezdxf.readfile(output / "plan.dxf")
    assert dxf.header["$INSUNITS"] == 6
    assert len(dxf.modelspace().query("LWPOLYLINE")) == 2


def test_no_scale_withholds_quantities(tmp_path: Path):
    manifest_path = make_demo(tmp_path / "capture")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["rooms"] = manifest["rooms"][:1]
    manifest["rooms"][0]["camera"].pop("height_m")
    manifest["stitches"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    plan = run_project(manifest_path, tmp_path / "result")
    assert plan["rooms"][0]["metric_status"] == "unscaled"
    assert plan["quantities"][0]["area_m2"] is None
    assert ezdxf.readfile(tmp_path / "result" / "plan.dxf").header["$INSUNITS"] == 0


def test_disconnected_rooms_do_not_get_a_combined_cad_plan(tmp_path: Path):
    manifest_path = make_demo(tmp_path / "capture")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stitches"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "result"
    plan = run_project(manifest_path, output)
    assert plan["rooms"][1]["placement"] == "independent"
    assert not (output / "plan.dxf").exists()
    assert (output / "room_a.dxf").exists()
    assert (output / "room_b.dxf").exists()
    assert "placement unknown" in (output / "plan.svg").read_text(encoding="utf-8")
