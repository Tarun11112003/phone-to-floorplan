# Retained transition: correspondence safety and sparse-model audit

## Scope and research decision

Read [assessment component research](../ASSESSMENT_COMPONENT_RESEARCH.md) first.
Its relevant conclusion is to retain COLMAP and its correctness guards, evaluating
matcher alternatives by registered target views and usable geometry, not match
counts. A/B's external-pose and assumed-camera approaches do not resolve this
RGB-only correspondence question. No further upstream investigation or dependency
installation was needed: the documented DISK option and retained artifacts cover it.

This is a read-only follow-up to [batch 017](017_DISK_LIGHTGLUE_TRANSITION.md).
Exactly the same 24 RGBs, pinned implementation/checkpoints, camera initialization
priors, geometric verification and mapping options are retained. No new feature
inference or mapping runs were performed in this follow-up. The independently
executed repeats from 017 were reverified against current database/model bytes.

`scripts/audit_transition_tracks.py` adds diagnostic union-of-observation tracks,
exact feature-ID triangle consistency, weak-edge spatial support and labeled match
visualizations. It reads frozen databases using SQLite read-only connections and
hashes every retained trial file and production Python source before/after.
It never filters matches, changes guards, registers cameras or merges models.

## SIFT versus DISK + LightGlue

| Same 24-view result | SIFT | DISK + LightGlue |
|---|---:|---:|
| Candidate pairs | 276 | 276 |
| Candidates | 7,931 diagnostic replay | 42,224 actual imported |
| Verified pairs | 39 | 109 |
| Components, including isolates | 10 | 1 |
| Isolated views | 7 | 0 |
| Endpoint graph path | Absent | Present |
| Native strict initialization-suitable pairs | 1 | 0 |
| Largest saved model | 2 views, 371 points | 2 views, 67 points |
| Saved-model mean reprojection residual | 0.297695 px | 1.000242 px |
| Models containing both endpoints | 0 | 0 |
| Saved points with tracks longer than two views | 0 | 0 |

SIFT candidates are the previously declared native diagnostic replay, not historic
raw pipeline counts. Local model residuals are internal and concern different point
sets; they do not independently prove either model's dimensional accuracy.

## Which connections exist, and which guards do they survive?

The retained set contains only `frame_00024.png` from the original 12-view group
and `frame_00027.png` from the original 16-view group. Thus this measures an
endpoint proxy, not a merger of both complete original groups.

LightGlue adds 57 edges between previously separate SIFT components. Its shortest
verified endpoint path has these actual candidate/inlier counts:

| Edge | Candidates | Verified inliers | Geometry |
|---|---:|---:|---|
| frame_00024 -> bridge_00002 | 1,321 | 1,243 | UNCALIBRATED |
| bridge_00002 -> frame_00025 | 30 | 23 | UNCALIBRATED |
| frame_00025 -> frame_00027 | 21 | 18 | UNCALIBRATED |

All three survive the unchanged pairwise minimum of 15 inliers and 4 px RANSAC
verification. All 109 learned verified pairs are UNCALIBRATED. Maximum stored-F
Sampson residual remains 3.999057 px. The direct 24/27 pair has only 13 candidates,
zero verified inliers and no accepted geometry. None of the three shortest-path
edges is individually indispensable: alternative pairwise graph paths exist.

**The connections do not survive into a jointly registered sparse model.** Saved
LightGlue views are only `frame_00026.png` and `bridge_00018.png`; SIFT saves only
`bridge_00004.png` and `bridge_00005.png`. Neither registers either endpoint in
the saved model. Existing COLMAP internal initialization fallback produces these
local two-view models; it does not establish the original strict initialization
criterion. No application option or acceptance requirement was relaxed.

Native strict suitability is the previously measured installed-API result, now
bound to unchanged database hashes. Conditional pose angles and stored fundamental
inlier counts are not interchangeable with the native mapper's essential-geometry
tests. Motion, intrinsic calibration and feature errors are not uniquely separated
by these diagnostics.

## New safety evidence

A diagnostic track is a connected component of `(image, keypoint index)`
observations joined by verified pair correspondences. A track with more than one
keypoint from the same image is explicitly conflicting; it is not silently
converted to a usable 3D track.

| Track diagnostic | SIFT | DISK + LightGlue |
|---|---:|---:|
| Observation components | 1,591 | 5,942 |
| Conflicting components | 36 | 978 |
| Components with same-image separation >4 px | 20 | 978 |
| Components with same-image separation >12 px | 10 | 736 |
| Clean tracks spanning at least three views | 816 | 2,017 |
| Endpoint-spanning observation components | 0 | 4 |
| Clean endpoint-spanning tracks | 0 | 0 |
| Directly testable triangle compositions | 5,203 | 18,542 |
| Contradictory compositions | 13 (0.25%) | 2,879 (15.53%) |

Triangle counts reuse observations and are not independent labeled samples or
false-match rates. Clean feature tracks alone also do not demonstrate calibrated,
triangulatable 3D geometry. The 4/12 px bins above are descriptive diagnostics,
not newly introduced correctness gates.

All four learned endpoint-spanning components are conflicting. Their maximum
within-image axis ranges are **1,063.125, 973.125, 770.625 and 18.75 px**. These
are lower bounds on separation between distinct observations within an image,
not world-space errors. The large components cannot be explained solely by
subpixel duplicate features. This establishes incompatible correspondence
identities, without uniquely identifying every incorrect edge.

On the two weak shortest-path edges, **16/23** and **14/18** inliers participate
in components with same-image separation above 12 px. Participation is a
transitive diagnostic: it does not assert every such pair's match is false.

The 18-inlier frame25/27 edge covers only 6 and 5 cells of an 8x8 image grid;
inlier convex hulls span approximately 11.13% and 10.38% of the images. The
23-inlier edge spans 9/8 cells and approximately 16.57%/10.12% hull area.
Labeled visualizations show repeated floor/cabinet-edge concentration. In
frame25/27, indices 0/1 appear to link wooden cabinet-handle locations to tiled
floor/boundary locations. These are suspicious visual correspondences, not
independently adjudicated physical labels. The broad graph therefore must not
be interpreted as reliable property connectivity.

## Reproducibility, regression and decision

Two complete audit executions (`track_safety2`, `track_safety3`) reproduce all
run diagnostics, original group identities, trial-file hashes, production hashes
and audit-script hash exactly. The original two completed runs per matcher still
have identical contents in all six compared database tables, identical graph
diagnostics and identical model binaries/camera centers. This rechecks existing
independent inference runs; it is not a new physical repeat or new inference run.

- Targeted safety/video tests: **26 passed in 1.38 s**.
- Full regression: **198 passed in 61.08 s**. No failures.
- Original inputs, production sources and guard settings remain unchanged.

**Reject DISK + LightGlue for production on the evidence available.** It produces
a reproducible pairwise graph gain but no joint 3D reconstruction, with substantial
correspondence-identity conflicts. This does not reject every possible use of the
matcher; it rejects adopting this configuration to solve the measured transition.
No production milestone was completed, so no commit was created and nothing was
pushed. The baseline's own conflicts and partial registration remain unresolved.

Floor coverage remains **25/176**, and the **0.702677 m ceiling-boundary shift**
remains unvalidated. Physical accuracy and assessment acceptance are not established.

## Reproduction and single next step

Use fresh output directories; the script deliberately refuses overwrite:

```powershell
.\.venv\Scripts\python.exe scripts/audit_transition_tracks.py --out demo/fresh_transition_track_safety
.\.venv\Scripts\python.exe -m pytest -q tests/test_transition_tracks.py tests/test_transition_matchers.py tests/test_video_bridge_trial.py tests/test_sfm_components_audit.py tests/test_sfm_diagnostics.py
.\.venv\Scripts\python.exe -m pytest -q
```

Requires retained batch-017 inputs, not a fresh-clone turnkey package. Compact
measured results and full-artifact hashes are in
[the safety summary](../results/phase3_transition_track_safety_summary.json).

**Next:** run the previously proposed matched 32-view SIFT/DISK+LightGlue context
comparison, adding original RGB anchors **16/19/22/23/28/31/34/37** and retaining
all 24 current views. Withhold previous optimized poses and retain all guards.
Require a single model spanning both original groups and inspect track consistency
before considering adoption. The context hypothesis is untested; this experiment
must not be presented as a successful fix.
