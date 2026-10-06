"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image

from .demo import make_demo
from .pipeline import run_project


def _evaluate(plan_path: Path, truth_path: Path) -> dict:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    corner_errors = []
    dimension_errors = []
    area_errors = []
    for room in plan["rooms"]:
        if room["metric_status"] == "unscaled":
            raise ValueError(f"Cannot evaluate metric dimensions for unscaled room {room['id']}")
        actual = np.asarray(room["corners"], dtype=float)
        expected = np.asarray(truth[room["id"]], dtype=float)
        if actual.shape != expected.shape:
            raise ValueError(f"Ground truth for {room['id']} has a different number of corners")
        corner_errors.extend(np.linalg.norm(actual - expected, axis=1).tolist())
        actual_edges = np.linalg.norm(np.roll(actual, -1, axis=0) - actual, axis=1)
        expected_edges = np.linalg.norm(np.roll(expected, -1, axis=0) - expected, axis=1)
        dimension_errors.extend(np.abs(actual_edges - expected_edges).tolist())
        area_actual = 0.5 * abs(np.dot(actual[:, 0], np.roll(actual[:, 1], -1)) - np.dot(actual[:, 1], np.roll(actual[:, 0], -1)))
        area_expected = 0.5 * abs(np.dot(expected[:, 0], np.roll(expected[:, 1], -1)) - np.dot(expected[:, 1], np.roll(expected[:, 0], -1)))
        area_errors.append(float(abs(area_actual - area_expected)))
    return {
        "corner_count": len(corner_errors),
        "median_corner_error_m": float(np.median(corner_errors)),
        "p95_corner_error_m": float(np.percentile(corner_errors, 95)),
        "max_corner_error_m": float(np.max(corner_errors)),
        "dimension_count": len(dimension_errors),
        "p95_dimension_error_m": float(np.percentile(dimension_errors, 95)),
        "max_area_error_m2": max(area_errors),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditable photo/video-to-floor-plan demo")
    commands = parser.add_subparsers(dest="command", required=True)
    unified = commands.add_parser('reconstruct', help='Unified calibrated photos/video/LiDAR capture workflow')
    unified.add_argument('manifest',type=Path)
    unified.add_argument('--out',required=True,type=Path)
    intake = commands.add_parser('prepare-capture',help='Normalize stock phone photos, video or Stray Scanner export')
    intake.add_argument('--tier',choices=['photos','video','lidar'],required=True)
    intake.add_argument('--source',required=True,type=Path)
    intake.add_argument('--out',required=True,type=Path)
    intake.add_argument('--max-frames',type=int,default=300,help='LiDAR frame budget, sampled uniformly')
    capture = commands.add_parser('run-capture',help='Prepare and reconstruct a raw capture in one command')
    capture.add_argument('--tier',choices=['photos','video','lidar'],required=True)
    capture.add_argument('--source',required=True,type=Path)
    capture.add_argument('--out',required=True,type=Path)
    capture.add_argument('--max-frames',type=int,default=300,help='LiDAR frame budget, sampled uniformly')
    benchmark = commands.add_parser('benchmark',help='Run a suite and independently evaluate all results')
    benchmark.add_argument('suite',type=Path)
    benchmark.add_argument('--out',required=True,type=Path)
    stitch = commands.add_parser('stitch-captures',help='Verify overlap and join independent RGB-D run directories')
    stitch.add_argument('runs',nargs='+',type=Path)
    stitch.add_argument('--out',required=True,type=Path)
    demo = commands.add_parser("make-demo", help="Create two synthetic connected rooms, one photo and one MP4")
    demo.add_argument("directory", type=Path)
    run = commands.add_parser("run", help="Reconstruct a documented project manifest")
    run.add_argument("manifest", type=Path)
    run.add_argument("output", type=Path)
    evaluation = commands.add_parser("evaluate", help="Evaluate against independent corner coordinates")
    evaluation.add_argument("plan", type=Path)
    evaluation.add_argument("ground_truth", type=Path)
    polygons = commands.add_parser('evaluate-plan',help='Evaluate general room polygons with one global rigid alignment')
    polygons.add_argument('plan',type=Path)
    polygons.add_argument('reference',type=Path)
    polygons.add_argument('--out',required=True,type=Path)
    polygons.add_argument('--alignment',choices=['rigid','identity'],default='rigid')
    assignment = commands.add_parser('evaluate-assignment',help='Score stated assignment gates; missing outputs fail')
    assignment.add_argument('plan',type=Path)
    assignment.add_argument('reference',type=Path)
    assignment.add_argument('--tier',choices=['photos','video','lidar'],required=True)
    assignment.add_argument('--out',required=True,type=Path)
    repeat = commands.add_parser('evaluate-repeatability',help='Compare two independently captured plans and surveyed truth')
    repeat.add_argument('first',type=Path)
    repeat.add_argument('second',type=Path)
    repeat.add_argument('reference',type=Path)
    repeat.add_argument('--out',required=True,type=Path)
    frame = commands.add_parser("sample-video", help="Extract a frame to inspect or annotate")
    frame.add_argument("video", type=Path)
    frame.add_argument("image", type=Path)
    frame.add_argument("--time", type=float, default=1.0, help="Time in seconds")
    sfm = commands.add_parser("reconstruct-rgb", help="Optional COLMAP reconstruction from overlapping RGB media")
    sfm.add_argument("source", type=Path, help="Photo directory or video file")
    sfm.add_argument("output", type=Path, help="Fresh output directory")
    sfm.add_argument("--fps", type=float, default=2.0)
    sfm.add_argument("--max-frames", type=int, default=40)
    sfm.add_argument("--camera-model", default="SIMPLE_RADIAL")
    sfm.add_argument("--camera-params", default="", help="Comma-separated COLMAP camera parameters, when measured")
    sfm.add_argument("--matching", choices=["auto", "sequential", "exhaustive"], default="auto")
    icl = commands.add_parser("benchmark-icl", help="Idealized LiDAR-style benchmark against ICL-NUIM room mesh")
    icl.add_argument("archive", type=Path, help="ICL-NUIM living_room_obj_mtl.tar.gz")
    icl.add_argument("output", type=Path)
    icl.add_argument("--seed", type=int, default=42)
    rgbd = commands.add_parser("reconstruct-rgbd", help="Estimate poses and a rectangular room proposal from RGB-D pairs")
    rgbd.add_argument("manifest", type=Path)
    rgbd.add_argument("output", type=Path)
    rgbd.add_argument("--max-frames", type=int)
    args = parser.parse_args()
    if args.command == 'reconstruct':
        from .workflow import reconstruct
        ledger = reconstruct(args.manifest,args.out)
        print(json.dumps({'run_id':ledger['run_id'],'result':ledger['result'],'runtime_s':ledger['runtime_s']},indent=2))
        if ledger['result']['status'] == 'failed':
            raise SystemExit(1)
    elif args.command in {'prepare-capture','run-capture'}:
        from .ingest import prepare_capture
        if args.command == 'run-capture':
            if args.out.exists() and any(args.out.iterdir()):
                raise FileExistsError(f'Use a fresh output directory: {args.out}')
            manifest = prepare_capture(args.tier,args.source,args.out/'intake',args.max_frames)
            from .workflow import reconstruct
            ledger = reconstruct(manifest,args.out/'result')
            print(json.dumps({'capture':str(manifest),'run':str(args.out/'result'/'run.json'),
                              'status':ledger['result']['status'],
                              'floor_plan_ready':ledger['result'].get('floor_plan_ready',False),
                              'plan':str(args.out/'result'/'plan.json') if (args.out/'result'/'plan.json').exists() else None},indent=2))
            if not ledger['result'].get('floor_plan_ready',False):
                raise SystemExit(1)
        else:
            print(json.dumps({'manifest':str(prepare_capture(args.tier,args.source,args.out,args.max_frames))},indent=2))
    elif args.command == 'evaluate-assignment':
        from .assignment_gates import evaluate_assignment
        metrics=evaluate_assignment(json.loads(args.plan.read_text(encoding='utf-8')),
                                    json.loads(args.reference.read_text(encoding='utf-8')),args.tier)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(metrics,indent=2),encoding='utf-8')
        print(json.dumps({key:metrics[key] for key in ('evaluator_version','tier','known_gates_pass','assignment_complete','pending_specifications')},indent=2))
    elif args.command == 'evaluate-repeatability':
        from .repeatability import evaluate_repeatability
        metrics=evaluate_repeatability(*[json.loads(path.read_text(encoding='utf-8'))
                                         for path in (args.first,args.second,args.reference)])
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(metrics,indent=2),encoding='utf-8')
        print(json.dumps({key:metrics[key]['gate'] for key in ('wall_repeatability','ceiling_repeatability','ceiling_accuracy')},indent=2))
    elif args.command == 'evaluate-plan':
        from .benchmark import evaluate_polygons
        metrics=evaluate_polygons(json.loads(args.plan.read_text(encoding='utf-8')),json.loads(args.reference.read_text(encoding='utf-8')),args.alignment)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(metrics,indent=2),encoding='utf-8')
        print(json.dumps(metrics,indent=2))
    elif args.command == 'stitch-captures':
        from .stitching import stitch_runs
        print(json.dumps(stitch_runs(args.runs,args.out),indent=2))
    elif args.command == 'benchmark':
        from .benchmark import run_suite
        print(json.dumps(run_suite(args.suite,args.out),indent=2))
    elif args.command == "make-demo":
        print(make_demo(args.directory))
    elif args.command == "run":
        plan = run_project(args.manifest, args.output)
        print(json.dumps({"rooms": len(plan["rooms"]), "output": str(args.output), "metric_status": [room["metric_status"] for room in plan["rooms"]]}, indent=2))
    elif args.command == "sample-video":
        if args.time < 0 or not args.video.is_file():
            parser.error("Video must exist and time must be nonnegative")
        args.image.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-ss", str(args.time), "-i", str(args.video), "-frames:v", "1", str(args.image)], check=True, capture_output=True, text=True)
        with Image.open(args.image) as extracted:
            print(json.dumps({"image": str(args.image), "width": extracted.width, "height": extracted.height}, indent=2))
    elif args.command == "reconstruct-rgb":
        from .sfm import reconstruct_rgb
        print(json.dumps(reconstruct_rgb(args.source, args.output, args.fps, args.max_frames, args.camera_model, args.camera_params, args.matching), indent=2))
    elif args.command == "benchmark-icl":
        from .icl_benchmark import run_icl_benchmark
        print(json.dumps(run_icl_benchmark(args.archive, args.output, seed=args.seed), indent=2))
    elif args.command == "reconstruct-rgbd":
        from .rgbd import reconstruct_rgbd
        result = reconstruct_rgbd(args.manifest, args.output, args.max_frames)
        print(json.dumps({key: value for key, value in result.items() if key not in {"planes", "tracking_quality", "plan_metadata"}}, indent=2))
    else:
        print(json.dumps(_evaluate(args.plan, args.ground_truth), indent=2))


if __name__ == "__main__":
    main()
