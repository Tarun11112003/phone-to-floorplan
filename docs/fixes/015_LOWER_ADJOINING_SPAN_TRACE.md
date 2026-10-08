# Batch 015: lower adjoining-span sensor and traversal audit

## Decision and scope

No reconstruction change is justified by this trace. Preserve batch 014's bounded
seed-selection fix, every current wall/cell/connection, and all existing finite
join/support guards. The query z=4.44 m, x=-2.73 to -0.44 m is an inspection
coordinate, **not a proposed boundary or surveyed wall**.

The retained producer is `floorplan/layout.py`, SHA-256
`a19a7c9fa23a3d61d177bc59e85143804fae3df6ae925c925e75ee7a1e8d3c1f`.
Baseline: `demo/phase3_strip_trace/current_exterior`. All `floorplan/*.py`
producer hashes, baseline input hashes and geometry artifact hashes are checked
by the trace; production source and frozen artifacts are unchanged.

## Sensor-to-support findings

`scripts/trace_adjoining_span.py::trace` backprojects all positive pixels in the
176 selected depth frames with their per-frame calibration and saved refined
poses. It compares original and extracted depth/confidence PNG byte hashes,
replays the actual stride-8 weighted voxel fusion exactly, and replays the
current proposal list exactly. It never emits walls or a plan.

| Stage in the +/-0.12 m query band | Result | Interpretation |
|---|---:|---|
| Positive depth pixels at existing wall heights | 2,828 | Repeated observations, not independent support |
| Range-valid pixels | 2,828 | The depth range guard loses none of these returns |
| Confidence 0 / 1 / 2 pixels | 868 / 473 / 1,487 | Confidence filtering is disclosed; not an extraction defect |
| Accepted confident pixels | 1,960 | Available selected-frame wall-height observations |
| Stride-8 accepted points | 29 | Production sampling, before voxel fusion |
| Fused wall-height points | 29 | No point-count loss in this query during fusion |
| Residual points | 9 | 20 explained points removed; not a hidden continuous surface |
| Fused points at all heights | 510 | Most lie outside the existing wall-height slab |

Only four of twelve x bins contain any fused wall-height points: 2, 1, 19 and
7 points respectively. Eight bins are empty. Of 20 points removed by the initial
support mask, 12 first belong to approximately horizontal planes and eight to
existing vertical planes. Removing that mask cannot create a continuous wall
from the original 29 sparse points. The region cannot independently supply
the existing 250-point plane consensus or 40-point finite-segment support guard.
Nearby planes can have sufficient support elsewhere; their global support does
not establish finite extent across this span.

The dense temporal audit reads **all 5,251** original depth/confidence pairs and
per-frame odometry/calibration at stride 8: **1,628** accepted query observations
from **133** frames. These are repeated, unfused observations in **raw odometry
coordinates**, not comparable to 29 refined/fused voxels. Dense temporal sampling
does reveal more returns; it does not by itself prove a connecting wall. This
audit does not rule out thin features between sampled pixels, nor establish what
a full-resolution all-frame reconstruction would recover.

## Traversal and measured-ray evidence

`crossing_rays` uses actual confident depth endpoints. A ray qualifies only when
its intersection with the query lies inside the x span and existing wall-height
slab, with **more than 10 cm of ray length on both sides**. This is a disclosed
diagnostic clearance, not a changed reconstruction or acceptance threshold.

- **132,289** confident measured rays cross the query in **16** selected frames.
- **115,983** of those rays have confidence level 2.
- All twelve x bins have crossing-ray evidence; count and height profiles are
  retained in `trace.json`. Observed crossing heights span approximately 0.25
  to 1.47 m above the existing sampling bound, not full ceiling height.
- The selected refined camera path crosses four times near x=-2.147, -1.548,
  -1.192 and -0.714 m, with 0.223-0.261 m steps and no declared path breaks.
- Selected raw poses also cross four times. All-frame raw odometry corroborates
  crossings at frame pairs 898/899, 992/993, 1052/1053 and 1168/1169, with
  0.0053-0.0162 m steps.

These returns contradict treating the entire queried span as a solid wall in
the supplied pose/calibration frame. They **do not** establish semantic door
identities, opening widths, physical absence of every partial wall, or cm accuracy.
They also do not prove the supplied trajectory is physically accurate.

![Selected-frame returns and support distribution](../../demo/phase3_adjoining_trace/lower_span/trace.png)

## Root-cause classification

| Candidate | Finding |
|---|---|
| Missing/insufficient sensor evidence | Insufficient continuous wall-surface support at this query; positive free-space evidence, rather than merely an unobserved span |
| Traversal/pose coverage | Traversal exists in raw and refined paths; no missing traversal or declared break explains a missing solid connector here |
| Depth/confidence extraction | Byte-identical payloads, exact fusion and unchanged range counts rule out selected-input extraction/fusion loss; low-confidence observations remain a sensor limitation |
| Residual/support selection | Only nine residual points, versus 29 before masking; no omitted continuous raw consensus demonstrated |
| Wall/junction geometry | No supported finite connecting span demonstrated; extrapolating the nearby right-hand wall is unjustified |
| Other software cause | No software-addressable connector omission established by this audit |

The original hypothesis that this query should be a lower enclosing wall is
unsupported. This is an **evidence limitation for that hypothesis**, not an
explanation of every remaining floor-completeness failure. Uncovered floor
samples and other unclosed boundaries still require investigation.

Independent survey/capture annotations must establish actual surface identity,
wall endpoints and openings, and validate pose/calibration. Retain original
captures, frame/pose identities, laser/tape dimensions and their measurement
uncertainty. Do not construct expected geometry from this query.

## Move to the next measurable bottleneck

Roadmap phase 2 is strict RGB video registration. The new audit
`scripts/audit_sfm_components.py::audit` opens the retained COLMAP database
**read-only**, inspects every saved sparse model and records input hashes.
It does not rematch, remap or change model selection.

For the original 72-budget AUTO trial (68 selected views):

- 139 verified pairs form **eight nontrivial components**, of sizes
  **16, 12, 8, 7, 7, 6, 2, 2**, plus **eight isolated images**.
- The saved sparse models contain **9 views / 1,104 points / 0.5501 px** mean
  reprojection error, and **10 views / 153 points / 0.8953 px** respectively.
- Their disjoint union is 19 views; the selected model remains **10/68**.
  Unioning disconnected models is not a common-coordinate reconstruction.
- The model groups have no verified-pair bridge. Selecting the larger model is
  consistent with the current architecture; changing selection to maximize point
  count would sacrifice view coverage and would not connect the property.
- No pair is classified CALIBRATED. This alone is not proof of bad calibration
  or unusable geometry; initialization/parallax still needs separate diagnosis.

The source-time gap between the two largest groups is now precisely located:
`frame_00024.png` at **11.55 s** and `frame_00027.png` at **13.066667 s**.
Selected intervening frames 25/26 at 12.066667/12.566667 s are isolated.
Exhaustive matching was already run on selected views, so repeating identical
pairs is not a new strategy. Next run one bounded **RGB-only bridge-view trial**
using extra original MP4 frames in that interval, retaining existing SIFT and
geometric verification guards. Measure new cross-component verified edges before
considering any mapper/stitching change; never borrow sensor sidecars.

No reference repository or external model was needed for this diagnosis. Retain
the existing COLMAP/voxel/support architecture. Forced connectors, weakened
confidence/plane guards, disconnected-model concatenation and arbitrary model
switching were considered as design options and rejected without being claimed
as executed experiments. Investigate a new matcher only if this bounded trial
shows a matching bottleneck that existing sampling cannot address.

## Validation and before/after boundary

The sensor trace completes with exact fusion and proposal replay. Fresh frozen
floor and ceiling layout replays each pass **15/15 checks**, including exact
wall segments, connections, cells, producer/dependency fingerprints and artifacts.

| Metric | Baseline | After this audit |
|---|---:|---:|
| Covered floor samples | 25/176 | 25/176 |
| Uncovered floor samples | 151 | 151 |
| Floor proposals / finite segments | 29 / 69 | 29 / 69 |
| Covered ceiling samples | 295/300 | 295/300 |
| Ceiling proposals / finite segments | 40 / 81 | 40 / 81 |
| Selected video model | 10/68 | 10/68 |
| Production geometry changes | 0 | 0 |

The ceiling's **historical 0.702677 m boundary shift remains unvalidated**.
Preserving it in exact replay neither justifies it nor proves accuracy.

The first targeted test run had **1 failed, 22 passed in 33.42 s**: two negative
ray-fixture endpoints actually intersected inside the allowed height/x span.
Correcting those endpoints, without changing ray logic, gives **23 passed in
30.68 s**. The final full suite passes **179 tests in 56.94 s**; its result is
also recorded in the hashed checkpoint.
No fresh end-to-end raw reconstruction was necessary for a diagnostic-only
batch; these are sensor replay, frozen layout regression and cached SfM audits.

This improves evidence for REQ-07/10/42 and diagnoses the REQ-03/05/27 video path;
**no whole requirement or assessment acceptance gate is newly closed**. Physical
calibration, measured accuracy, damage truth and the remaining acceptance holds
from batch 014 remain outstanding.

## Reproduction

Use fresh outputs and the unchanged matching producer; run native workloads
serially. These retained paths are local continuation dependencies, not a final
portable submission bundle.

```powershell
.\.venv\Scripts\python.exe scripts/trace_adjoining_span.py demo/phase3_strip_trace/current_exterior/floor --source datasets/Given_dataset/single_scan_floor_only/1a8384c3f6 --out demo/fresh_adjoining_trace --dense-sensor
.\.venv\Scripts\python.exe scripts/audit_sfm_components.py demo/phase3_sync_boundary/video_sampling_verified_input/video72/result/sfm --out demo/fresh_video_components
.\.venv\Scripts\python.exe scripts/verify_layout_artifact.py demo/phase3_strip_trace/current_exterior/floor --out demo/fresh_adjoining_floor_verification
.\.venv\Scripts\python.exe scripts/verify_layout_artifact.py demo/phase3_strip_trace/current_exterior/ceiling --out demo/fresh_adjoining_ceiling_verification
.\.venv\Scripts\python.exe -m pytest tests/test_adjoining_span_trace.py tests/test_sfm_components_audit.py tests/test_wall_completion.py tests/test_floor_boundary_audit.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

New files: the two audit scripts, their two targeted test files, this ledger and
`docs/results/phase3_adjoining_span_summary.json`. Active README, roadmap, design,
status, operations and alternative-decision documents link this checkpoint.
No `floorplan/` file was edited; no commit or push was made.
