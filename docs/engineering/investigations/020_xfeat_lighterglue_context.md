# XFeat + LighterGlue on the retained 32-view RGB context

## Declared experiment

Use [batch 019](019_rgb_transition_context.md) as existing evidence; do not rerun
SIFT or DISK. Following [the component research](../alternative_approaches.md),
change only the experimental correspondence frontend. Ask whether XFeat's sparse
features and its trained LightGlue variant create consistent cross-group tracks
and a useful joint reconstruction. A connected pair graph alone is insufficient.
Production SIFT, geometry, calibration, mapping and acceptance remain unchanged.

The official XFeat-compatible matcher is **LighterGlue**, not the DISK checkpoint
with a different input tensor. Pin official revision
`e92685f57f8318b18725c5c8c0bd28c7fe188d9a`:

- [Official source and bundled weights](https://github.com/verlab/accelerated_features/tree/e92685f57f8318b18725c5c8c0bd28c7fe188d9a).
- [Apache-2.0 license](https://github.com/verlab/accelerated_features/blob/e92685f57f8318b18725c5c8c0bd28c7fe188d9a/LICENSE)
  governs the repository containing both checkpoints; no separate weight license
  or restricted terms were found. Retain its license and source provenance.
- `xfeat.pt`: SHA256 `0f5187fd7bedd26c7fe6acc9685444493a165a35ecc087b33c2db3627f3ea10b`.
- `xfeat-lighterglue.pt`: SHA256 `766102df37f11189efe5b0811d1f47c72b22629b79bfabfcfff9d2a2f84654b8`.
- Only the required unmodified source files and weights enter ignored `.tools`.
  No upstream source/checkpoint enters production or the submission package.
- Kornia's LightGlue implementation has an Apache-2.0 source header. Retain the
  installed Torch 2.6.0+cpu / torchvision 0.21.0+cpu / Kornia 0.8.1 / PyCOLMAP 4.2.1
  runtime used by prior trials; add no production dependency. Upstream's broader
  evaluation requirements list Kornia 0.7.2: the exact local version differs and
  checkpoint compatibility is therefore explicitly checked, not assumed.

## Fixed methodology

Use the same ordered 32 original RGB PNGs, timestamps, eight context anchors,
camera initialization metadata, 496 all-pairs combinations and target groups.
Never import saved optimized poses, sensor sidecars, survey scale or baseline
matches. Copy camera/rig/frame/image metadata into a new empty feature database.

Prespecify CPU, four Torch threads, seed 7, deterministic algorithms, maximum
dimension 1024 and maximum 2048 features (the prior learned trial's budget).
XFeat detection threshold 0.05 and LighterGlue confidence 0.1 remain upstream
defaults. Matcher: 64-D input, 96-D internal descriptors, six layers, one head,
depth confidence -1, width confidence 0.95. Disable CUDA FlashAttention on CPU.
Resize normalized RGB with bilinear antialiased interpolation. Preserve feature
indices; map keypoints back to original pixels and add 0.5 only at COLMAP import.
Never represent 64-D learned descriptors as SIFT descriptors.

All complete serialized downstream verification/mapping options must equal the
retained recipe. No threshold changes, forced initialization, pose import,
model concatenation or deletion of difficult frames. Existing native internal
initialization fallback is unchanged; saved output is not proof of strict
initialization suitability or physical correctness.

Run two independent fresh feature/database/model trials. Compare exact feature,
pair, geometry, model and camera-center repeats. Retain DB/WAL hashes; exclude
only mutable SQLite SHM read bookkeeping. Audit feature-ID tracks, exact triangle
composition, direct/group path matches, saved reprojection/cheirality and native
group-spanning tracks with the existing diagnostic functions.

## Loading check

An initial overly broad state-key check rejected the official bundled training
checkpoint before inference. Inspection found **no missing trainable matcher
parameters and no unequal loaded values**: extra entries belong to the training
extractor; Kornia computes its `confidence_thresholds` buffer internally. The
adapter explicitly allows only those two documented cases and requires every
trainable parameter and common checkpoint buffer to load exactly. Unknown or
missing parameter keys still fail. A targeted regression covers this distinction.
No downstream guard changes were made.

## Reproduction

After fetching the pinned files listed and hashed in the adapter into the ignored
snapshot cache, run native trials and validation serially:

```powershell
.\.venv\Scripts\python.exe scripts/experiments/experimental_xfeat_context.py --out demo/phase3_xfeat_context/trial2
.\.venv\Scripts\python.exe scripts/experiments/experimental_xfeat_context.py --out demo/phase3_xfeat_context/trial3
.\.venv\Scripts\python.exe scripts/evaluation/evaluate_xfeat_context.py --out demo/phase3_xfeat_context/evaluation2
# Retained read-only numeric/count-scope probe (ignored diagnostic artifact):
.\.venv\Scripts\python.exe demo/phase3_xfeat_context/numerical_probe.py
```

## Evidence status

The service restart interrupted the initial `trial1` during mapping. Its intact
database retains all 496 raw/verified rows, 85,439 stored match entries, 236 positive
verified pairs, 32 feature sets and no pose priors. It has no saved models or
completed experiment report. Original descriptor hashes and stage timers were
still in process memory and cannot be reconstructed as original measurements.
Retain this attempt separately; it is not a completed repeat or measured runtime.
Two full fresh trials (`trial2`/`trial3`) provide the declared reproducibility
evidence. The runner now saves frontend and verified-frontend reports before
mapping, preventing loss of that evidence on a future interruption. This changes
only diagnostic persistence; inputs, inference and downstream guards are intact.

## Completed results

The two fresh XFeat trials completed successfully. Reuse the completed SIFT/DISK
controls; neither was rerun. All backends use the same 32 inputs and guards.

| Metric | SIFT 32 | DISK + LightGlue 32 | XFeat + LighterGlue 32 |
|---|---:|---:|---:|
| Candidate matches | 15,299 diagnostic replay | 63,059 actual | **86,525 actual** |
| Verified pairs | 68 | 167 | **236** |
| Components including isolates | 12 | 1 | 1 |
| Isolated views | 8 | 0 | 0 |
| Unique registered views | 11 | 25 across two models | **29 in one model** |
| Sparse points per model | 1,012 | 1,931 / 1,404 | **5,455** |
| Mean reprojection residual, px | 0.636201 | 1.449190 / 1.337805 | **1.486099** |
| Joint target-group camera model | No | No | **Yes** |
| Joint endpoint 24/27 camera model | No | No | **Yes** |
| Saved point tracks spanning original groups | 0 | 0 | **0** |
| Actual same-input software repeats | Exact | Exact | **Exact** |

The XFeat model registers earlier anchors 16/19/22/23/24 and later anchors 27/28.
Later anchors 31/34/37 remain unregistered. No model is concatenated or aligned.
Joint camera membership is a real software reconstruction gain, but it does not
establish independently correct whole-property geometry. Intermediate views can
connect a valid chain without a point visible in both distant groups; absence
of a direct group-spanning point alone is not proof that the entire model is wrong.
It also supplies no positive direct landmark evidence to certify this connection.

Actual candidates are measured **before verification**. The final database has
85,439 stored entries: 193 nonempty rows with fewer than 15 candidates are cleared,
accounting for 1,086 entries. All other candidate rows are unchanged. The earlier
interrupted-attempt count was this final stored sum, not the original frontend
total. Do not mix these scopes or infer extraction loss from them.
The retained numerical probe also verifies that the interrupted attempt's six
database tables equal the completed trial's tables exactly. It still has no
completed model, retained descriptor hashes or measured full-run timing.

### Cross-group and geometric support

All 236 verified pairs are UNCALIBRATED. Maximum available stored-F Sampson
residual is **3.999920 px** under the unchanged 4 px guard. Direct endpoint 24/27
still has only six candidates and zero verified inliers. The shortest endpoint
path is 24 -> bridge03 -> 27, with 1,058 / 19 inliers; all 19 inliers on its weak
bridge edge belong to conflicting transitive components.

| Direct group pair | Candidates | Verified inliers | Same saved landmark matches |
|---|---:|---:|---:|
| 22 / 27 | 40 | 30 | 0 |
| 22 / 28 | 17 | 16 | 0 |
| 22 / 31 | 18 | 16 | 0; frame 31 unregistered |
| 23 / 27 | 24 | 21 | 0 |
| 23 / 28 | 16 | 16 | 0 |

These are new pairwise graph connections, not demonstrated direct 3D ties.
Labeled visualizations are retained in `evaluation2`. The reviewed 22/27 display
match 23 links a sofa/backrest edge to a hallway/baseboard location. It is a
visually suspicious, semantically inconsistent proposal; it is not retained as
the same native 3D point. Several remaining matches cluster along repeated
wall/floor junctions. This visual review is not a labeled precision benchmark.
Do not claim that the suspicious proposal survives the saved model, or that all
other proposals are independently known to be correct or incorrect.

### Track consistency and saved geometry

| Diagnostic | SIFT | DISK/LG | XFeat/LighterGlue |
|---|---:|---:|---:|
| Transitive feature components | 2,078 | 6,090 | 4,229 |
| Conflicting components | 59 | 960 | **778** |
| Observations in conflicts / total | 506 / 8,076 | 19,621 / 33,643 | **29,840 / 39,120** |
| Clean tracks with >=3 views | 1,166 | 1,946 | 1,341 |
| Clean group-spanning components | 0 | 5 | 6 |
| Clean endpoint-spanning components | 0 | 0 | **0** |
| Contradictory testable triangle compositions | 46 / 14,370 (0.32%) | 6,760 / 48,799 (13.85%) | **17,644 / 71,150 (24.80%)** |

All five XFeat endpoint-spanning raw components conflict. The largest contains
19,348 observations across all 32 views and reaches a same-image axis range of
**1,788.75 px**. Fewer conflicting components than DISK does not imply improvement:
large components merge contradictions. "Clean" only means consistent keypoint
identity, not physical correctness, sufficient parallax or a triangulated point.

The native model has **20,950 saved observations**, all with positive depth.
Observation residual min/median/p95/max is
**0.000341 / 1.510154 / 3.199323 / 3.999055 px**. All 5,455 saved XYZs are finite
in the additional read-only probe. There are 153 native point tracks with nearby
repeated image observations, with maximum axis range 7.5 px; these are distinct
from the enormous raw conflicts and are not automatically declared physical
errors. Optimized focal parameters range from 884.083 to 1,545.651 px, starting
from uncertain nominal RGB priors; this is not independent calibration evidence.

The copied-database native initialization audit finds **19 strict-suitable pairs**,
155 at the initial inlier count, and 41 at the initial angle condition.
Prior-conditional angle min/median/max is 0.081159 / 3.224248 / 84.036251 degrees.
These checks use RGB initialization priors, not measured physical motion.
Existing native initialization fallback remains unchanged. Each completed mapper
log contains **149 Cholesky linear-solver warnings**; successful output and low
residuals do not erase them or demonstrate a unique well-conditioned solution.

### Reproducibility and runtime

Both fresh runs reproduce all six compared database tables, feature hashes,
full matcher configuration, candidate/verified graphs and registered membership
exactly. All five model binary files are identical; maximum camera-center
difference is **zero**. No saved optimized poses enter either inference run.

- Fresh XFeat trial times: **396.151 / 391.438 s** (6.60 / 6.52 min).
- First completed run: extraction 14.805 s, matching 309.177 s,
  verification 0.358 s, mapping 63.354 s. Total also includes initialization,
  database preparation, diagnostics and provenance hashing.
- Retained fresh DISK/LG times: 1,449.757 / 1,506.607 s.
- Retained SIFT control times: 32.874 / 30.828 s, with cached features/pairs and
  separate candidate replay; do not report this as a fresh end-to-end speed ratio.
- These are bounded development timings, not clean-machine assessment timing.

### Diagnostic runtime correction and validation

The first read-only audit was stopped after identifying repeated work: it
rescanned each conflicting component once per member, including a 19,348-node
component. The measured comprehension would inspect **374,770,640 nodes**.
The isolated evaluator now memoizes the existing unchanged `track_spread` result
for each read-only component/coordinate object, retaining references to avoid ID
reuse and restoring the original function even on errors. No shared diagnostic
source or scientific criterion is edited. The successful audit reports 34,069
calls, 5,007 actual component calculations and 68,960 inspected nodes. It completes
in 8.59 s of command wall time. Only `evaluation2` is authoritative; incomplete
`evaluation` is excluded. Matching, verification and mapping were not rerun for
this correction. A regression checks exact spread equality and restoration.

- Latest targeted validation: **44 passed in 1.48 s**.
- Initial checkpoint smoke check failed as documented, then compatibility checks
  passed. Initial trial was interrupted externally; initial audit was deliberately
  stopped for redundant work. Neither is represented as a passing completed run.
  The standalone numerical probe initially lacked a repository import path; that
  diagnostic setup issue was corrected and the retained script completes.
- DB/WAL, retained controls and production hashes remain unchanged through audit.
- No production code changed; broader regression was not rerun per the requested
  scope. Previous full-suite result remains 205 passed, not a new result here.

## Decision and next step

**Reject production adoption for now; retain SIFT.** XFeat demonstrates a faster,
reproducible joint camera reconstruction, but the experiment does not establish
the required consistent cross-group geometry: raw contradictions worsen, direct
cross-group inliers do not survive as shared native landmarks, and solver warnings
remain. It is a useful experimental candidate, not a proven safe replacement.
Do not weaken verification or mapping to improve these numbers. No production
milestone is completed; **no commit and no push**.

REQ-03/05 RGB/property reconstruction evidence improves locally; whole-property
metric accuracy, completeness and acceptance remain partial. Floor coverage stays
**25/176**; the **0.702677 m ceiling shift** remains unvalidated. No physical survey,
capture repeat, true metric scale or assessment acceptance is claimed.

**Single next technical step:** audit the new 29-view model's relative camera
poses and indirect transition support against supplied odometry, using the
existing verified RGB/sensor timing correspondence. Withhold sensor poses from
inference; explicitly reject unsupported clock associations. This is sensor
consistency validation, not independent physical ground truth or metric acceptance.
It can determine whether the joint model's bridge is credible before trying another
frontend or considering an opt-in production integration.

See [compact evidence](../../../benchmarks/results/xfeat_context_summary.json).
