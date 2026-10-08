"""Extract a small, evenly sampled ICL-NUIM RGB-D sequence safely."""
from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path, PurePosixPath


def prepare(archive: Path, output: Path, stride: int = 5) -> dict:
    if stride < 1:
        raise ValueError("stride must be positive")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Use a fresh extraction directory to avoid mixing frame strides')
    output.mkdir(parents=True, exist_ok=True)
    count = 0
    with tarfile.open(archive, "r:gz") as packed:
        for member in packed:
            name = PurePosixPath(member.name)
            if not member.isfile() or name.is_absolute() or ".." in name.parts:
                continue
            is_frame = len(name.parts) == 2 and name.parts[0] in {"rgb", "depth"} and name.suffix == ".png" and name.stem.isdigit()
            is_metadata = len(name.parts) == 1 and (name.name == 'associations.txt' or name.name.endswith('.gt.freiburg'))
            if (is_frame and int(name.stem) % stride == 0) or is_metadata:
                target = output.joinpath(*name.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with packed.extractfile(member) as source:
                    target.write_bytes(source.read())
                count += 1
    frames = sorted((output / "rgb").glob("*.png"), key=lambda path: int(path.stem))
    manifest = {
        "schema_version": 1, "source": f"ICL-NUIM synthetic RGB-D: {archive.name}",
        "intrinsics": {"width": 640, "height": 480, "fx": 481.2, "fy": 480.0, "cx": 319.5, "cy": 239.5},
        "coordinate_convention": "OpenCV camera axes: x right, y down, z forward; native negative-fy convention converted",
        "depth_scale": 5000.0, "depth_max_m": 8.0,
        "frames": [{"id": int(path.stem), "rgb": "rgb/" + path.name, "depth": "depth/" + path.name} for path in frames],
    }
    (output / "sequence.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"extracted_files": count, "frame_pairs": len(frames), "manifest": str(output / "sequence.json")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--stride", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.output, args.stride), indent=2))
