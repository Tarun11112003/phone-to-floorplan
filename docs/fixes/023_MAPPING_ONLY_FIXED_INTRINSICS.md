# Mapping-only fixed-intrinsics ablation with original verified rows

Date: 2026-10-08. Uses the existing [component research](../ASSESSMENT_COMPONENT_RESEARCH.md),
[fixed-intrinsics control](022_FIXED_INTRINSICS_CONTROL.md) and unchanged
[withheld-odometry audit](021_TRANSITION_ODOMETRY_AUDIT.md). No matcher investigation,
production replacement, physical measurement or assessment acceptance is added.

## Controlled question and exact setup

Batch022 combined mapping calibration with re-verification, changing 60
verified-inlier count rows. This experiment asks whether mapping calibration
alone improves geometry with the original verified evidence held fixed.

- Source: **batch020 `demo/phase3_xfeat_context/trial2/features.db`**, not the
  reverified batch022 database. Retain all **32 RGB inputs**; the original saved
  model registered 29 of them. No view is added, dropped or re-extracted.
- Copy all original keypoints, descriptors, raw match rows and **all 496
  two-view records**, including 260 zero-inlier records. There are **236 positive
  verified pairs and 70,055 verified inlier entries**, all UNCALIBRATED.
- Preserve whole-row digests, including verified feature indices, configuration
  and **F/E/H blobs**, before calibration, before mapping and after mapping.
  Source relative-pose/camera blobs are NULL; reject sources with cached blobs,
  sensor pose priors or supplied non-reference rig extrinsics.
- Reuse batch022's exact pose-free calibration JSON. Set the supplied per-frame
  `[fx,cx,cy,0]` SIMPLE_RADIAL vectors and `prior_focal_length=1`. Fix all cameras
  in absolute pose estimation and local/global BA. Each saved intrinsic vector
  must match exactly. This does not prove optical calibration or distortion.
- Serialize mapping and verification options and require exact equality to
  batch022. Numeric inlier, parallax, reprojection, pose-error, random-seed,
  threading and acceptance guards stay unchanged. The only six option changes
  versus batch020 are the already declared intrinsic-policy fields.
- Call **only PyCOLMAP 4.2.1 `incremental_mapping`**. Do not call feature matching,
  extraction or `verify_matches`; do not supply a saved reconstruction, seed
  poses, depth, IMU, odometry poses, scale or a sensor-assisted optimizer.
- Retained uncalibrated F/E/H records remain unchanged. Native mapping must
  estimate poses using the fixed cameras and retained correspondences; this
  belongs to mapping, not a new verified-inlier selection pass.
- Two fresh trials run serially. All **632 existing pinned hash entries** pass
  before/after execution. Existing source artifacts and the uncommitted backlog
  are preserved. SQLite SHM bookkeeping is excluded as previously; DB/WAL remain
  included. Production SIFT and geometry source are unchanged.

## Independent post-hoc audit

The mapper receives only RGB, the retained feature database and pose-free camera
calibration. The separate evaluator reads odometry **after both saved models
exist**. Reuse the established playback-index **+1** sensor mapping, exact RGB
pixel witnesses and full-cadence timestamp fit. Image hashes are rechecked,
rather than repeating decoding/matching/timing experiments.

Compare COLMAP camera centers and camera-to-world orientations with the matching
sensor rows. Relative rotations and local translation directions require no
global alignment. Normalize displacement lengths by each trajectory's **19->24**
span: candidate **14.442699 model units**, sensor **1.036796 m**. A ratio of one
means equal relative displacement; it does not give the model metric scale or
establish physical dimensional accuracy. No poses are corrected or optimized.

Frame24 maps to sensor539 at source11.55s; frame27 to610 at13.066667s; frame28
to634 at13.583333s. Later31/34/37 map to705/773/842 at15.116667/16.633333/18.15s.
The unchanged auditor covers all32 registered views and the same transition.

There is no supplied sensor covariance, independently measured trajectory or
assessment-backed camera-pose acceptance tolerance. Retain the existing guards
(15-match minimum, existing pose constraints and 4px sparse filtering); do not
invent a new angular pass threshold. Varying both24/27 sensor associations by
one frame leaves **3.672419..5.852502deg** rotation and
**8.852611..10.887945deg** direction disagreement. This is sensitivity evidence,
not an acceptance band. No new frame-ordering/timing discrepancy is observed.

## Measured comparison

| Metric | Batch020 free intrinsics | Batch022 fixed + reverified | Batch023 mapping-only fixed |
|---|---:|---:|---:|
| RGB input views | 32 | 32 | 32 |
| Verified pairs | 236 | 236 | 236, original rows exact |
| Pair-graph components / isolated views | 1 / 0 | 1 / 0 | 1 / 0 |
| Registered views in one joint camera model | 29 | 32 | 32 |
| Sparse points | 5,455 | 6,360 | 6,187 |
| Mean point reprojection residual, px | 1.486099 | 1.470216 | 1.480503 |
| Focal range, px | 884.083..1,545.651 | 1,587.494..1,608.282 | 1,587.494..1,608.282 |
| Saved fixed-vector parameter change | N/A | zero, all32 | zero, all32 |
| Joint target-group camera membership | yes | yes | yes |
| Native point tracks directly spanning original groups | 0 | 0 | 0 |
| Linear-solver warnings per completed run | 149 | 23 | 52 |

Graph connectivity is unchanged. More registered views than batch020 and a joint
camera model are not correctness criteria by themselves. Reprojection error
worsens slightly versus batch022 even though the selected pose metrics improve.

| Relative motion | Metric | Batch020 | Batch022 | Batch023 |
|---|---|---:|---:|---:|
| **24->27** | Rotation disagreement, deg | 24.771982 | 5.199806 | **4.319124** |
| | Translation-direction disagreement, deg | 34.595082 | 10.235933 | **9.482126** |
| | Relative-length ratio | 1.496456 | 1.080450 | **1.035232** |
| **24->28** | Rotation disagreement, deg | 34.735237 | 5.381200 | **4.503354** |
| | Translation-direction disagreement, deg | 66.479466 | 9.309387 | **8.399241** |
| | Relative-length ratio | 3.721359 | 1.079837 | **1.043176** |
| 27->28 | Rotation disagreement, deg | 11.639250 | 0.581097 | 0.393824 |
| | Translation-direction disagreement, deg | 47.762522 | 4.264817 | 2.666715 |
| | Relative-length ratio | 10.872672 | 1.039585 | 1.026575 |
| 19->24 reference | Rotation disagreement, deg | 0.969732 | 1.508319 | 1.132821 |
| | Translation-direction disagreement, deg | 4.329983 | 2.373611 | 2.448213 |

For the **exact same 28 adjacent pairs** in all three models:

| Diagnostic | Batch020 | Batch022 | Batch023 |
|---|---:|---:|---:|
| Rotation median / p95, deg | 0.493650 / 6.081030 | 0.278988 / 1.573462 | 0.248627 / 1.305699 |
| Direction median / p95, deg | 22.113420 / 55.129357 | 7.645917 / 35.419851 | 6.751723 / **39.849600** |
| Direction maximum, deg | 59.992279 | 55.914256 | **92.028022** |

Do not hide the worsened direction tail. The largest discrepancy is
bridge00006->bridge00007, sensor displacement **0.020256m** over **0.066677s**;
its relative-length ratio is **0.073410**. Small displacements make direction
sensitive, but absent covariance is not evidence that this discrepancy is noise.

Later context still exposes cumulative orientation disagreement:

| From frame24 | Batch022 rotation, deg | Batch023 rotation, deg | Batch022 length ratio | Batch023 length ratio |
|---|---:|---:|---:|---:|
| ->31 | 8.951518 | 6.088059 | 1.004627 | 1.037492 |
| ->34 | 14.872499 | 12.447034 | 1.090823 | 1.042908 |
| ->37 | 18.706806 | **16.690768** | 1.193516 | 1.118663 |

The 31->34 consecutive rotation disagreement is **6.520814deg**, compared with
6.097519deg in batch022. Endpoint improvements do not eliminate this local
regression. This newly registered late span is a concrete follow-up target.

## Tracks, contradictions and solver evidence

The verified frontend is held exactly fixed, so its track/triangle diagnostics
reproduce **batch020**, rather than the altered batch022 verified frontend:

- **4,229** raw feature components, **39,120** observations; **778** conflicting
  components with **29,840** observations in conflicts.
- **1,341** clean components with at least three views. Five raw components span
  the transition endpoints; **all five conflict**, zero clean spanning components.
- **17,644 / 71,150** directly testable triangle relations conflict (**24.80%**);
  **714 / 875** triangles contain conflicts. These are identity-consistency
  failures, not newly assigned ground-truth annotations.
- Native saved model: **136** duplicate-image point tracks (batch022145,
  batch020153), maximum separation7.5px; **22,911** observations, no nonpositive
  depth observations, and zero native landmarks directly spanning original groups.
- Observation residual min/median/p95/max:
  **0.000230 / 1.513896 / 3.174062 / 3.963635px**. Nearby duplicates can survive
  existing pixel filtering; do not label all saved points incorrect on that basis.
- Both native runs exit **0**, with **52** repeated Ceres/Eigen dense-Cholesky
  linear-step failures each. Solver warnings increase versus batch02223. The
  solver ultimately writes a model; successful exit is not proof of geometry.

Indirect bridge tracks can legitimately connect cameras without a landmark seen
by both original endpoint groups. Zero direct group-spanning landmarks alone
does not disprove the model. Persistent identity conflicts and independent pose
disagreement collectively prevent production adoption.

## Reproducibility and tests

Both fresh runs reproduce all six database table digests, verified graphs,
memberships, five model binaries and post-hoc pose metrics **exactly**. Fixed
intrinsics are exact in all32 saved cameras. No model union or pose prior is used.

Total cached-input control runtimes: **42.679 / 43.717s**. Native mapping:
**41.063 / 42.153s**. Verification: **0s**. These exclude earlier matching,
calibration export and audit; they are not end-to-end runtime claims.

- First targeted run: **78 passed / 1 failed**. A new pose-prior fixture assumed
  six columns rather than the pinned schema's eight; corrected to explicit
  column names. This was a test fixture failure, not reconstruction behavior.
- Corrected early targeted run: **79 passed in2.38s**.
- Final targeted run: **81 passed in2.87s**, including **14 new control/audit cases**.
- Full regression: **263 passed in45.05s**, zero failures.
- An early CLI preflight rejected the experiment record because the new runner
  expected `xfeat` rather than the actual retained `xfeat_lighterglue` mode.
  Corrected source identity before output creation or native mapping. Retain that
  failed preflight log separately; only the two `_native.log` runs are results.
- One schema-inspection shell command failed quoting before execution. The
  successful direct PRAGMA read supplied the actual schema; no evidence was
  altered. No such diagnostic is represented as a completed experiment.

Reproduction uses new output directories; do not overwrite the retained evidence:

```powershell
.\.venv\Scripts\python.exe scripts/experimental_mapping_only.py --out demo/phase3_mapping_only/trial1
.\.venv\Scripts\python.exe scripts/experimental_mapping_only.py --out demo/phase3_mapping_only/trial2
.\.venv\Scripts\python.exe scripts/evaluate_mapping_only.py --out demo/phase3_mapping_only/evaluation
.\.venv\Scripts\python.exe -m pytest -q tests/test_mapping_only.py tests/test_fixed_intrinsics.py tests/test_transition_odometry.py tests/test_xfeat_context.py tests/test_transition_context.py tests/test_transition_tracks.py tests/test_transition_matchers.py
.\.venv\Scripts\python.exe -m pytest -q
```

Native output was captured by `subprocess.run(..., stdout=log, stderr=STDOUT)`
in UTF-8, avoiding PowerShell's native-stderr wrapping. Runtime is recorded only
for complete results. [Compact hashed evidence](../results/phase3_mapping_only_summary.json)
pins new scripts/tests, this record, raw logs, candidate DB/WAL/model bytes and
the read-only evaluation. Large artifacts remain ignored under `demo`.

## Causal conclusion and decision

**A: measured partial geometric improvement**, versus both original batch020 and
the preceding batch022 control. This is not B (connectivity-only gain): graph
connectivity and 32-view membership remain unchanged versus batch022 while
independently audited target rotations/directions/relative lengths improve.
It also does not close the geometry failure: late orientation, direction-tail
regressions, raw contradictions and solver warnings remain.

**Mapping-stage calibration is a demonstrated contributor.** Batch020's large
transition failure can be substantially reduced without changing matches or
verified inlier rows. Therefore calibrated re-verification is not required for
those gains, and its60 changed rows cannot be the sole explanation. This control
still bundles nominal intrinsic initialization, prior status and intrinsic
locking; it does not isolate which of those individual policies matters most.

**The remaining error is not proven to be a mapper software defect.** The same
ambiguous correspondence graph enters mapping, supplied sensor covariance is
unknown, and calibration/distortion accuracy lacks independent proof. These
results do not distinguish incorrect landmark support, geometric degeneracy,
native optimization behavior and sensor/optical uncertainty. Do not assign the
entire residual to mapping or patch a solver based only on its warnings.

Independent-support classification remains **B: partially sensor-consistent but
questionable**. **Keep XFeat experimental and production SIFT unchanged.** No
production fix, commit or push is justified by this batch. No new open-source
dependency or restricted code/assets/models are introduced; documented A/B and
COLMAP research is reused rather than repeated.

New files: `scripts/experimental_mapping_only.py`,
`scripts/evaluate_mapping_only.py`, `tests/test_mapping_only.py`, this record and
the compact JSON summary. Existing research, design, status, roadmap, operations
and source decisions receive a current evidence notice. All older pinned records
remain unchanged. No unrelated refactoring or implementation is included.

REQ-03/05/10/27/29 remain **PARTIALLY IMPLEMENTED**. This improves causal video
geometry evidence, not a complete metric property, video-wall gate, actual drift
correction/footprint ablation, physical benchmark or full Fix Loop acceptance.
Floor remains **25/176** covered samples; the **0.702677m ceiling boundary shift
is still unvalidated**. Independent survey, same-property three-tier captures and
repeats, damage labels, calibrated intervals, consumer comparison, official
schema/gates and cold walk-in evidence remain outstanding.

**Single next technical step:** audit the saved **31->34** landmark support for
feature-identity conflicts and triangulation-angle distribution, using this
frozen database/model to localize its **6.520814deg** orientation disagreement
before changing matching, filtering or mapping. Earlier29-view results did not
register those late context views; this is new evidence to investigate, not a
repeat of the already completed matcher/verification comparisons.
