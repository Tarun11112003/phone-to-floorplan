# Open-source investigation and adoption decisions

Updated 2026-10-06. These are engineering decisions for the code-only take-home.
Repository availability alone does not establish suitability or measurement accuracy.

The current geometry pipeline already executes [COLMAP](https://github.com/colmap/colmap)
for poses, [OpenMVS](https://github.com/cdcseacave/openMVS) for dense RGB geometry,
and [Open3D](https://github.com/isl-org/Open3D) for registration/point-cloud processing.
COLMAP documents a BSD license; OpenMVS carries AGPL-3.0. These dependencies and
their separate third-party terms must stay attributed when packaging a submission.
The table below focuses on additional candidates investigated in this increment.

| Project / primary source | Useful stage | Requirements and limitations | Decision |
| --- | --- | --- | --- |
| [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2), [indoor metric checkpoint](https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf) | Sparse-photo depth proposal | Small: 24.8M parameters, CPU supported; indoor metric variant trained on synthetic Hypersim. No camera poses or stitching. Learned scale requires independent evaluation. Upstream Small model Apache-2.0; larger variants CC-BY-NC-4.0. | Selected for a bounded CPU experiment. Do not replace sensor depth or label its predictions cm-accurate. |
| [RoomFormer](https://github.com/ywyue/RoomFormer) | Multiroom polygon proposal from top-down point-density image | MIT repository. Official environment Linux, Torch 1.9, CUDA 11.1, compiled deformable attention and rasterizer. Input is a reconstructed point cloud, not raw stills. | Useful second geometry backend on a GPU environment; not a drop-in Windows/CPU replacement. Preserve density-to-metric transform and independently check wall support. |
| [Floor-SP](https://github.com/woodfrog/floor-sp) | Room-boundary optimization | Sequential room-wise shortest paths, consistency and complexity objectives; legacy dependencies and upstream preprocessing. | Algorithm reference for future polygon optimization. Current bounded supported-cell implementation is original code; no upstream code copied. |
| [UniDepth](https://github.com/lpiccinelli-eth/UniDepth) | Monocular metric depth and camera inference | Upstream recommends Linux/CUDA; CC-BY-NC-4.0. Metric predictions do not establish survey accuracy. | Alternative research benchmark; lower priority than the small CPU model. Do not assume a company take-home automatically qualifies as noncommercial use. |
| [Grounded SAM 2](https://github.com/IDEA-Research/Grounded-SAM-2) | Text-conditioned image/video masks | Composite pipeline: check each detector, segmenter and checkpoint separately. Segmentation is not a validated damage diagnosis; shadows and decoration remain confounders. | Candidate replacement for experimental stain/crack masks after annotated indoor damage examples exist. Geometry projection and deduplication remain reusable. |
| [Prompt Depth Anything](https://github.com/DepthAnything/PromptDA) | RGB plus low-resolution depth refinement | Requires depth input, so belongs only in the LiDAR tier. Generated edges can alter measured boundaries. | Evaluate as an optional refinement against held-out sensor samples; never introduce it into a no-depth photo benchmark. |

## Licensing decision

Public and unlicensed are different from permissively licensed. GitHub explains
that absent a license the default rights are retained, while GitHub viewing/forking
rights are separate: [GitHub licensing documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
Use a permitted implementation/checkpoint with attribution; otherwise study the
published method and implement independently, or obtain the author's permission.
Keep code, weights and dataset terms separate. No unlicensed code has been copied
as part of this investigation.

## Experiment protocol

1. Pin model revision and hash downloaded weights; keep optional dependencies outside the core path.
2. Predict depth using RGB only. Do not pass sensor depth or poses into the model.
3. Evaluate predictions separately against available LiDAR with valid-confidence masks.
4. Report raw metric errors and scale bias. Do not align prediction scale to the evaluation reference.
5. Label LiDAR agreement as a sensor comparison, not independent centimetre ground truth.
6. Promote a backend only after evaluating poses, room geometry, openings and runtime on held-out properties.

The supplied scans are useful integration data. They do not replace the brief's
surveyed same-property three-tier benchmark, repeated capture, or consumer-app comparison.

## Completed Depth Anything experiment

Actual CPU inference is now implemented in `floorplan/metric_depth.py`, using
Transformers 4.49.0, Torch 2.6.0 and safetensors with remote code disabled by default.
Checkpoint revision: `8078d68a9c75a972131914f6afd0c1723be0da7f`.
The optional dependency group is `learned-depth`. Models are cached under `.tools/`.

Eight uniformly sampled registered RGB frames from the supplied single-room scan
were passed to the model without sensor depth or poses. Predictions were evaluated
afterward against valid 0.2–8 m LiDAR pixels at confidence >=1. No reference scale
was fitted. Results: `demo/given_metric_depth_small/sensor_comparison.json`.
An archived, image-free copy is [given_metric_depth_small.json](results/given_metric_depth_small.json).

| Frame | Raw mean absolute error vs sensor (m) | Median predicted / sensor depth |
| --- | ---: | ---: |
| 0 | 0.425 | 1.220 |
| 240 | 0.128 | 0.852 |
| 480 | 0.449 | 1.259 |
| 730 | 0.395 | 0.754 |
| 970 | 0.774 | 0.553 |
| 1220 | 0.686 | 1.512 |
| 1460 | 0.532 | 0.756 |
| 1710 | 0.394 | 0.904 |

Download/model loading plus eight inferences took 18.85 s after dependency setup;
this is not a clean-machine installation benchmark. RGB was the registered 256x192
stream, so this result does not characterize full-resolution stills. Sensor depth
itself is noisy and is not survey truth. Nevertheless the observed scale variation
does not support using this model as a cm-accurate measurement source. **Decision:
retain the experimental adapter; do not promote learned depth into production
measurement or claim that this experiment solves 2–8-photo stitching.**

```powershell
& .\.venv\Scripts\python.exe -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
& .\.venv\Scripts\python.exe -m pip install transformers==4.49.0
& .\.venv\Scripts\python.exe -m floorplan.cli benchmark-metric-depth demo/given_single_room_run_v2/intake/sequence.json --out runs/depth_trial --images 8
```
