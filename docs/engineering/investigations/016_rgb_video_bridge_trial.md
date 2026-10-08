# Batch 016: original RGB bridge-frame experiment

## Scope and preserved baseline

Use only the supplied `single_room/c00a170fe1/rgb.mp4`. No sensor depth,
confidence, odometry, IMU, calibration CSV, survey scale or previous sparse-model
poses enter inference. Frozen baseline:
`demo/phase3_sync_boundary/video_sampling_verified_input/video72/result/sfm`.

The current `floorplan/sfm.py` hash matches the original run's producer and the
installed pycolmap version matches its recorded **4.2.1**. Read-only baseline
audit and original input hashes are retained under `demo/phase3_video_bridge`.
All 68 original selected PNGs are copied unchanged into fresh experiment folders.
Each trial uses a fresh SQLite backup of the original feature/match database;
existing sparse models are inspected for evaluation only, never merged/initialized
into the new mapper. Old features/pairs are cached, not extracted afresh.

Every old row in cameras, images, keypoints, descriptors, matches and
two-view geometries remains exactly equal by content digest. Original input
files and all production Python module hashes remain unchanged. Adding source
views changes the experimental dataset, not matching or acceptance policy.

## Controlled trial and measured results

The first sampling recipe extracts real encoded frames at source times
**11.55-13.066667 s**, requested separation **0.125 s**. No interpolated frames
are synthesized. Retain the existing 320x240 Laplacian sharpness test **>=10**;
exclude selected source-time duplicates within 9 ms (a diagnostic deduplication
rule, not a changed acceptance guard). Of 12 candidates, ten are new accepted
views; the two excluded endpoint frames already exist in the baseline.

Matching remains CPU SIFT, exhaustive pairing, AUTO/SIMPLE_RADIAL cameras,
one thread, existing ratio **0.8**, descriptor distance **0.7**, mutual cross-check,
minimum verified inliers **15**, RANSAC error **4 px**, confidence **0.999** and
seed **7**. All remaining extraction, verification and incremental-mapping
options are saved in each `experiment.json`. Model-size and triangulation guards
are unchanged. The experiment does not generate a metric scale or a plan.

| Measurement | Frozen baseline | Requested 8 Hz | Requested 16 Hz |
|---|---:|---:|---:|
| Input views | 68 | 78 | 88 |
| New accepted views | 0 | 10 | 20 |
| Verified pairs | 139 | 169 | 222 |
| New pairs involving added views | 0 | 30 | 83 |
| Nontrivial pair components | 8 | 8 | 9 |
| Isolated views, total | 8 | 13 | 13 |
| Original isolated views | 8 | 7 | 7 |
| Verified connection between target groups | absent | absent | absent |
| Sparse model containing both target groups | none | none | none |
| Saved sparse models | 9 / 10 views | 12 / 10 views | 16 / 10 views |

Baseline nontrivial component sizes: **16,12,8,7,7,6,2,2**.
8 Hz component sizes: **17,16,8,7,7,6,2,2**.
16 Hz component sizes: **23,18,8,7,7,6,2,2,2**. Its extra two-view component
is disconnected from both target groups; the increased count is not stitching.
At both sampling rates six newly added views remain isolated, alongside seven
original isolated views. Previously isolated `frame_00025.png` gains verified
edges but still does not register in a saved model.

The 8 Hz models contain **1,294 / 153 points**, with mean reprojection errors
**0.61155 / 0.89526 px**. The 16 Hz models contain **1,506 / 153 points**, with
errors **0.66801 / 0.89526 px**. The original models contain **1,104 / 153 points**
and errors **0.55010 / 0.89526 px**. These are internal residuals, not physical
accuracy. A larger local model is not a connected scene.

The selected largest model changes from the original ten-view group to a model
with nine original views and three/seven added views. **The union of registered
original views remains 19/68**, not increased original-room/property coverage.
The existing maximum-view model-selection rule is retained; no alternative
selection, arbitrary scale alignment or sparse-model concatenation is promoted.

## Why the first bridge fails

The source interval visibly sweeps away from textured furniture across mostly
uniform wood/tile surfaces, with changing orientation and reduced image detail.
This is visual inspection of captures, not independent surface annotation.
Accepted sharpness ranges approximately **20-264**, so simply passing the current
sharpness filter does not guarantee useful stable feature support.

The first three added frames have **1,289 / 894 / 419** SIFT keypoints and join
the earlier group. Later views decline to **143**, then **46-67** keypoints.
No later view bridges through to the other target group at this sampling rate.

Do not interpret an empty stored `matches` row as literally zero descriptor
correspondences. COLMAP can clear sub-threshold matches before database storage;
this behavior was studied in the [official matching controller](https://github.com/colmap/colmap/blob/main/src/colmap/controllers/feature_matching_utils.cc).
Current upstream source is a conceptual reference, not asserted identical to
the installed release. The actual diagnostic replays the installed **4.2.1**
native matcher with exactly the saved matching options and no database writes.

Selected failing transitions in the 8 Hz replay:

| Source-time transition | Native pre-verification candidates | Required minimum | Stored verified inliers |
|---|---:|---:|---:|
| 12.083333 -> 12.216667 s | 13 | 15 | 0 |
| 12.216667 -> 12.350000 s | 12 | 15 | 0 |
| 12.350000 -> 12.500000 s | 3 | 15 | 0 |
| 12.500000 -> 12.566667 s | 6 | 15 | 0 |
| 12.566667 -> 12.633333 s | 5 | 15 | 0 |
| 12.633333 -> 12.766667 s | 7 | 15 | 0 |
| 12.766667 -> 12.916667 s | 10 | 15 | 0 |
| 12.916667 -> 13.066667 s | 13 | 15 | 0 |

The native diagnostic uses a fresh descriptor-index context; its approximate
nearest-neighbor counts can differ slightly from cached pipeline counts on
successful pairs. They must not be represented as the exact pre-trimming counts
of the original run. The recorded failing replay counts independently show
insufficient candidates under unchanged options.

For all 30 newly verified 8 Hz pairs, computed fundamental-matrix Sampson
residuals have maximum **3.87745 px**, with per-pair median range
**0.20890-0.69818 px**. Twenty-eight classify UNCALIBRATED and two
PLANAR_OR_PANORAMIC. These checks support local geometric consistency of the
accepted edges; they do not provide the absent cross-group edge or camera poses.

Actual source frames through the failure interval (separate handoff: `demo/phase3_video_bridge/bridge_contact_sheet.png`)

## Bounded alternative after diagnosis

Only after identifying the local correspondence shortfall, halve the requested
spacing to **0.0625 s** in the exact same source interval. Matching, verification,
camera and mapper settings remain fixed. There are 23 candidates, of which 20
are accepted; three source-time duplicates are excluded. No new dependency is
added and no reconstruction algorithm is changed.

This creates 83 verified pairs involving added views and larger local models,
but the target groups remain disconnected. Thus increased temporal sampling
alone is **not a successful bridge at either tested rate**. Do not widen geometric
thresholds or lower the 15-inlier guard to turn this failure into success.

Existing isolated [LightGlue+DISK experiments](008_lightglue_photo_matching.md)
were reviewed as a potential correspondence alternative. They previously improved
matches on other RGB groups without recovering their failed SfM model, so they
are not automatically superior. They were **not executed on this bridge interval**
in this batch. Neither reference repository was newly benchmarked or incorporated.
No external source code, assets or models were copied into production.

## Repeatability, regression and remaining limits

The 8 Hz trial is repeated from the same immutable images and a fresh baseline
database. Verified pairs, all six audited database-table contents, components,
registered image sets and binary sparse-model files are **exactly identical**.
Maximum raw camera-center coordinate difference is zero; this is same-input
software repeatability, **not physical repeat capture accuracy**.

The 16 Hz repeat also reproduces all six database-table contents, verified
pairs, components and binary sparse-model files exactly. Its maximum raw
camera-center coordinate difference is zero. Native replay still finds failing
adjacent transitions with **4-14** candidates, below 15. The maximum Sampson
residual across its 83 added-view verified pairs is **3.97523 px**.
Trial runtimes reuse old features: **78.53 / 66.17 s** for the
two 8 Hz runs and **123.84 / 103.66 s** for the two 16 Hz runs. These are not fresh
full-pipeline speed comparisons against the original 351.85 s reconstruction.

Targeted graph/connectivity, native-coordinate residual and existing SfM
diagnostic tests: **10 passed in 1.26 s**. Full regression: **182 passed in
58.04 s**. No test failure occurred in this batch. The initial PowerShell wrapper reported exit 1 because
native COLMAP informational stderr became `NativeCommandError`; the Python
experiment completed and wrote valid artifacts. Subsequent wrappers explicitly
propagate `$LASTEXITCODE`; the repeated Python process returns 0. This wrapper
issue is separate from the genuine absent-bridge result.

No production reconstruction logic or acceptance guard was changed. Preserve the
floor's **25/176 coverage, 151 uncovered samples**, bounded seed fix and unresolved
lower-span evidence limitation. The earlier **0.702677 m ceiling boundary shift
remains unvalidated**. No whole assessment requirement is newly closed.

## Reproduction and next step

Each output must be fresh. Run native reconstruction/tests serially. Original
producer, input images and cached database are local continuation dependencies;
final portable packaging must include or regenerate them. The initial 8 Hz script
version is retained at `demo/phase3_video_bridge/baseline_source` with its original
hash; current code only adds the declared 16 Hz sampling option.

```powershell
.\.venv\Scripts\python.exe scripts/experiments/experimental_video_bridge.py --baseline demo/phase3_sync_boundary/video_sampling_verified_input/video72/result/sfm --source datasets/Given_dataset/single_room/c00a170fe1/rgb.mp4 --out demo/fresh_bridge8
.\.venv\Scripts\python.exe scripts/experiments/experimental_video_bridge.py --baseline demo/phase3_sync_boundary/video_sampling_verified_input/video72/result/sfm --source datasets/Given_dataset/single_room/c00a170fe1/rgb.mp4 --out demo/fresh_bridge8_repeat --reuse-images demo/fresh_bridge8
.\.venv\Scripts\python.exe scripts/experiments/experimental_video_bridge.py --baseline demo/phase3_sync_boundary/video_sampling_verified_input/video72/result/sfm --source datasets/Given_dataset/single_room/c00a170fe1/rgb.mp4 --out demo/fresh_bridge16 --spacing-s .0625
.\.venv\Scripts\python.exe scripts/experiments/experimental_video_bridge.py --baseline demo/phase3_sync_boundary/video_sampling_verified_input/video72/result/sfm --source datasets/Given_dataset/single_room/c00a170fe1/rgb.mp4 --out demo/fresh_bridge16_repeat --spacing-s .0625 --reuse-images demo/fresh_bridge16
.\.venv\Scripts\python.exe scripts/diagnostics/audit_sfm_components.py demo/phase3_sync_boundary/video_sampling_verified_input/video72/result/sfm --out demo/fresh_bridge_baseline
.\.venv\Scripts\python.exe scripts/evaluation/compare_video_bridge_trials.py --baseline demo/fresh_bridge_baseline --first demo/fresh_bridge8 --repeat demo/fresh_bridge8_repeat --out demo/fresh_bridge8_comparison
.\.venv\Scripts\python.exe scripts/evaluation/compare_video_bridge_trials.py --baseline demo/fresh_bridge_baseline --first demo/fresh_bridge16 --repeat demo/fresh_bridge16_repeat --out demo/fresh_bridge16_comparison
```

When logging native output in PowerShell, capture `$LASTEXITCODE` immediately
after Python and `exit` that value, so informational stderr is not mistaken for
a failed Python process.

Next evaluate a bounded **pinned DISK+LightGlue trial on the 24 retained
transition views** (20 added 16 Hz images plus original frames 24/25/26/27),
using the exact RGBs and existing verification and mapper guards. Require actual
verified endpoint connectivity and a model containing both endpoint views before considering
integration; more raw matches or a larger disconnected model are insufficient.
Retain the current default pipeline and require independent metric/physical
evidence separately.

Files added: `scripts/experiments/experimental_video_bridge.py`,
`scripts/evaluation/compare_video_bridge_trials.py`, `tests/test_video_bridge_trial.py`,
this ledger and `benchmarks/results/video_bridge_summary.json`. Active README,
roadmap, status, design, operations and alternative-decision docs link the results.
No commit or push is made.
