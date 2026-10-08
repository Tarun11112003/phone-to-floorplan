# Pinned DISK + LightGlue on the retained RGB transition

## Declared scope and baseline

Continue the measured correspondence bottleneck in [batch 016](016_rgb_video_bridge_trial.md).
Use exactly its 20 retained 16 Hz bridge PNGs plus original frames 24/25/26/27,
ordered by original source time: 24 RGB views, 11.55–13.066667 s.
No fresh frame selection, sensor depth, confidence, IMU, odometry, survey scale,
optimized camera poses or previous 3D model enters inference.

The SIFT baseline is the **exact retained feature and verified-pair subset**,
not a fresh full-video reconstruction. Initial camera/image/rig/frame metadata
is copied unchanged to fresh databases for both alternatives. SIFT pre-verification
counts are diagnosed through a fresh native matcher replay, whose approximate
nearest-neighbor context can differ from historic pre-trimming counts. Those
counts must not be called the original pipeline's exact raw counts.

The retained baseline has **39 verified pairs**, nontrivial components **12/3/2**,
and **seven isolated views**. Original endpoints `frame_00024.png` and
`frame_00027.png` have no verified path. Fresh mapping produces a two-view local
model with 371 points and mean reprojection error 0.297695 px; neither endpoint
is jointly registered. Repeating this mapping gives identical binary model files.
The small returned model is COLMAP's existing behavior; no model-size guard is
changed to produce it.

## Alternative and falsification

The isolated candidate uses the already installed official LightGlue package:

- Code revision `eb42fee2d71449efb0aa5c10549752b5d75384d8`, checked against
  installed `direct_url.json`; hashes of every package Python source are retained.
- DISK checkpoint `depth-save.pth` SHA-256
  `9c2ee4ded238892dfa51569941372601e35e4a74aa6f84ea80053d2ab1c07abe`.
- LightGlue `disk_lightglue_v0-1_arxiv.pth` SHA-256
  `b5b21d47ea24f2c5e501aec9c91b9716e4c8c3429a4dc1e615c133c4c9378335`.
- Torch 2.6.0+cpu, Torchvision 0.21.0+cpu, Kornia 0.8.1, PyCOLMAP 4.2.1.
- CPU, seed 7, four Torch threads, deterministic algorithms, DISK up to 2,048
  keypoints, default original-image coordinate restoration, LightGlue defaults
  with FlashAttention disabled. All 276 possible pairs are evaluated.

The official [LightGlue revision](https://github.com/cvg/LightGlue/tree/eb42fee2d71449efb0aa5c10549752b5d75384d8)
and its installed package identify Apache-2.0 code/weights for LightGlue and DISK.
No third-party source or checkpoint is vendored into production. The official
[HLoc import convention](https://github.com/cvg/Hierarchical-Localization/blob/master/hloc/triangulation.py)
was inspected to confirm that learned original-image zero-based keypoint centers
need **+0.5 px** when imported into COLMAP. This is a coordinate conversion, not
a change to geometric error thresholds. No HLoc mapping/RANSAC recipe is adopted.

`frozen_options` rejects any difference from the prior experiment's complete
verification or mapper options: minimum 15 inliers, RANSAC 4 px/confidence 0.999,
mapper initialization 100 inliers/16° triangulation, existing focal/pose/track
filters, seeded single-thread mapping. No forced endpoint initialization or model
concatenation is allowed. All 24 views remain in every trial.

Prediction: learned correspondences create a reproducible verified endpoint path
**and** a sparse model containing both endpoints under those guards. Falsify if
either condition is absent. Increased candidate/inlier counts alone are insufficient.
Even a successful bounded experiment requires full-video validation before
production integration; neither case demonstrates metric accuracy.

## Validation procedure

`scripts/experiments/experimental_transition_matchers.py` creates fresh databases and outputs;
`scripts/evaluation/compare_transition_matchers.py` checks exact inputs/options/camera priors,
component changes, all-pair and adjacent candidate/inlier counts, geometry labels,
fundamental-matrix Sampson residuals, sparse models and same-input repeatability.
Image, input, package, checkpoint, production-source and script hashes are recorded.

```powershell
.\.venv\Scripts\python.exe scripts/experiments/experimental_transition_matchers.py --mode sift --out demo/phase3_transition_matchers/sift4
.\.venv\Scripts\python.exe scripts/experiments/experimental_transition_matchers.py --mode sift --out demo/phase3_transition_matchers/sift5
.\.venv\Scripts\python.exe scripts/experiments/experimental_transition_matchers.py --mode lightglue --out demo/phase3_transition_matchers/lightglue_thread4_1
.\.venv\Scripts\python.exe scripts/experiments/experimental_transition_matchers.py --mode lightglue --out demo/phase3_transition_matchers/lightglue_thread4_2
.\.venv\Scripts\python.exe scripts/evaluation/compare_transition_matchers.py --sift demo/phase3_transition_matchers/sift4 --sift-repeat demo/phase3_transition_matchers/sift5 --learned demo/phase3_transition_matchers/lightglue_thread4_1 --learned-repeat demo/phase3_transition_matchers/lightglue_thread4_2 --out demo/phase3_transition_matchers/comparison
```

Run native reconstruction and tests serially. Capture and propagate Python's
`$LASTEXITCODE` when redirecting COLMAP stderr in PowerShell. Outputs and cached
dependencies remain ignored; final portable packaging still needs the declared
RGB inputs and environment provisioning.

## Acceptance holds

Floor completeness remains **25/176 covered, 151 uncovered samples**. Preserve
the bounded seed-selection fix and unsupported lower-span limitation. The earlier
**0.702677 m ceiling boundary shift remains unvalidated**. These are separate
geometry holds and must not drive a fabricated connecting wall. Physical survey,
independent repeats, metric calibration and full assessment acceptance remain open.

## Outcome

The initial single-Torch-thread run finished all 24 feature extractions and logged
37/276 pair-progress before being deliberately stopped for resource cost. Its
partial `lightglue1` database is retained locally, has no completed experiment
report, and is excluded from the comparison. The fresh trials use the four-thread
Torch configuration already used in the earlier isolated matcher study; all
COLMAP verification/mapping threads and thresholds stay fixed. The finalized
script is used for two fresh SIFT mappings as well. This is an execution-setting
adjustment, not a changed feature budget or a successful geometry result.

Both fresh learned runs have completed; production **SIFT remains unchanged**.
No production adoption or metric-accuracy improvement is justified.

| Measurement on exactly 24 views | Retained SIFT | DISK + LightGlue |
|---|---:|---:|
| Candidate pairs evaluated | 276 | 276 |
| Candidate matches, total | 7,931 (native replay) | 42,224 (actual imported) |
| Median candidates per pair | 3 | 15.5 |
| Pairs with fewer than 15 candidates | 231 | 129 |
| Verified pairs | 39 | 109 |
| Nontrivial component sizes | 12 / 3 / 2 | 24 |
| Isolated views | 7 | 0 |
| Verified endpoint path | absent | present, three edges |
| Joint endpoint sparse model | absent | absent |
| Largest saved model | 2 views / 371 points | 2 views / 67 points |
| Mean model reprojection error | 0.297695 px | 1.000242 px |
| Native initialization-suitable pairs, unchanged starting options | 1 / 39 | 0 / 109 |
| Maximum verified-inlier Sampson residual | 3.975227 px | 3.999057 px |
| Runtime, first / repeat | 10.24 / 10.52 s | 699.42 / 644.57 s |

SIFT's timings reuse features and verified geometry; they are **not fresh
end-to-end feature-extraction timings**. Learned timings include fresh feature
extraction/matching/verification. Do not present this as a fair full-pipeline
speed ratio. All learned pairs classify `UNCALIBRATED`; SIFT has 30 uncalibrated
and nine planar-or-panoramic pairs. Configuration labels and pixel residuals do
not prove physical scene correctness, parallax or metric scale.

The learned shortest path is
`frame_00024 -> bridge_00002 -> frame_00025 -> frame_00027`, with **1,243 / 23 / 18**
verified inliers. These edges pass the existing 15-inlier pair guard, yet do not
establish usable common-coordinate 3D structure. The only saved learned model
contains `frame_00026.png` and `bridge_00018.png`; neither original endpoint is
in it. No sparse models are concatenated or manually aligned.

### Reproducibility

Both SIFT and learned repeats reproduce all six audited database-table contents,
all candidate counts, verified inlier counts/classifications, components, model
memberships and binary model files **exactly**. Learned feature outputs, package
identity and checkpoint hashes match exactly. Maximum raw camera-center difference
is **zero**. This is same-input software determinism, not physical repeatability.

### Failure diagnosis and decision

The original correspondence shortfall is improved **within this bounded trial**:
there are 70 additional verified edges and a connected endpoint graph. The
remaining failure is native **3D initialization/registration**, not an absent
2D graph path. `scripts/diagnostics/audit_transition_initialization.py` copies each database,
loads the original mapper configuration and calls the installed native
`estimate_initial_two_view_geometry` without registering or exporting any model.
It finds **zero** suitable learned pairs versus **one** SIFT pair; both frozen
databases retain their original hashes.

Native mapping logs also show rejected initial pairs and unsuccessful attempted
registration of `bridge_00017` / `bridge_00015`, despite 55 / 39 visible 3D points
and 816 / 483 structure-less fallback correspondences respectively. COLMAP's
existing internal initialization fallback appears in both workflows; the caller's
configuration and application acceptance guards are unchanged. The retained
two-view result is not promoted to a property reconstruction.

Prior-conditioned relative-pose diagnostics have median estimated angles about
**1.00° (SIFT)** and **1.40° (learned)**. All ten learned pairs with a diagnostic
angle >=16° have fewer than 100 stored F-inliers. This suggests weak joint support
for initialization, but is **not a direct recreation of the mapper's rejection
reason**: the SIFT pair that passes the native suitability test has a different
stored-geometry pose-angle estimate below 16°. These are different native
calculations; stored F-inlier counts/pose angles cannot substitute for the
mapper's suitability checks. The [current upstream mapper](https://github.com/colmap/colmap/blob/main/src/colmap/sfm/incremental_mapper.cc)
was inspected as a conceptual reference; it is not asserted identical to the
installed build. The reported suitability counts come from the installed API.
Actual motion, feature-track correctness and intrinsic-calibration error are not
uniquely distinguished by these conditional diagnostics. Do not claim a measured
physical parallax failure or conclude that weaker thresholds would be correct.

**Decision: do not integrate DISK + LightGlue into production.** The predicted
joint endpoint model was not recovered, the local sparse model has fewer points
and a larger internal residual, and the candidate is materially more expensive
on this CPU. Keep the isolated harness as measured evidence and a reference for
further bounded evaluation. No reference-repository architecture was incorporated;
the official matcher and HLoc coordinate convention were the relevant alternatives.

Targeted safeguard/diagnostic tests: **20 passed in 1.60 s**. An intermediate
fixture test failed because its synthetic `pose_priors` insert omitted required
`coordinate_system`; correcting the fixture made it pass without implementation
changes. Full regression: **192 passed in 53.67 s**. No regression failure remains.
See [the compact hashed evidence](../../../benchmarks/results/transition_matcher_summary.json).

### Single next technical step

Evaluate a **32-view context trial**: retain every current transition image and
add original registered RGB anchors **16, 19, 22, 23, 28, 31, 34, 37** from the
frozen video selection. These eight images are present in its two original sparse
models, so they supply existing observed reconstruction context on both sides.
Use their RGB and original initialization priors only, not prior optimized poses
or model alignment. Compare against a matching 32-view SIFT baseline and require
one model spanning both original groups under the unchanged guards. This is a
proposed experiment, not an implemented or successful fix. All physical/geometry
acceptance holds above remain unchanged.
