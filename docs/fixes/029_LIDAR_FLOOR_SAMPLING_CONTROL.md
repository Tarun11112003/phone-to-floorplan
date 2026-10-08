# Supplied LiDAR floor completeness: bounded depth-density control

Date: 2026-10-08. The RGB registration chain is formally
[closed](028_FINAL_FRAME31_REPLAY.md); no earlier frames or registration solvers
are revisited. Use [component research](../ASSESSMENT_COMPONENT_RESEARCH.md) and
the existing floor sensor traces rather than repeating previous investigations.

**Selected gap:** floor-plan completeness on the supplied LiDAR floor scan,
supporting REQ-04/07/10/42. Only25 of176 retained camera positions are inside
accepted/inferred floor cells. This is a camera-position coverage diagnostic,
not a surveyed floor-area percentage. Incomplete boundaries prevent a reliable
whole-property output and affect more downstream requirements than cosmetic work.

## Evidence and hypothesis before any production edit

Current `floorplan/layout.py` SHA-256 remains
`a19a7c9fa23a3d61d177bc59e85143804fae3df6ae925c925e75ee7a1e8d3c1f`.
The source `demo/phase3_strip_trace/current_exterior/floor` reproduces exactly:
**15/15 frozen artifact checks pass**, including room corners, finite segments,
connections, dependencies and measurement-producer fingerprint. Baseline relevant
tests: **47 passed in21.41s**. No stale-result assumption is used.

The floor dataset contains5,251 matching depth/confidence identities, camera
matrix, IMU, odometry and RGB MP4. The control uses the same176 selected frames,
their per-frame depth intrinsics, and the retained refined sensor trajectory.
Every selected original depth/confidence PNG matches its extracted file byte-for-byte.
No frame, confidence threshold, depth range, pose, feature, match or verified row
changes. Sensor/odometry poses are legitimate inputs for this LiDAR tier; they
are not used to reopen or correct the RGB-only registration experiments.

Earlier traces already established:

- The left exterior plane omission was a seed-selection defect that was fixed;
  the bounded fix remains unchanged, but floor coverage stayed25/176.
- The queried lower adjoining span has sparse wall-height support and extensive
  measured crossing-ray/traversal evidence. A solid connecting wall there remains
  unjustified; increasing density does not authorize one.
- Selected extraction and weighted fusion reproduce exactly. There is no evidence
  of discarded files or corrupted depth/confidence extraction.

New question: does production's fixed stride8 spatial depth sampling contribute
to fragmentation elsewhere? It samples one of64 pixel locations. A stride4 control
retains the old sample lattice and adds observed pixels, without changing the
camera frames, confidence/range guards, 2cm voxel fusion, plane fitting, proposal
budgets, finite extent/junction guards or inferred-cell policy.

This is an isolated geometry control. Pose estimation/optimization is not rerun.
No sensor-assisted change is introduced into production RGB reconstruction.
No missing measurements, rooms, annotations or expected boundaries are invented.

## Evaluated approach and prior alternatives

Retain the existing weighted voxel fusion and raw-supported layout architecture.
The recorded research recommends preserving calibrated Stray ingestion; A/B
index assumptions and unsupported rectangles would weaken it. A's height-band
density/Hough candidates and B's projection modes offer candidate-generation
ideas, but our bounded raw-support searches already represent these concepts.

The existing shortlist also contains Open3D TSDF, PolyLayout and RoomFormer.
No noise/fragmentation evidence here establishes that replacing voxel fusion,
adding a learned room model or changing the architecture is necessary. First
evaluate the smallest input-density variable. No new external dependency,
checkpoint, research download or third-party implementation code is introduced.
Those alternatives are design candidates, not tested competitors in this batch.

## Result and preservation decision

| Metric | Retained stride8 | Isolated stride4 |
|---|---:|---:|
| Retained frames/poses |176|176, identical|
| Fused points |116,480|360,845|
| Wall-plane proposals |29|40|
| Retained finite wall segments |69|98|
| Accepted observed polygons |1|1|
| Inferred cells |1|3|
| Covered camera positions |25/176|79/176|
| Uncovered positions |151|97|
| Polygonization dangles |70|109|
| Complete/accuracy validated |No|No|

The stride8 cloud is reproduced **bit-for-bit** before the stride4 control runs.
The density control completes once in26.723s. This is an isolated local geometry
runtime, not a clean-machine/end-to-end assessment timing claim. It produces
more support and hypotheses but does not increase the observed-polygon count.
Its result remains partial under the unchanged acceptance guards.

The denser global fit chooses a different floor/wall basis. The original trial's
direct comparison of the two local coordinate systems was unsuitable: preserve
that preliminary result, mark its room comparisons superseded, and compare through
the **known sensor-world bases into the baseline floor frame**. No transform,
pose, scale or ground truth is fitted. The candidate footprint uses its reported
floor datum for this diagnostic projection. Tests distinguish a pure axis-sign
change from an actual dimensional change.

In the common frame, the accepted baseline polygon is **not retained**. Its
best-overlap candidate is inferred, with IoU0.004815 and only2.975% of baseline
area intersecting it. This is not a matched physical room or a dimension-error
measurement. The prior inferred cell's best-overlap observed candidate retains
60.767% of its area, with0.656936m boundary Hausdorff difference. The candidate
polygons have zero area overlap except8.54e-17m2 numerical residue in one pair;
nonoverlap alone cannot validate their identity or dimensions.

**Decision: reject changing the production sampling default.** A54-position
coverage increase, largely from inferred hypotheses, does not justify replacing
accepted geometry. No density-based reconstruction improvement is shipped.
No further native trial is needed to justify this rejection; candidate repeatability
has not been demonstrated. The existing stride8 result and guards remain unchanged.

## Root cause and what the supplied data can establish

Sampling density influences available plane/segment support and subsequent model
selection. However, denser observations alone are not a defensible completeness
fix: the fitted basis/proposals/topology also change and the prior accepted cell
disappears. This control does not isolate a concrete new software defect in
boundary logic or establish that raw evidence is insufficient for every other
unclosed region. Do not extrapolate the earlier lower-span finding to all151
uncovered samples.

Verified: selected sensor extraction, exact calibrated stride8 backprojection/
weighted fusion, exact baseline reconstruction artifacts, frozen poses, and unchanged
production/acceptance code. Internally observed: additional density changes the
model and inferred camera coverage. Not verified: semantic room identities,
physical floor boundaries, dimensional accuracy, independent repeats or deployment
uncertainty. The dataset has no independent laser/tape floor/wall survey or
annotated room/opening boundaries. Depth/pose agreement would be sensor consistency,
not independent centimetre accuracy.

## Validation, files and reproduction

New isolated code:
[experimental_lidar_sampling.py](../../scripts/experimental_lidar_sampling.py),
[evaluate_lidar_sampling.py](../../scripts/evaluate_lidar_sampling.py), and
[test_lidar_sampling.py](../../tests/test_lidar_sampling.py).
These do not enter production reconstruction. Initial focused checks pass61 tests
in21.46s. Additional tests cover known-basis comparison and preserve real geometry
changes. Final targeted checks: **69 passed in21.08s**. Full current-worktree
regression: **343 passed in39.93s**, zero failures. These are software regression
results, not accuracy or completeness passes;17 new tests cover the control.
The first trial script is retained as an ignored source snapshot matching its
recorded hash; the corrected evaluator does not rerun fitting or mutate that trial.

```powershell
.\.venv\Scripts\python.exe scripts/verify_layout_artifact.py demo/phase3_strip_trace/current_exterior/floor --out demo/lidar_floor_baseline_fresh
.\.venv\Scripts\python.exe scripts/experimental_lidar_sampling.py --out demo/lidar_floor_stride4_fresh
.\.venv\Scripts\python.exe scripts/evaluate_lidar_sampling.py --trial demo/lidar_floor_stride4_fresh --out demo/lidar_floor_stride4_evaluation.json
.\.venv\Scripts\python.exe -m pytest -q tests/test_lidar_sampling.py tests/test_wall_completion.py tests/test_wall_planes.py tests/test_supported_cells.py tests/test_layout_artifact.py tests/test_rgbd.py tests/test_ceiling.py tests/test_adjoining_span_trace.py tests/test_boundary_comparison.py
.\.venv\Scripts\python.exe -m pytest -q
```

Use fresh output names, retain UTF-8 stdout/stderr, and run native workloads
serially. These commands depend on retained local artifacts/intake paths; they
are not a clean-clone acceptance rehearsal. No production code, old model,
threshold, input or unrelated uncommitted work changes. No meaningful production
milestone is completed, so **no commit or push** is made.

Evidence: [compact summary](../results/phase3_lidar_sampling_summary.json),
`demo/phase3_lidar_sampling/floor_baseline/verification.json`,
`stride4_trial/experiment.json`, `evaluation.json`, source snapshot and test logs.
Current status, operations, design, roadmap, component research and alternative
decision records receive this result without erasing previous evidence.

## Requirement status and next focused component

REQ-04 supplied LiDAR integration receives additional verified sensor replay
evidence; native phone/cold-route acceptance stays pending. REQ-07/10 remain
partial: production floor coverage stays25/176 and property closure/adjacency
is unresolved. REQ-42 gains retained commands, artifacts and producer/input hashes,
without establishing final portable delivery. RGB registration remains CLOSED.
The historical0.702677m ceiling-boundary shift and all physical acceptance holds
remain unchanged. Opening/damage truth, calibration properties, surveyed benchmark,
Fix Loop, consumer comparison, official schema and cold/walk-in evidence remain open.

**Single next assessment step:** audit the original versus shifted ceiling-scan
boundary using retained source geometry and confident per-frame depth rays;
measure finite surface support and free-space contradictions for the0.702677m
change before changing ceiling or boundary logic. This is sensor-conditional
validation, not a substitute for an independent physical survey.
