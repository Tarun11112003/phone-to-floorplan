# Fixed per-frame intrinsics control on retained XFeat correspondences

This tests the calibration hypothesis identified by
[batch 021](021_TRANSITION_ODOMETRY_AUDIT.md), using the existing
[component research](../ASSESSMENT_COMPONENT_RESEARCH.md). No matching inference,
production SIFT change, architectural replacement or physical gate is performed.

## Setup and separation of evidence

Preserve all **32 original RGB inputs** and XFeat feature indices/candidate rows
from batch 020. Its saved baseline registers 29 views; dropping the other three
would bias the comparison. Reuse the verified playback-index +1 sensor identity
and original exact-pixel witnesses. Every control image has the baseline hash.

Export a strict pose-free JSON containing only per-view image name, frame ID,
dimensions, fx/fy/cx/cy and source/alignment hashes. The CSV export selects those
columns without interpreting x/y/z, quaternion or IMU values. The reconstruction
command receives only this JSON and the retained feature database. It never
imports odometry poses, optimized baseline poses, a metric scale or depth.

For each independent per-frame SIMPLE_RADIAL camera, set supplied fx/cx/cy and
the existing zero radial coefficient, with `prior_focal_length=1`. All supplied
fx/fy values are exactly equal, allowing the existing camera model to remain.
Reject unequal fx/fy, invalid dimensions or undeclared calibration/pose fields.
No separately supplied distortion lookup is used or estimated in this control.
This experiment fixes the provided calibration; it does not independently prove
optical calibration accuracy or distortion correction.

Set all 32 cameras constant during local/global bundle adjustment and absolute
pose registration; disable focal and extra-parameter refinement there. Principal
point refinement was already disabled. The serialized options differ in exactly
six declared **intrinsic-policy fields**, not numerical verification, mapping,
inlier, parallax, pose-error, reprojection, seed, threading or acceptance thresholds.
Initial image selection remains automatic, including native fallback behavior.
No pose priors or non-reference rig extrinsics enter the control database.

The installed pinned PyCOLMAP 4.2.1 API and its
[official mapper source](https://github.com/colmap/colmap/blob/4.2.1/src/colmap/sfm/incremental_mapper.cc)
were checked for constant-camera behavior in pose registration and adjustment.
No upstream implementation is copied. Prior A/B and matcher research is reused;
there is no additional library, checkpoint or model dependency.

Retained final raw match rows contain **85,439 entries**. The original frontend
had 86,525; batch 020 already documented 1,086 entries cleared from sub-15 rows.
These unavailable sub-threshold candidates are not regenerated or relabeled as
new feature-extraction loss. Images, keypoints, descriptors and all stored raw
match rows remain exact through verification and mapping.

Clear copied two-view geometry so calibrated verification genuinely reruns, using
the unchanged verification options. The graph retains exactly the same **236
positive edge identities**, one component and zero isolates. Geometry becomes
150 CALIBRATED / 86 UNCALIBRATED, versus all 236 UNCALIBRATED before. **60 pair
rows change verified inlier counts**. Thus this measures the complete calibrated
camera policy, including its legitimate verification effects; it does not isolate
bundle-adjustment focal freedom from changed inlier selection or nominal
initialization. Do not attribute every gain exclusively to disabling refinement.

## Measured results

Two fresh control databases are reconstructed, serially. The existing auditor
uses odometry **only after reconstruction** and performs no pose/scale fitting.
Relative-length ratios normalize each result by its own common 19->24 span;
one means equal relative displacement to the sensor reference, not metric scale.

| Metric | Free-intrinsics XFeat baseline | Fixed-intrinsics control |
|---|---:|---:|
| Retained inputs | 32 | 32 |
| Verified pairs | 236 | 236 |
| Connected components / isolates | 1 / 0 | 1 / 0 |
| Registered views in one joint model | 29 | **32** |
| Sparse points | 5,455 | **6,360** |
| Mean point reprojection residual, px | 1.486099 | 1.470216 |
| Focal range, px | 884.083..1,545.651 | **1,587.494..1,608.282** |
| Fixed-camera parameter difference | Not applicable | **exactly zero, all 32** |
| Solver warnings per completed run | 149 | 23 |
| Native point tracks spanning original groups | 0 | 0 |

Later context frames 31/34/37 now register in the same model. This is a real
bounded registration improvement, not a metric whole-property plan or an
assessment completeness pass. Cameras/points remain monocular model units.

| Relative motion | Rotation disagreement, before -> after | Direction disagreement, before -> after | Relative length ratio, before -> after |
|---|---:|---:|---:|
| 19->24, earlier reference | 0.969732 -> 1.508319 deg | 4.329983 -> 2.373611 deg | 1 -> 1 by definition |
| **24->27, target transition** | **24.771982 -> 5.199806 deg** | **34.595082 -> 10.235933 deg** | **1.496456 -> 1.080450** |
| **24->28, extended transition** | **34.735237 -> 5.381200 deg** | **66.479466 -> 9.309387 deg** | **3.721359 -> 1.079837** |
| 27->28, final old consecutive step | 11.639250 -> 0.581097 deg | 47.762522 -> 4.264817 deg | 10.872672 -> 1.039585 |

Not every motion improves: the 19->24 orientation disagreement grows. On the
same 28 consecutive spans available in both models, rotation error median/p95
improves **0.493650/6.081030 -> 0.278988/1.573462 deg**, and direction error
median/p95 **22.113420/55.129357 -> 7.645917/35.419851 deg**. Small-translation
direction errors still require caution because sensor noise is not quantified.

The transition remains only **partially sensor-consistent (B)**. Varying both
24/27 sensor identities by +/- one frame still leaves **4.590513..6.704423 deg**
rotation and **9.592163..11.667285 deg** direction disagreement. This is a timing
sensitivity probe, not an acceptance band. No assessment-backed camera-pose
tolerance or sensor covariance is available.

The additional later context exposes residual drift:

| Motion from frame 24 | Rotation disagreement | Direction disagreement | Relative length ratio |
|---|---:|---:|---:|
| ->31 | 8.951518 deg | 11.659330 deg | 1.004627 |
| ->34 | 14.872499 deg | 6.916334 deg | 1.090823 |
| ->37 | **18.706806 deg** | 4.220273 deg | **1.193516** |

Constant calibrated focal values do not eliminate this remaining orientation
drift. The 31->34 consecutive orientation error alone is 6.097519 deg. New
camera membership must not hide this larger-chain limitation.

## Correspondence and saved-model safety

| Safety diagnostic | Baseline | Fixed control |
|---|---:|---:|
| Conflicting raw feature components | 778 | 792 |
| Observations in conflicts / total | 29,840 / 39,120 | 29,912 / 39,183 |
| Clean raw endpoint-spanning components | 0 | 0 |
| Triangle contradictions | 17,644 / 71,150 (24.80%) | 17,972 / 73,191 (24.55%) |
| Duplicate-image native point tracks | 153 | 145 |
| Saved observations | 20,950 | 23,410 |
| Nonpositive-depth saved observations | 0 | 0 |

Native observation residual min/median/p95/max is
0.000304 / 1.510528 / 3.174897 / 3.977946 px under the existing 4 px filter.
Nearby duplicate-image observations reach 7.5 px separation; they do not imply
that every corresponding saved point is physically incorrect. Large raw
identity conflicts and zero direct native group-spanning landmarks remain
unresolved. Indirect bridge tracks can connect distant cameras legitimately,
but pair graph connectivity and positive-depth/pixel guards do not certify that
the joint shape is correct. The earlier suspicious proposals are not promoted
to independent geometric evidence.

## Reproducibility, tests and actual failures

- Two fresh mapping runs reproduce all six database table digests, verified
  graphs, memberships, five model binaries and post-hoc pose metrics exactly.
- Runtimes: **39.114 / 38.393 s**; verification **0.877 / 0.797 s**, mapping
  **36.487 / 36.102 s**. These reuse features/matches and exclude extraction,
  matching, calibration export and evaluation. They cannot be compared as
  end-to-end speedups against the original 6.5-minute learned matching runs.
- All **528 previously pinned unique evidence/source hashes** remain unchanged;
  DB/WAL remain checked, excluding only SQLite SHM read bookkeeping.
- Initial targeted tests: **41 passed in 2.18 s**.
- Final targeted regression: **67 passed in 2.13 s**, including **17 new cases**.
- Full suite: **249 passed in 43.68 s**, zero failing tests.
- Windows PowerShell recorded trial1 native informational stderr as a
  `NativeCommandError` and reported wrapper status 1. The experiment itself
  finished and saved its validated record/model. Trial2 captures raw native
  output through Python, exits **0**, and exactly reproduces trial1.
- The first read-only evaluation stopped while decoding trial1's UTF-16 log as
  UTF-8, after safety computation and before writing a complete evaluation.
  The evaluator now decodes BOM-marked UTF-16 or UTF-8 losslessly; regressions
  cover both. Only **evaluation2** is authoritative. Reconstruction is not rerun
  for that diagnostic correction; the partial evaluation is retained separately.

```powershell
.\.venv\Scripts\python.exe scripts/experimental_fixed_intrinsics.py export --out demo/phase3_fixed_intrinsics/calibration.json
.\.venv\Scripts\python.exe scripts/experimental_fixed_intrinsics.py map --calibration demo/phase3_fixed_intrinsics/calibration.json --out demo/phase3_fixed_intrinsics/trial1
.\.venv\Scripts\python.exe scripts/experimental_fixed_intrinsics.py map --calibration demo/phase3_fixed_intrinsics/calibration.json --out demo/phase3_fixed_intrinsics/trial2
.\.venv\Scripts\python.exe scripts/evaluate_fixed_intrinsics.py --out demo/phase3_fixed_intrinsics/evaluation2
.\.venv\Scripts\python.exe -m pytest -q tests/test_fixed_intrinsics.py tests/test_transition_odometry.py tests/test_xfeat_context.py tests/test_transition_context.py tests/test_transition_tracks.py tests/test_transition_matchers.py
.\.venv\Scripts\python.exe -m pytest -q
```

Use new output paths; existing evidence is not overwritten. Native commands can
be logged through `subprocess.run(..., stdout=log, stderr=STDOUT)` to avoid
PowerShell's stderr wrapping; record the actual native return code. Pose audits
reuse pinned source timing/image identity and do not re-decode or rerun inference.

## Engineering decision and remaining scope

**The calibrated intrinsic policy demonstrably improves this reconstruction.**
The hypothesis that wrong/unstable calibration contributes is supported; it is
not the sole cause. This control changes supplied initialization, prior status,
intrinsic freedom and calibration-dependent inlier selection together. Raw
correspondence ambiguity and remaining camera drift persist. No new production
arithmetic, intake or synchronization defect is established.

**XFeat remains experimental; preserve production SIFT.** This is stronger
evidence for an opt-in calibrated-video path, not justification for promoting a
model that still has residual sensor disagreement or substituting scanner
calibration into ordinary stock videos that do not provide it. No production
milestone is shipped, so **no commit or push**; do not commit the isolated
experimental controls merely because they completed.

Added `scripts/experimental_fixed_intrinsics.py`,
`scripts/evaluate_fixed_intrinsics.py`, `tests/test_fixed_intrinsics.py`, this
record and [compact hashed evidence](../results/phase3_fixed_intrinsics_summary.json).
Current design/research/status/operations/roadmap decisions are updated. All
mapping data, pose-free calibration and raw safety/audit outputs remain ignored.

REQ-03/05/10/27/29 remain **PARTIALLY IMPLEMENTED**. The control improves video
geometry evidence; it does not produce a complete metric property, demonstrate
assessment drift correction/footprint ablation, or prove video wall accuracy.
Floor stays **25/176**, and the **0.702677 m ceiling shift remains unvalidated**.
Independent survey, three-tier same-property data/repeats, damage labels,
calibrated intervals, consumer comparison, official schema/gates and cold
walk-in evidence remain outstanding. No centimetre accuracy or acceptance claim.

**Single next technical step:** run a **mapping-only fixed-intrinsics ablation**
that preserves the baseline's exact 236 verified-pair/inlier rows without
re-verification, then apply the same withheld-odometry auditor. This differs
materially from the completed control: it isolates mapping/calibration effects
from the 60 changed verified-inlier rows, before assigning a narrower root cause
or proposing any production camera-policy change. Do not repeat matching or
weaken correctness guards.
