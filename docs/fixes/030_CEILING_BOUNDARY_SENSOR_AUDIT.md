# Ceiling-scan boundary shift: original sensor evidence audit

Scope is exclusively the historical 0.702677 m boundary change
in `single_scan_with_ceiling`. Production reconstruction, accepted geometry,
sampling, matching, poses and acceptance guards are unchanged. The RGB registration
investigation remains CLOSED and XFeat remains experimental.

**Decision:** retain the current production baseline with its boundary-accuracy
warning. The shift's software mechanism is identified, but neither footprint is
independently validated. No reproducible implementation defect justifies another
geometry edit, and no production fix or commit is made.

## What the shift actually represents

The historical frozen residual-wall comparison changes one existing floor-plan
polygon, original `room_1` to current `room_2`. It does not translate an entire
wall uniformly and does not measure a change in ceiling height. It cuts a notch
from the polygon's lower-right corner in the shared floor basis.

| Metric | Historical original | Historical shifted/current | After this audit |
|---|---:|---:|---:|
| Affected polygon area | 10.477367266 m² | 9.945719535 m² | 9.945719535 m², unchanged |
| Removed area | — | 0.531647731 m² | Unchanged |
| Polygon/boundary Hausdorff difference from original | — | 0.702677028 m | Unchanged |
| Affected room scalar ceiling height | Unavailable (`null`) | Unavailable (`null`) | Unavailable |
| Covered camera positions, full ceiling-scan plan | 148/300 | 295/300 | 295/300, unchanged |
| Physical accuracy independently validated | No | No | No |

The earlier coverage gain is a camera-position diagnostic, not a measured floor
area or accuracy improvement. Eight observed polygons plus four inferred cells
are not proof of twelve actual rooms. Scalar ceiling height is unavailable for
all eight observed current ceiling-scan polygons; this audit does not investigate
their ceiling-plane rejection paths.

The changed region is approximately x = -5.997 to -5.294 m and z = 0.157 to
0.923 m in the retained floor basis. Its two new edges are:

- Horizontal: `(-5.306930, 0.923184)` to `(-5.995392, 0.920433)`.
- Inner vertical: `(-5.995392, 0.920433)` to `(-5.996928, 0.157486)`.

The two replaced portions are the original outer right and bottom edges. Their
original observed planes remain in the wall network. An additional residual
horizontal plane near z = 0.92 m joins an **already present** finite inner wall
near x = -5.997 m, introducing the notch in polygonization. This is boundary
proposal/finite-junction model selection, not a newly measured sensor displacement.

## Sources, calibration and controls

Source: `datasets/Given_dataset/single_scan_with_ceiling/c7d28f72c6`.
The case contains 6,899 depth PNGs, 9,745 confidence PNGs and 9,745 odometry rows;
confidence/pose identities without a depth PNG cannot supply missing depth. The
audit uses the original 300 selected, matching depth/confidence identities from
the retained run; it does not change the frame selection or infer absent data.

- Source depth/confidence are 256 × 192, and RGB calibration dimensions are
  1920 × 1440. Depth is converted from the supplied millimetres to metres.
- Every selected original depth/confidence PNG is byte-identical to its extracted
  retained file. Accepted depth uses the existing 0.2–8 m range and confidence
  >= 1; confidence-2 counts are reported separately.
- Each frame's intrinsics are checked exactly against `odometry.csv` and scaled
  by the original RGB/depth dimensions. The standalone `camera_matrix.csv` is
  not substituted for per-frame calibration.
- Every normalized raw camera pose exactly reproduces its original odometry
  translation and normalized optical quaternion. The source convention is retained;
  no additional coordinate flip or fitted alignment is introduced.
- Both original raw sensor poses and retained refined LiDAR poses are audited.
  No new pose estimation, refinement, optimization or reconstruction is performed
  by the sensor audit. These are two representations of the same capture, not
  two independent surveys.
- The historical comparison uses an exactly common floor basis, floor datum,
  frozen cloud and source trajectory. Only the residual-wall proposal stage changes.
- Replaying the selected source stride-8 points, original confidence/distance
  weights and 2 cm weighted voxel fusion reproduces the original **202,477-point
  cloud bit-for-bit**. Fusion/extraction loss is not the cause of this controlled
  shift. Pixels outside that sampling lattice are also inspected for local support.
- A fresh current-baseline layout replay passes **15/15 exact checks**, including
  all room corners, segments, connections, geometry dependencies and measurement
  producer. Production layout SHA-256 stays
  `a19a7c9fa23a3d61d177bc59e85143804fae3df6ae925c925e75ee7a1e8d3c1f`.

This verifies the selected original observations and reproducibility of this
comparison. It does not rule out useful observations in other unselected frames,
prove sensor scale accuracy, or independently calibrate phone intrinsics/poses.

## Exact plane and finite-edge support

The read-only auditor associates each changed edge to its saved observed network
segment and a **unique exact fitted-plane identity**. It does not choose an
approximate nearby wall or borrow support from a distant portion of that plane.
Ray intersections use the actual tilted 3D fitted plane, not a falsely vertical
extrusion of its 2D footprint.

The new horizontal source is residual plane index 51 in the controlled combined
plane list (network segment 30). Its source records 786 residual supporting voxels,
211 occupied cells, 2.631 m robust height span across its **whole** extent and
0.0121 m plane RMS. The inner vertical is pre-existing source plane index 24
(old network 27, current network 32). Whole-plane support alone does not establish
full-height support along the finite notch edges.

Local fused support uses the existing 35 mm plane band and 0.25–3 m wall-height
slab above the supplied floor datum. Crossing rays must intersect within the
queried finite extent, with measured endpoints beyond the fitted plane and
**more than 10 cm clearance on both sides**. These are diagnostic settings from
the earlier sensor traces, not measurement-accuracy or assessment tolerances.

| Queried finite edge | Fused local points | Refined support pixels | Refined confidence-2 crossing rays | Raw support pixels | Raw confidence-2 crossing rays |
|---|---:|---:|---:|---:|---:|
| Original outer right | 797 | 55,811 | 611 | 61,774 | 36 |
| Original outer bottom | 699 | 46,362 | 22,113 | 7,331 | 74,137 |
| New horizontal notch | 964 | 70,765 | 84,203 | 98,177 | 82,061 |
| Existing inner vertical used by notch | 1,054 | 92,173 | 73,145 | 96,234 | 85,877 |

Support counts include confidence 1 and 2. Crossing counts in the table are
confidence 2 only. They are repeated unfused pixel observations, not independent
measurements, unique landmarks, surveyed walls or probabilities.

The new horizontal notch has support in 20 selected frames under both pose modes;
its crossing rays occur in 13 refined / 14 raw-pose frames. The inner vertical has
support in 23 frames and crossing rays in 22 under both modes. Refined stride-8
support counts are 1,085 and 1,392 respectively, with another 69,680 and 90,781
accepted pixels outside that sampling lattice. A lack of sampled returns is not
the explanation for these two local surfaces.

Height distributions distinguish observed low surfaces from a full-height wall:

- **Horizontal notch:** 64,610/70,765 (91.3%) refined supported returns are below
  1.5 m. Of 84,203 refined confidence-2 crossing rays, 83,882 (99.6%) cross at
  heights >= 1.5 m. Raw poses show the same low-support/upper-crossing pattern.
- **Inner vertical:** 89,100/92,173 (96.7%) refined supported returns are below
  1.5 m. Its finite fused-support 5th–95th-percentile height span is only 0.983 m,
  despite tall outlying points elsewhere/along that plane.
- The old outer bottom is sensitive to raw versus refined poses. The original
  footprint is therefore not independently justified by this audit either.

![Original and retained footprint, with local height-resolved support and crossing rays](../../demo/phase3_ceiling_shift/boundary_sensor_evidence.png)

The figure is generated from the saved audit only. Confidence >= 1 support and
crossings are plotted; confidence-2 counts are given separately above. The image
and raw per-frame tables are retained locally in the ignored evidence directory.

## Root-cause classification and decision

| Candidate cause | Evidence-based conclusion |
|---|---|
| Genuine sensor/depth evidence | Real local surfaces have repeated high-confidence support in both pose modes. Their interpretation as a full-height enclosure is unsupported; sensor evidence does not independently prove either room perimeter. |
| Frame coverage/sampling | Same 300 frame identities in the frozen comparison; stride-8 fusion exactly reproduces. Extensive other accepted pixels also support low surfaces. No frame/sampling change explains this shift. |
| Extraction/fusion loss | Original PNG extraction and weighted fusion are exact. No extraction/fusion defect is demonstrated. |
| Boundary extraction/support logic | **Identified mechanism:** a residual horizontal plane activates a junction with an existing finite inner segment and changes polygon topology. Whole-source plane support is stronger/taller than local notch support. |
| Coordinate/calibration error | Same frozen floor basis/datum and exact supplied per-frame intrinsics/raw poses. No convention or extraction mismatch explains the shift. Hardware calibration, pose uncertainty and sensor accuracy remain unverified. |
| Other issue | Distinguishing a low partition, object, opening/transmissive surface or true structural perimeter requires additional semantic/physical evidence. No one interpretation is established by depth alone. |

Crossing rays challenge the interpretation of these edges as **continuous opaque
full-height walls**. They do not establish that a low partition or opening cannot
be part of a legitimate room boundary. Therefore neither deleting the notch nor
adding/connecting another wall is justified by these observations alone.

Classification: **known boundary-support/model-selection mechanism with
evidence-limited physical/semantic interpretation**. No proven deterministic
software defect, and no demonstrated safer geometry correction. Production
remains unchanged. The 0.702677 m displacement warning remains unresolved;
neither coverage nor reprojection/surface RMS converts it into accuracy evidence.

Prior research is reused: A's height-band/histogram candidates and B's projection
modes are candidate-generation ideas already represented in the pipeline. Fixed
ceiling-height/rectangle fallbacks would manufacture dimensions. Open3D TSDF,
PolyLayout and RoomFormer are previously documented alternatives; none resolves
this local semantic/survey ambiguity without additional evidence. They are not
executed or adopted in this batch. No third-party implementation/model is added.

## Validation and reproduction

New isolated files: [audit_ceiling_boundary_shift.py](../../scripts/audit_ceiling_boundary_shift.py)
and [test_ceiling_boundary_shift.py](../../tests/test_ceiling_boundary_shift.py).
They do not enter production reconstruction. Seventeen new diagnostic test cases
cover changed-edge scope, finite support, true fitted-plane tilt, crossing
clearance/height limits, and exact/ambiguous source-plane association.

**Targeted validation: 60 passed in 27.52 s. Full regression: 360 passed in
50.13 s, zero failures. Current geometry replay: 15/15 exact checks.** The
authoritative per-frame audit completes in 28.882 s with exit 0. This is local
diagnostic runtime, not a clean-machine/end-to-end assessment timing claim.

An earlier preliminary audit included a nearly coincident shared-edge numerical
sliver as an extra changed edge. Its logs/output are retained but superseded for
edge scope. The diagnostic now excludes shared edges within a 1e-8 m numerical
association band and reports exactly four changed portions; a dedicated test
guards this case. This correction changes no sensor threshold, reconstructed
boundary, original artifact or production logic. It is not a production fix.

```powershell
.\.venv\Scripts\python.exe scripts/audit_ceiling_boundary_shift.py --out demo/ceiling_notch_audit_fresh
.\.venv\Scripts\python.exe scripts/verify_layout_artifact.py demo/phase3_strip_trace/current_exterior/ceiling --out demo/ceiling_baseline_fresh
.\.venv\Scripts\python.exe -m pytest -q tests/test_ceiling_boundary_shift.py tests/test_ceiling.py tests/test_layout_artifact.py tests/test_wall_completion.py tests/test_wall_planes.py tests/test_adjoining_span_trace.py tests/test_boundary_comparison.py
.\.venv\Scripts\python.exe -m pytest -q
```

Use fresh output directories. Commands require the retained historical/current
artifacts and local intake paths; this is not yet a portable clean-clone acceptance
bundle. Keep raw stdout/stderr and exit codes. Evidence is indexed in the
[compact summary](../results/phase3_ceiling_boundary_summary.json); complete
frame-level sensor counts and hashes are in
`demo/phase3_ceiling_shift/audit_final/audit.json`, current geometry replay in
`ceiling_baseline/verification.json`, with test logs beside them.

The existing uncommitted work and all previously pinned evidence are preserved.
Only the isolated diagnostic/test and documentation are added/updated. No
production code, solver, accepted geometry or guard changes. No meaningful
production milestone is established, so there is **no commit or push**.

## Requirement impact and evidence still needed

REQ-04 gains verified supplied LiDAR extraction/backprojection/fusion evidence.
REQ-07/08/10 remain **partial**: supported boundary interpretation, complete
room/property geometry and measured ceilings are not demonstrated. REQ-25's
ceiling accuracy/repeatability gate is not tested by a footprint displacement.
REQ-42 gains retained reproduction/evidence, not final portable delivery.
No complete assessment requirement is closed by this sensor-conditional audit.

To validate the notch, retain a corresponding plan/photo annotation identifying
the physical room perimeter and local surfaces, an independent laser/tape survey
of both candidate edge locations and opening/partition heights, and the mapping
to this capture's local coordinate frame. Record original readings, survey
uncertainty, capture/device identity and an independent repeat. Score identified
physical wall/opening dimensions against held-out truth; do not fit the output
to that truth before scoring. This is required evidence, not a request to
manufacture a missing expected polygon.

Floor completeness remains 25/176 covered samples. Surveyed three-tier property
benchmark/repeats, opening/damage truth, calibration/uncertainty, measured drift
and Fix Loop, consumer comparison, official external schema/gates and cold/walk-in
evidence remain open. The registration diagnostic chain stays CLOSED.

**Single next technical step:** trace `_observed_ceiling` rejection reasons for
the affected current `room_2` using its existing cloud, planes and sensor-camera
positions, to distinguish missing ceiling observations from plane-selection or
support loss. Keep geometry and thresholds fixed until that trace establishes
a software-addressable cause.
