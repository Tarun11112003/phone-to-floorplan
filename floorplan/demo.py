"""Make a fully known scene for a reproducible geometry smoke test."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

from .geometry import Camera


def _draw_room(target: Path, width_m: float, length_m: float, camera_x: float) -> list[list[float]]:
    camera = Camera(1000, 800, 700.0, 700.0, 500.0, 400.0, 1.6)
    polygon = [(0.0, 0.0), (width_m, 0.0), (width_m, length_m), (0.0, length_m)]
    corners = [list(camera.project_floor((x - camera_x, y + 4.0))) for x, y in polygon]
    image = Image.new("RGB", (camera.width, camera.height), (218, 230, 237))
    draw = ImageDraw.Draw(image)
    draw.polygon([tuple(p) for p in corners], fill=(180, 164, 135), outline=(44, 67, 72), width=5)
    back_left, back_right = corners[3], corners[2]
    draw.rectangle((int(back_left[0] + 35), 190, int(back_right[0] - 35), 295), fill=(220, 232, 238), outline=(47, 68, 76), width=5)
    draw.line([tuple(corners[0]), tuple(corners[3])], fill=(42, 63, 72), width=5)
    draw.line([tuple(corners[1]), tuple(corners[2])], fill=(42, 63, 72), width=5)
    draw.text((30, 30), "Synthetic room: review the red floor corners in the evidence image", fill=(20, 43, 57))
    image.save(target)
    return corners


def make_demo(destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    corner_a = _draw_room(destination / "room_a.png", 4.0, 3.0, 2.0)
    corner_b = _draw_room(destination / "room_b.png", 3.0, 3.0, 1.5)
    video = destination / "room_b.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-loop", "1", "-i", str(destination / "room_b.png"), "-t", "3", "-pix_fmt", "yuv420p", str(video)], check=True, capture_output=True, text=True)
    base_camera = {"width": 1000, "height": 800, "fx": 700.0, "fy": 700.0, "cx": 500.0, "cy": 400.0, "height_m": 1.6}
    manifest = {
        "schema_version": 1,
        "rooms": [
            {"id": "room_a", "label": "Room A", "source": {"type": "image", "path": "room_a.png"}, "camera": base_camera, "floor_corners_px": corner_a, "ceiling_height_m": 2.7, "openings": [{"edge_index": 1, "start_fraction": 1 / 3, "end_fraction": 2 / 3, "height_m": 2.1}]},
            {"id": "room_b", "label": "Room B", "source": {"type": "video", "path": "room_b.mp4", "frame_time_s": 1}, "camera": base_camera, "floor_corners_px": corner_b, "ceiling_height_m": 2.7, "openings": [{"edge_index": 3, "start_fraction": 1 / 3, "end_fraction": 2 / 3, "height_m": 2.1}]},
        ],
        "stitches": [{"room_id": "room_b", "target_room_id": "room_a", "source_points": [[0, 1], [0, 2]], "target_points": [[4, 1], [4, 2]]}],
    }
    manifest_path = destination / "project.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (destination / "ground_truth.json").write_text(json.dumps({"room_a": [[0, 0], [4, 0], [4, 3], [0, 3]], "room_b": [[4, 0], [7, 0], [7, 3], [4, 3]]}, indent=2), encoding="utf-8")
    return manifest_path
