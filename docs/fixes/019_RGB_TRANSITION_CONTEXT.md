# Matched 32-view RGB context experiment

## Declared scope

Continue [the retained-track safety audit](018_TRANSITION_TRACK_SAFETY.md).
Preserve all 24 transition images and add original RGB anchors
**16/19/22/23/28/31/34/37**. They supply observed context from the two original
groups, not camera poses. Use the original 88-view density database only for
initial camera/image/rig/frame metadata and retained SIFT feature/pair rows.
Saved optimized sparse poses, depth, confidence, odometry, IMU and survey scale
are excluded from inference. No optimized model is loaded by the trial runner.

The pinned DISK/LightGlue recipe is unchanged from batch 017. Both backends use
the same 32 RGB PNGs, source times and camera initialization priors. Each is run
twice in independent fresh databases. All **496** possible pairs are evaluated.
The shared learned-matcher function retains an old `/276` progress-log denominator;
actual pair records and pair files must contain 496 entries. That log text is
not a different sampling or matching recipe.

Complete serialized verification/mapping options must match the frozen density
experiment: minimum 15 pair inliers, 4 px RANSAC, seeded CPU execution, original
100-inlier/16-degree initialization and existing pose/focal/track filters. No
forced initialization, threshold relaxation, sparse-model concatenation, manual
alignment or removal of difficult views is allowed. Existing native internal
fallback remains unchanged and is reported separately from strict suitability.

## Question and decision rule

Does extra RGB context provide sufficient legitimate multiview constraints to
recover one model containing members of both original groups under the current
guards? Also report original endpoints 24/27 separately: a group-spanning model
and an endpoint-spanning model are distinct results.

Measure graph connectivity, isolates, exact feature-ID cycles/transitive conflicts,
clean group-spanning tracks, registered views, native point-track structure,
positive depth, reprojection residuals and exact same-input repeats. Compare all
original feature/pair rows against the 24-view baseline, including zero rows.
Raw graph growth is insufficient for adoption; pointwise residuals do not establish
physical correctness or metric accuracy. Any production integration additionally
requires a reproducible joint result and review of suspicious correspondences.

This is a development experiment, not the physical benchmark's prospective Fix
Loop. Floor coverage **25/176** and the unvalidated **0.702677 m** ceiling shift
remain untouched.

## Reproduction

Use fresh paths and run native reconstruction/tests serially. Retained batch-017
inputs and the isolated pinned dependency cache are required.

```powershell
.\.venv\Scripts\python.exe scripts/experimental_transition_context.py --mode sift --out demo/phase3_transition_context/sift1
.\.venv\Scripts\python.exe scripts/experimental_transition_context.py --mode sift --out demo/phase3_transition_context/sift2
.\.venv\Scripts\python.exe scripts/experimental_transition_context.py --mode lightglue --out demo/phase3_transition_context/lightglue1
.\.venv\Scripts\python.exe scripts/experimental_transition_context.py --mode lightglue --out demo/phase3_transition_context/lightglue2
.\.venv\Scripts\python.exe scripts/compare_transition_context.py --out demo/phase3_transition_context/comparison2
```

The SIFT control copies source feature/pair rows and separately replays candidates;
the learned backend freshly extracts and matches. Runtime scopes differ and must
not be presented as a fresh end-to-end speed ratio. Source, production, helper,
checkpoint, package and image hashes are retained. Documentation will record the
completed comparison before any adoption decision.

## Completed results

| Metric | SIFT 24 control | SIFT 32 context | DISK/LG 24 control | DISK/LG 32 context |
|---|---:|---:|---:|---:|
| Candidate pairs | 276 | 496 | 276 | 496 |
| Candidates | 7,931 replay | 15,299 replay | 42,224 actual | 63,059 actual |
| Verified pairs | 39 | 68 | 109 | 167 |
| Components including isolates | 10 | 12 | 1 | 1 |
| Isolated views | 7 | 8 | 0 | 0 |
| Largest model | 2 views | 11 views | 2 views | 15 views |
| Unique views across saved models | 2 | 11 | 2 | 25 |
| Saved sparse points by model | 371 | 1,012 | 67 | 1,931 / 1,404 |
| Mean reprojection residual by model, px | 0.297695 | 0.636201 | 1.000242 | 1.449190 / 1.337805 |
| Joint original-group model | No | No | No | No |
| Joint endpoint 24/27 model | No | No | No | No |

The learned 32-view output has **two separate models, 15 and 11 views**. Their
one shared registered image means 26 view memberships correspond to 25 unique
images. Their point counts are separate-gauge model sizes, not a unique stitched
world-point count. SIFT's model registers only the earlier group. Learned model 0
registers original earlier-group members 16/19/22/23/24; model 1 registers only
later-group members 27/28. The other three later anchors are unregistered.

Extra context therefore improves **local reconstruction**, but does not resolve
the target-group reconstruction bottleneck. It is not a measured accuracy gain.
Residuals refer to different reconstructed point sets and cannot establish a
dimensional comparison or an independent geometric ground-truth result.

### Pairwise connections and suspicious edges

All original 24-view camera/image/keypoint/descriptor/match/two-view rows,
including zero-match rows, are unchanged in both enlarged databases. The learned
endpoint path therefore still uses the audited edges **24 -> bridge02 -> 25 -> 27**,
with **1,243 / 23 / 18** inliers. The previously identified unsafe correspondence
support has not been repaired by adding context.

The shortest original-group path is now the direct **frame37 -> frame23** edge:
**39 candidates, 20 verified inliers, UNCALIBRATED**. Its labeled visualization
shows sofa/backrest-edge locations matched to door/dark-entry-edge locations.
These are visually suspicious, semantically inconsistent correspondences; this
is not an independently labeled full match-accuracy benchmark. No valid group
connection should be inferred from this short graph path.

The unchanged verification accepts the pairwise graph: 167 learned verified
pairs, all UNCALIBRATED, maximum available stored-F Sampson residual **3.999905 px**.
SIFT has 68 pairs and maximum available Sampson residual **3.976709 px**. Neither
backend yields a group-spanning registered model. Geometry/model guards were
never relaxed to promote these paths.

### Track and sparse-model safety

| 32-view diagnostic | SIFT | DISK + LightGlue |
|---|---:|---:|
| Conflicting observation components | 59 | 960 |
| Components with same-image separation >12 px | 15 | 776 |
| Clean tracks with at least three views | 1,166 | 1,946 |
| Original-group-spanning observation components | 0 | 15 |
| Clean original-group-spanning components | 0 | 5 |
| Clean endpoint-spanning tracks | 0 | 0 |
| Directly testable triangle compositions | 14,370 | 48,799 |
| Contradictory compositions | 46 (0.32%) | 6,760 (13.85%) |
| Reconstructed point tracks spanning original groups | 0 | 0 |
| Nonpositive-depth saved observations | 0 / 5,406 | 0 / 12,765 |
| Maximum saved-observation reprojection residual | 3.925019 px | 3.975721 / 3.886333 px |

"Clean" means no duplicate image/keypoint identity conflict in the transitive
component; it does not certify correct physical correspondence, usable parallax
or a triangulated point. The five clean group-spanning components do not enter
a saved group-spanning model. The four endpoint-spanning learned components all
remain conflicting, with within-image axis ranges reaching **1,379.999878 px**.

Native saved points sometimes contain nearby repeated image observations: 35
SIFT point tracks and 16/7 learned point tracks; maximum same-image axis ranges
are 4.756836 and 5.625 px. These are distinct from the large raw transitive
conflicts and are not declared physical errors. Native reprojection/cheirality
diagnostics support internal local-model consistency only.

The learned models share only **bridge_00017.png**. They reconstruct just **one
identical keypoint index** there, with **zero** links whose 3D tracks support
opposite original groups. A single positive depth ratio (0.182239) is merely a
local gauge diagnostic, not a scale calibration or validated registration. No
alignment, concatenation or merge is attempted; there is insufficient common
landmark support to justify one under the current correctness requirements.

### Reproducibility, timing and an audit correction

Both independently executed repeats reproduce all six compared database tables,
feature outputs, candidate counts, verified geometry, components and model
memberships exactly. All saved model binary files are identical, and maximum
raw camera-center difference is **zero** for every repeated model. These are
software repeats, not independent captures.

SIFT elapsed times are **32.874 / 30.828 s**, reusing source features/pairs.
Learned elapsed times are **1,449.757 / 1,506.607 s** (24.16 / 25.11 min), with
fresh features and all-pair matching. Do not report these as comparable fresh
end-to-end speed ratios. The CPU learned experiment alone exceeds 15 minutes,
but it is not the assessment's clean-machine timing measurement.

The first integrity comparison failed because its blanket file-hash guard
included SQLite's mutable **shared-memory read marks (`features.db-shm`)**.
Read-only SQLite queries can update that bookkeeping. The corrected diagnostic
excludes only `.db-shm`, retains immutable **database plus WAL** hashes and still
checks exact table/model contents. A regression verifies that changing WAL data
fails integrity while changing SHM read marks does not. The successful output is
`comparison2`; the failed partial `comparison` is excluded from final evidence.
Do not copy a WAL-backed database without its WAL: use a coherent SQLite backup
or retain both files. Original geometry, options and scientific data are unchanged.

- Targeted tests: **33 passed in 2.28 s**.
- Full regression: **205 passed in 54.96 s**; no remaining test failures.
- One comparison validation failed as described above; corrected rerun passed.
- No production reconstruction, geometry or acceptance code changed.

## Decision and assessment effect

**Retain production SIFT; do not adopt DISK + LightGlue from this experiment.**
Local completeness increases, but neither backend solves the joint-group goal.
Learned cross-group support remains suspect and CPU cost is substantial. The
experiment does not establish the required whole-property video geometry,
metric wall errors, independently calibrated uncertainty or physical acceptance.
REQ-03/05 and related phase-2 geometry requirements remain partial.

The consolidated research already recommends evaluating CPU-friendly
**XFeat + LighterGlue** at this correspondence bottleneck. No fresh A/B source
research, architecture import or additional dependency was needed in this pass.
No production milestone was completed: **no commit and no push**.

Floor coverage remains **25/176** and the **0.702677 m ceiling-boundary shift**
remains unvalidated. No physical survey or capture evidence is fabricated.

See [compact hashed results](../results/phase3_transition_context_summary.json).

**Single next step:** run a pinned **XFeat + LighterGlue 32-view comparison** on
these exact inputs with unchanged verification/mapping guards, checking package
and checkpoint rights before use. Require usable joint-group geometry, inspect
track consistency and measure actual CPU runtime before any adoption decision.
