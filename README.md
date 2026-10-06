# Cozmo floor-plan take-home demo

**Exact-brief audit (2026-10-06):** the supplied assignment is broader than the V3
prototype. Read the [requirement-by-requirement compliance audit](docs/ASSIGNMENT_COMPLIANCE.md)
and [updated implementation / incremental E2E plan](docs/ASSIGNMENT_UPDATE_PLAN.md).
V3's controlled passes use an earlier custom evaluator and do not establish
assignment compliance, especially for 2–8 photos per room, ceiling height,
calibrated intervals, damage/scope outputs and the required physical benchmark.

The assignment-specific work now includes a [stock capture protocol](docs/CAPTURE_PROTOCOL.md),
[device matrix](docs/DEVICE_MATRIX.md), a raw-media intake command and a provisional
gate evaluator. [Incremental E2E results](docs/ASSIGNMENT_E2E_STATUS.md) record
the actual success and failure statuses. These additions make failures inspectable; they do not make the
three-tier accuracy claim valid.

```powershell
& .\.venv\Scripts\python.exe -m pip install -e ".[sfm,rgbd,mapping,capture,test]"
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier photos --source captures\property_photos --out runs\photos_01
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier video --source captures\walkthrough.mov --out runs\video_01
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier lidar --source captures\stray_export --out runs\lidar_01
& .\.venv\Scripts\python.exe -m floorplan.cli evaluate-assignment runs\lidar_01\result\plan.json truth\property.json --tier lidar --out runs\lidar_01\gates.json
& .\.venv\Scripts\python.exe -m floorplan.cli evaluate-repeatability runs\repeat_a\result\plan.json runs\repeat_b\result\plan.json truth\property.json --out runs\repeatability.json
```

`run-capture` creates `intake/capture.json`, `intake/intake.json` and
`result/run.json` even when reconstruction fails after intake. It exits nonzero
unless a ready plan exists. The published JSON schema and earlier Round 1 rules
referenced in the brief were not included in the supplied HTML, so the evaluator
is versioned as provisional. The exact benchmark still requires a surveyed
three-room property, repeated independent captures and consumer-app exports.
On LiDAR runs where walls are observed but a room stays open,
`result/layout_diagnostic.svg` shows the supported segments and camera path.
The supplied `datasets/Given_dataset/` has been exercised as a real raw-input
checkpoint; its three scans currently yield diagnostic failures rather than a
certified plan. Results and causes are in the incremental E2E report.

This repository is a **CPU, code-only research prototype** for restoration floor plans. It includes calibrated RGB-D mapping, actual phone LiDAR ingestion, concave multiroom layouts, verified capture stitching, measured-scale RGB multi-view stereo, and auditable SVG/DXF/JSON/CSV outputs.

The full three-tier field-accuracy requirement is **not yet satisfied**. On the controlled two-room fixture, photos, video, and simulated LiDAR now pass wall, corner, opening, coverage, and topology targets; RGB wall P95 error is **0.57–0.87 cm**. One real-phone room measures about **2.0 cm P95** against a provisional laser-derived reference. These results do not establish accuracy across arbitrary properties.

## Current workflow

See the [V3 implementation guide and diagrams](docs/V3_IMPLEMENTATION.md), [measured results](docs/V3_RESULTS.md), and [accepted roadmap](docs/IMPLEMENTATION_PLAN.md). V2 remains as a historical baseline.

```powershell
& .\.venv\Scripts\python.exe -m pip install -e ".[sfm,rgbd,mapping,evaluation,test]"
& .\.venv\Scripts\python.exe scripts\install_openmvs.py
& .\.venv\Scripts\python.exe -m floorplan.cli reconstruct examples\icl_rgbd.json --out demo\my_run
& .\.venv\Scripts\python.exe -m floorplan.cli benchmark examples\public_benchmark.json --out demo\my_benchmark
& .\.venv\Scripts\python.exe -m pytest -q
```

Output directories must be fresh. Download/preparation steps and the controlled multiroom demo are documented in the implementation guide and dataset notes. The sections below preserve the original baseline commands; use `reconstruct` above for the new common workflow.

Read the [architecture and flow charts](docs/ARCHITECTURE.md), [dataset research](docs/DATASETS.md), [measured benchmark results](docs/BENCHMARK_RESULTS.md), and [personal decisions](DESIGN_NOTES.md).

![Architecture](docs/figures/architecture.png)

## Legacy rectangular RGB-D benchmark

The ICL-NUIM archives and 177-frame subset are already downloaded locally. On a fresh checkout, follow [dataset acquisition](docs/DATASETS.md) first. This path estimates camera poses and walls without supplied corners or reference poses. Use a fresh output directory:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e ".[rgbd,evaluation,test]"
& .\.venv\Scripts\python.exe -m floorplan.cli reconstruct-rgbd datasets\icl_nuim\trajectory2\sequence.json demo\my_rgbd_run
& .\.venv\Scripts\python.exe scripts\evaluate_icl.py demo\my_rgbd_run\plan.json datasets\icl_nuim\living_room_obj_mtl.tar.gz demo\my_rgbd_run\evaluation.json
```

The current output is [demo/icl_rgbd_refined/plan.svg](demo/icl_rgbd_refined/plan.svg). The calibrated depth supplies metric scale. This baseline assumes a single rectangular room and an approximately level starting camera. It is tested on synthetic RGB-D; it is not yet a native iPhone LiDAR importer.

## Assisted two-room quick start

This separate baseline uses marked floor corners in a JSON manifest, camera calibration, measured scale, and doorway anchors. It demonstrates multi-room projection/stitching/export and does not infer corners from arbitrary RGB images.

Use Python 3.10 or newer. On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e .
& .\.venv\Scripts\python.exe -m floorplan.cli make-demo demo
& .\.venv\Scripts\python.exe -m floorplan.cli run demo\project.json demo\output
& .\.venv\Scripts\python.exe -m floorplan.cli evaluate demo\output\plan.json demo\ground_truth.json
```

The generated `demo/output/plan.svg` opens in a browser. `plan.dxf` opens in CAD software. `REPORT.md` links to overlays of the marked source images.

This is a synthetic geometry test: the camera views and corner annotations are generated from the same known room geometry. Its near-zero error verifies transforms and export, **not** accuracy on real properties.

## Assisted workflow on your own media

1. Put photos or videos in a project directory, and copy `demo/project.json` as a starting manifest.
2. For each room, set `source.type` to `image` or `video` and provide the relative media path. For video, set `frame_time_s` to the desired time in seconds. The program extracts that frame with FFmpeg supplied by `imageio-ffmpeg`.
3. Enter the image width, height, focal lengths `fx`/`fy`, principal point `cx`/`cy`, and camera `yaw_deg`/`pitch_deg` if the camera was not level. These must describe the **same frame orientation and resolution** that the program reads. Record the centre of each visible wall-floor junction in `floor_corners_px`, walking around the room boundary in order. The numbered overlay lets you check these selections.
4. Supply `camera.height_m` if measured, or `reference_edge: {"edge_index": 0, "length_m": 4.0}` for a known edge. A reference edge uses the boundary segment from corner `edge_index` to the following corner. Without either, lengths and quantities are withheld from metric output.
5. If two rooms are observed at a shared doorway, provide at least two corresponding points in each room's local floor coordinates under `stitches`. Example: `source_points` `[[0,1],[0,2]]` in room B and `target_points` `[[4,1],[4,2]]` in room A. Both rooms need metric scale. Disconnected rooms remain independent.
6. Run `python -m floorplan.cli run path\to\project.json path\to\output`.

The manifest camera is at local floor position `(0,0)` and its local `+Y` axis points forward when yaw and pitch are zero. Positive pitch points upward. Corners must be below the horizon so their viewing rays hit the floor. `height_m` is the lens centre above the floor, not ceiling height. `ceiling_height_m` is optional and used only for wall area. Openings are described by `edge_index`, fractions along that edge, and `height_m`; they are deducted from net wall area.

The output `metric_status` is `reference_scaled` when a measured camera height or edge length is provided, and `unscaled` otherwise. `reference_scaled` describes where the scale came from; it is **not** a validation certificate. Source geometry, camera data, and reference measurements all need independent checks before estimating quantities on a real job.

When rooms have no stitching evidence, the SVG displays them as separate panels marked “placement unknown,” and the export writes one DXF per room. A combined `plan.dxf` is produced only when all rooms have a shared placement.

## Included real video dataset

`datasets/tum_freiburg1_room/rgb.avi` is the 13.8 MB RGB movie from the [TUM RGB-D `freiburg1_room` sequence](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/download). The matching ground-truth trajectory is also included. They are useful for checking video decoding, frame extraction, tracking experiments, and capture quality. Its [dataset page](https://cvg.cit.tum.de/data/datasets/rgbd-dataset) states CC BY 4.0 for data unless otherwise noted. The movie has no floor-corner annotations or certified room dimensions, so it is not used to claim floor-plan measurement accuracy. Attribution and provenance are in `datasets/tum_freiburg1_room/SOURCE.md`.

To inspect a real frame, run:

```powershell
& .\.venv\Scripts\python.exe -m floorplan.cli sample-video datasets\tum_freiburg1_room\rgb.avi demo\tum_frame.png --time 5
```

An optional RGB reconstruction experiment uses [PyCOLMAP](https://colmap.github.io/pycolmap/index.html):

```powershell
& .\.venv\Scripts\python.exe -m pip install -e ".[sfm]"
& .\.venv\Scripts\python.exe -m floorplan.cli reconstruct-rgb datasets\tum_freiburg1_room\rgb.avi demo\tum_sfm --fps 2 --max-frames 100
```

This writes a COLMAP sparse model, `sparse.ply`, and `sfm_summary.json`. It estimates camera poses and sparse 3D structure from RGB only. The model has **unknown metric scale**, and sparse points are not a floor plan. `partial` now means fewer than 90% of selected frames entered the largest model. Keep the SfM experiment separate from the measured-corner plan until camera poses, scale, and structural geometry can be aligned and validated. `--matching exhaustive` compares every pair and improved the short ICL video experiment from 55/89 to 89/89 registered frames; it has quadratic matching cost.

In the local TUM experiment, the largest model registered 10 of 91 extracted frames. This is partial coverage and does not provide a complete room plan. The experiment is recorded in `DESIGN_NOTES.md`.

For a camera with known intrinsics, pass `--camera-model` and `--camera-params` in [COLMAP's parameter order](https://colmap.github.io/cameras.html). For example, the [TUM Freiburg 1 RGB calibration](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/file_formats) can be approximated with `--camera-model OPENCV --camera-params '517.3,516.5,318.6,255.3,0.2624,-0.9531,-0.0054,0.0026'`. This eight-parameter model omits TUM's reported `k3` term. In the local test it registered 10 of 91 frames, so calibration alone did not resolve the coverage gap.

## Test

```powershell
& .\.venv\Scripts\python.exe -m pip install -e ".[test]"
& .\.venv\Scripts\python.exe -m pytest -q
```

The synthetic test covers image and video ingestion, ground projection, room alignment, metric quantities, and export. The TUM video is a separate real-media decoding test.
