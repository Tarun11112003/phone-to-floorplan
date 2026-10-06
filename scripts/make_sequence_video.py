"""Encode calibrated sequence RGB images into a video for input-path testing."""
import argparse
import json
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fps", type=float, default=6.0)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    camera = manifest["intrinsics"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio_ffmpeg.write_frames(str(args.output), (camera["width"], camera["height"]), fps=args.fps, quality=9, codec="libx264", pix_fmt_in="rgb24", pix_fmt_out="yuv420p")
    writer.send(None)
    for frame in manifest["frames"]:
        with Image.open(args.manifest.parent / frame["rgb"]) as image:
            writer.send(np.asarray(image.convert("RGB")))
    writer.close()
    print(json.dumps({"output": str(args.output), "frames": len(manifest["frames"]), "fps": args.fps}, indent=2))
