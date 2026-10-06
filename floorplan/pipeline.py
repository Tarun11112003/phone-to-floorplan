"""Reproducible floor-plan processing from annotated images and video frames."""

from __future__ import annotations

import csv
import html
import json
import subprocess
from pathlib import Path

import ezdxf
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

from .geometry import Camera, GeometryError, rigid_alignment, transform_points, validated_polygon


def _source_frame(room: dict, project_dir: Path, output_dir: Path) -> Path:
    source = room["source"]
    source_path = (project_dir / source["path"]).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if source["type"] == "image":
        return source_path
    if source["type"] != "video":
        raise ValueError(f"Unsupported source type: {source['type']}")
    target = output_dir / f"{room['id']}_frame.png"
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-ss", str(source.get("frame_time_s", 0)), "-i", str(source_path), "-frames:v", "1", str(target)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    if not target.exists():
        raise RuntimeError(f"No frame extracted from {source_path}")
    return target


def _overlay(frame: Path, corners: list[list[float]], target: Path) -> None:
    with Image.open(frame) as original:
        image = original.convert("RGB")
    draw = ImageDraw.Draw(image)
    points = [tuple(p) for p in corners]
    draw.line(points + points[:1], fill=(255, 40, 30), width=4)
    for index, (x, y) in enumerate(points):
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(255, 40, 30))
        draw.text((x + 8, y - 8), str(index), fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    image.save(target)


def _room_local(room: dict, project_dir: Path, output_dir: Path) -> dict:
    frame = _source_frame(room, project_dir, output_dir)
    camera = Camera.from_dict(room["camera"])
    with Image.open(frame) as image:
        if image.size != (camera.width, camera.height):
            raise GeometryError(f"{room['id']}: camera size {camera.width}x{camera.height} differs from frame {image.size}")
    corners = room["floor_corners_px"]
    if not isinstance(corners, list) or len(corners) < 3:
        raise GeometryError(f"{room['id']}: provide at least three floor corners")
    points = [camera.floor_point(pixel) for pixel in corners]
    validated_polygon(points)
    # A single image does not establish a building-wide translation. Give each
    # room a stable local origin at the lower-left of its floor bounding box.
    min_x = min(x for x, _ in points)
    min_y = min(y for _, y in points)
    points = [(x - min_x, y - min_y) for x, y in points]
    status = "reference_scaled" if "height_m" in room["camera"] else "unscaled"
    reference = room.get("reference_edge")
    if reference:
        index = int(reference["edge_index"])
        if index < 0 or index >= len(points):
            raise GeometryError(f"{room['id']}: invalid reference edge index")
        measured = float(reference["length_m"])
        inferred = float(np.linalg.norm(np.asarray(points[index]) - np.asarray(points[(index + 1) % len(points)])))
        if measured <= 0 or inferred <= 0:
            raise GeometryError(f"{room['id']}: invalid reference measurement")
        scale = measured / inferred
        points = [(x * scale, y * scale) for x, y in points]
        status = "reference_scaled"
    _overlay(frame, corners, output_dir / f"{room['id']}_evidence.png")
    return {
        "id": room["id"], "label": room.get("label", room["id"]),
        "local_corners": points, "corners": points,
        "metric_status": status, "ceiling_height_m": room.get("ceiling_height_m"),
        "openings": room.get("openings", []),
        "evidence_image": f"{room['id']}_evidence.png",
        "source_path": room["source"]["path"],
    }


def _apply_stitches(rooms: dict[str, dict], stitches: list[dict]) -> None:
    resolved = {next(iter(rooms))}
    pending = list(stitches)
    while pending:
        progress = False
        for stitch in pending[:]:
            source_id, target_id = stitch["room_id"], stitch["target_room_id"]
            if source_id not in rooms or target_id not in rooms:
                raise GeometryError("Stitch references an unknown room")
            if target_id not in resolved:
                continue
            if source_id in resolved:
                raise GeometryError(f"Multiple alignment paths for {source_id} are not supported in this demo")
            source = rooms[source_id]
            target = rooms[target_id]
            if source["metric_status"] == "unscaled" or target["metric_status"] == "unscaled":
                raise GeometryError("Both rooms need metric scale before stitching")
            target_local = np.asarray(stitch["target_points"], dtype=float)
            target_anchor = np.asarray(target["local_corners"], dtype=float)
            target_global = np.asarray(target["corners"], dtype=float)
            # Known local-to-global relation of the previously resolved target room.
            if len(target_anchor) < 2:
                raise GeometryError("Target room has too few corners")
            rotation_to_world, translation_to_world, _ = rigid_alignment(target_anchor.tolist(), target_global.tolist())
            target_points_world = target_local @ rotation_to_world + translation_to_world
            rotation, translation, residual = rigid_alignment(stitch["source_points"], target_points_world.tolist())
            if residual > 0.05:
                raise GeometryError(f"{source_id}: doorway anchors disagree by {residual:.3f} m RMS")
            source["corners"] = transform_points(source["local_corners"], rotation, translation)
            source["stitch_rms_m"] = residual
            resolved.add(source_id)
            pending.remove(stitch)
            progress = True
        if not progress:
            raise GeometryError("Stitch graph is disconnected or out of order")
    for room_id, room in rooms.items():
        if room_id not in resolved:
            room["placement"] = "independent"
        else:
            room["placement"] = "stitched" if room_id != next(iter(rooms)) else "origin"


def _quantities(room: dict) -> dict:
    if room["metric_status"] == "unscaled":
        return {"room_id": room["id"], "label": room["label"], "area_m2": None, "perimeter_m": None, "gross_wall_area_m2": None, "net_wall_area_m2": None}
    polygon = validated_polygon(room["corners"])
    area = float(polygon.area)
    perimeter = float(polygon.length)
    height = room["ceiling_height_m"]
    gross = perimeter * float(height) if height is not None else None
    opening_area = 0.0
    unknown_opening_height = False
    for opening in room["openings"]:
        index = int(opening["edge_index"])
        if index < 0 or index >= len(room["corners"]):
            raise GeometryError(f"{room['id']}: opening has invalid edge index")
        begin, end = float(opening["start_fraction"]), float(opening["end_fraction"])
        if opening.get("height_m") is None:
            unknown_opening_height = True
            if not 0 <= begin < end <= 1:
                raise GeometryError("Invalid opening fractions")
            continue
        opening_height = float(opening["height_m"])
        if not 0 <= begin < end <= 1 or opening_height <= 0 or (height is not None and opening_height > float(height)):
            raise GeometryError(f"{room['id']}: opening dimensions are invalid")
        edge = np.asarray(room["corners"][(index + 1) % len(room["corners"])]) - np.asarray(room["corners"][index])
        opening_area += float(np.linalg.norm(edge)) * (end - begin) * opening_height
    return {"room_id": room["id"], "label": room["label"], "area_m2": area, "perimeter_m": perimeter, "gross_wall_area_m2": gross, "net_wall_area_m2": gross - opening_area if gross is not None and not unknown_opening_height else None}


def _svg(rooms: list[dict], target: Path) -> None:
    placed = [room for room in rooms if room["placement"] != "independent"]
    independent = [room for room in rooms if room["placement"] == "independent"]
    groups = ([placed] if placed else []) + [[room] for room in independent]
    visual: dict[str, list[tuple[float, float]]] = {}
    offset = 0.0
    max_height = 0.0
    for group in groups:
        all_group_points = [point for room in group for point in room["corners"]]
        min_x, min_y = min(x for x, _ in all_group_points), min(y for _, y in all_group_points)
        max_x, max_y = max(x for x, _ in all_group_points), max(y for _, y in all_group_points)
        for room in group:
            visual[room["id"]] = [(x - min_x + offset, y - min_y) for x, y in room["corners"]]
        offset += max_x - min_x + 1.0
        max_height = max(max_height, max_y - min_y)
    scale = 120.0
    width = max(400, offset * scale + 120)
    height = max(300, max_height * scale + 120)
    def pt(point: tuple[float, float]) -> tuple[float, float]:
        return 60 + point[0] * scale, height - 60 - point[1] * scale
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">', '<rect width="100%" height="100%" fill="white"/>']
    for room in rooms:
        points = visual[room["id"]]
        polygon = validated_polygon(points)
        point_text = " ".join(f"{pt(p)[0]:.2f},{pt(p)[1]:.2f}" for p in points)
        lines.append(f'<polygon points="{point_text}" fill="#edf5fa" fill-opacity="0.55" stroke="#18364c" stroke-width="3"/>')
        for opening in room.get('openings', []):
            index=opening['edge_index']
            a,b=np.asarray(points[index]),np.asarray(points[(index+1)%len(points)])
            start=pt(a+(b-a)*opening['start_fraction']); end=pt(a+(b-a)*opening['end_fraction'])
            lines.append(f'<line x1="{start[0]:.2f}" y1="{start[1]:.2f}" x2="{end[0]:.2f}" y2="{end[1]:.2f}" stroke="white" stroke-width="7"/>')
            lines.append(f'<line x1="{start[0]:.2f}" y1="{start[1]:.2f}" x2="{end[0]:.2f}" y2="{end[1]:.2f}" stroke="#278366" stroke-width="2" stroke-dasharray="5 3"/>')
        cx, cy = pt((polygon.centroid.x, polygon.centroid.y))
        label = html.escape(room["label"])
        if room["placement"] == "independent":
            label += " (placement unknown)"
        lines.append(f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" font-family="Arial" font-size="18" fill="#17354c">{label}</text>')
        for index, start in enumerate(points):
            end = points[(index + 1) % len(points)]
            center = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            px, py = pt(center)
            length = float(np.linalg.norm(np.asarray(end) - np.asarray(start)))
            label = f"{length:.2f} m" if room["metric_status"] != "unscaled" else "unscaled"
            lines.append(f'<text x="{px:.1f}" y="{py - 7:.1f}" text-anchor="middle" font-family="Arial" font-size="13" fill="#b23b22" stroke="white" stroke-width="3" paint-order="stroke">{label}</text>')
    lines.append('</svg>')
    target.write_text("\n".join(lines), encoding="utf-8")


def _dxf(rooms: list[dict], target: Path) -> None:
    document = ezdxf.new("R2010")
    document.header["$INSUNITS"] = 6 if all(room["metric_status"] != "unscaled" for room in rooms) else 0
    model = document.modelspace()
    for room in rooms:
        model.add_lwpolyline(room["corners"], close=True, dxfattribs={"layer": "ROOM_WALL_FACES"})
        corners = np.asarray(room['corners'], float)
        for index, (start, end) in enumerate(zip(corners, np.roll(corners, -1, axis=0))):
            if room['metric_status'] != 'unscaled':
                dimension = model.add_aligned_dim(p1=tuple(start), p2=tuple(end), distance=0.22,
                    dxfattribs={'layer': 'DIMENSIONS'}, override={'dimtxt': 0.10, 'dimasz': 0.08, 'dimdec': 2})
                dimension.render()
            for opening in room.get('openings', []):
                if opening['edge_index'] == index:
                    a = start + (end-start) * opening['start_fraction']
                    b = start + (end-start) * opening['end_fraction']
                    model.add_line(tuple(a), tuple(b), dxfattribs={'layer': 'OBSERVED_OPENINGS', 'color': 3})
        polygon = validated_polygon(room["corners"])
        model.add_text(room["label"], dxfattribs={"height": 0.18, "insert": (polygon.centroid.x, polygon.centroid.y), "layer": "ROOM_LABELS"})
    document.saveas(target)


def run_project(manifest_path: Path, output_dir: Path) -> dict:
    manifest_path = manifest_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Expected schema_version 1")
    rooms: dict[str, dict] = {}
    for source_room in manifest["rooms"]:
        if source_room["id"] in rooms:
            raise ValueError("Room IDs must be unique")
        rooms[source_room["id"]] = _room_local(source_room, manifest_path.parent, output_dir)
    if not rooms:
        raise ValueError("Project contains no rooms")
    _apply_stitches(rooms, manifest.get("stitches", []))
    rows = [_quantities(room) for room in rooms.values()]
    plan = {"schema_version": 1, "units": "metres when metric_status is reference_scaled; otherwise arbitrary scale", "rooms": list(rooms.values()), "quantities": rows}
    (output_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    with (output_dir / "quantities.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    _svg(list(rooms.values()), output_dir / "plan.svg")
    if any(room["placement"] == "independent" for room in rooms.values()):
        combined_dxf = output_dir / "plan.dxf"
        if combined_dxf.exists():
            combined_dxf.unlink()
        for room in rooms.values():
            _dxf([room], output_dir / f"{room['id']}.dxf")
    else:
        _dxf(list(rooms.values()), output_dir / "plan.dxf")
    report = ["# Floor-plan run", "", f"Source manifest: `{manifest_path}`", "", "Dimensions are projected from marked floor corners. Metric dimensions require a measured camera height or reference edge.", ""]
    for room, row in zip(rooms.values(), rows):
        report.append(f"- {room['label']}: {room['metric_status']}, {room['placement']}; area {row['area_m2'] if row['area_m2'] is not None else 'unavailable'} m²; evidence [{room['evidence_image']}]({room['evidence_image']})")
    report.extend(["", "RoomPlan and learned depth inference are outside this code demo. Every wall corner in this run comes from the input annotations."])
    (output_dir / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return plan
