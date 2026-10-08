# MoGe-2 RGB-only metric-depth experiment

## Question

RGB SfM can recover an unscaled scene, but the photo tier has no depth or pose
input and the assignment expects dimensioned output. A monocular metric-geometry
model may supply a learned absolute-scale proposal, though model metricness is
not centimetre accuracy.

The Microsoft MoGe project documents metric point maps/depth and estimated camera
FOV from one image. The MoGe-2 ViT-S checkpoint is listed at 35M parameters and
its Hugging Face card reports MIT. Its speed claim is for a large GPU and model;
this workstation has CPU-only Torch, so runtime and memory are part of the test.
Do not use MoGe-3's GPU-focused installation path for this bounded v2 experiment.

## Experiment design

- Pin MoGe code revision, checkpoint revision and SHA-256 for each.
- Run RGB only on held-out ARKitScenes iPhone and ICL-NUIM images at 2/4/8 input
  counts. Never pass sensor depth, poses, intrinsics or laser references to model
  inference; evaluate those references afterward only.
- Compare raw predicted metric depth to synchronized ARKitScenes sensor depth and
  ICL-NUIM depth/mesh. Use valid masks and report MAE, median absolute error,
  scale bias, runtime and peak memory without post-hoc scale fitting.
- Measure consistency of a shared visible plane across different input images.
- Keep results separate from room-floor-plan gates until a reproducible method
  converts predictions into supported walls, topology, openings and dimensions.

## Prediction and falsification

Prediction: MoGe-2 ViT-S can run on the existing CPU environment and improve raw
depth scale error over the already-tested Depth Anything V2 Small on at least one
of the held-out geometry datasets. Falsify if it cannot install/run in the current
runtime budget, if raw scale error is no better, if frame-to-frame scale varies
too much for shared walls, or if room geometry remains unsupported. Do not fit a
scale against the held-out reference to rescue the result.

Even a successful depth comparison does not pass the photo-plan gate. The result
must still demonstrate wall lengths within the photo tolerance, footprint,
openings, multi-room adjacency and calibrated intervals on held-out properties.

## First measured result

Implemented `scripts/evaluation/evaluate_moge_depth.py` as a standalone RGB-only probe.
The pinned MoGe v2 ViT-S checkpoint loaded on CPU and evaluated eight uniformly
sampled synchronized frames from ARKitScenes scene 41418140. Inference took
10.35 s/frame on average after a 0.85 s cached model load. Against uint16 sensor
depth (mm converted to m; confidence >=1), with no scale fit, macro per-frame
MAE was 0.554 m, median absolute error 0.456 m, and signed depth bias -0.364 m.
Per-frame MAE ranged from about 0.138 to 0.838 m, showing substantial view
dependence. Raw per-frame evidence is in the ignored local artifact
`demo/moge_metric_eval/41418140_8.json`.

Pinned artifacts: MoGe repository commit `74fbce054ebed49800de42d0ad0e83495065719a`;
Hugging Face checkpoint revision `26b477f41595707c5db6770294c0d1721e8ed4ed`;
`model.pt` SHA-256 `79a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc`.
The runner verifies the checkpoint hash before scoring.

This falsifies the proposal as a dependable metric-scale source for this sample:
it is far from centimetre measurement and too slow for real-time CPU guidance.
Do not wire it into floor-plan dimensions. This is sensor agreement only, not
independent surveyed truth; the comparison should be repeated on another room and
the existing Depth Anything comparison used a different frame sample, so no
claim of model superiority is made. The next photo-tier priority remains a
capture-known scale measurement plus quality-gated multi-view reconstruction.
