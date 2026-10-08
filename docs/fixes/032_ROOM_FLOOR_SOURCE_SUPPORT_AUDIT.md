# room_2: original floor returns versus sampling and fusion

This diagnostic addresses only the upstream local-floor
blocker in the supplied ceiling scan. It uses the unchanged room_2 polygon,
plane 1, 300 retained camera poses, intrinsics, cloud and acceptance guards.
The [component research](../ASSESSMENT_COMPONENT_RESEARCH.md),
[boundary audit](030_CEILING_BOUNDARY_SENSOR_AUDIT.md) and
[native decision trace](031_OBSERVED_CEILING_DECISION_TRACE.md) provide the prior
evidence. RGB registration remains CLOSED and XFeat remains experimental.

**Finding:** original accepted observations exist outside the retained stride-8
lattice. With the same 300 frames and refined poses, their diagnostic occupied
cell union covers **29.2154%**, versus **14.1246%** in the retained cloud.
All available original frames cover **44.0880% under raw sensor poses**.
Extraction/calibration checks pass and native fusion reproduces exactly, losing
**zero local support voxels and zero occupied cells**. The demonstrated
bottleneck is spatial sampling plus temporal frame selection, rather than a
complete absence of original observations or a fusion/occupancy implementation
defect.

**Decision:** retain production and the 25% guard. Sampling/selection is a
software-addressable information-loss limitation, but no reproducible extraction,
coordinate-transform, fusion or native guard bug is established. Dense sensor
pixel unions are not a native accepted fused floor or independent dimensional
truth. No production fix, geometry edit, commit or push is made.

## Fixed baseline and policy

Retained run: `demo/phase3_strip_trace/current_exterior/ceiling`.
Original source: `datasets/Given_dataset/single_scan_with_ceiling/c7d28f72c6`.

- room_2 footprint: **9.945719534889562 m²**, ten unchanged corners.
- Plane 1: original normal `(-0.037523429, 0.999071808, 0.021154530)`,
  offset **1.4415419023641063 m**, RMS **0.012258440934206426 m**.
- Native orientation, RMS, below-camera and reference-level guards pass.
  Its reference-level difference is **0.038206344 m**, within the existing 0.04 m guard.
- Plane membership uses the native **strict 35 mm band**, then the same
  **5 cm buffered polygon**. Coverage uses occupied **20 cm cells clipped
  to the original polygon**, with the unchanged 100-point minimum/25% guard.
- Source confidence acceptance remains **>=1**, depth range **[0.2, 8] m**,
  depth scale **1,000 units/m**, pixel lattice **(u mod 8 = 0, v mod 8 = 0)**
  and weighted global voxel size **2 cm**.
- No plane fitting, wall extraction, new junction, pose optimization, frame
  insertion or alternative ceiling inference is performed by this audit.

These are existing observation policies, not independently calibrated accuracy
tolerances or the assessment's physical ceiling/opening error gates.

## Original available data and identity checks

The original source contains **6,899 depth PNGs**, **9,745 confidence PNGs**
and **9,745 odometry rows**. All 6,899 depth identities have matching confidence
and odometry. The **2,846 confidence identities without a depth PNG already lack
depth in the original source**; they are not extraction losses and cannot supply
invented floor returns.

All audited depth/confidence images are **256×192**; RGB dimensions are
**1920×1440**. Per-frame odometry intrinsics are scaled to depth resolution.
Optical quaternion rotations are normalized and used directly, with no extra
axis flip or last-frame camera-matrix substitution. Sensor identities and
timestamps are contiguous/strictly ordered as applicable, with exact retained
frame timestamp matches.

The selected 300 original depth/confidence pairs are **byte-identical to their
600 extracted copies**. Their per-frame intrinsic values and original raw poses
match the normalized manifest exactly. All selected identities appear in the
retained trajectory in the same order. **Zero selected frames were skipped**
during the saved reconstruction. All 6,899 paired source frames also pass the
existing global confident-depth count checks; their omission is not explained
by those minimum-count guards. This does not verify their untested registration
or justify adding their raw poses to production.

The selected frames contain **14,730,808 in-range pixels**, **14,106,424
confidence-accepted pixels**, and **218,873 accepted stride-8 pixels globally**.
The local measurements below additionally require the fixed plane band and
buffered room, rather than counting arbitrary accepted points as floor evidence.

## Local evidence before and after sampling/fusion

All rows in this first table use the same retained 300 frames and **fixed refined
poses**. Returns may repeat across views; cell unions count each cell once.

| Evidence stage | Local returns/points | Supporting frames | Occupied cells | Clipped area | Coverage |
|---|---:|---:|---:|---:|---:|
| Original in-range pixels, including confidence 0 | 9,897 | 25 | 94 | 2.985680142 m² | 30.0198% |
| Original accepted pixels, confidence >=1 | 9,818 | 25 | 92 | 2.905680142 m² | 29.2154% |
| Confidence 2 subset, diagnostic only | 9,264 | 23 | 65 | 2.051379457 m² | 20.6258% |
| Accepted pixels outside the stride-8 lattice | 9,668 | 25 | 92 | 2.905680142 m² | 29.2154% |
| Native stride-8 samples before fusion | 150 | 22 | 43 | 1.404795563 m² | 14.1246% |
| Native stride-8 cloud after global fusion | 148 | Not an independent frame count | 43 | 1.404795563 m² | 14.1246% |

Confidence filtering removes **79 local returns and two otherwise occupied
cells**: **0.080000000 m² /0.8044 percentage points**. It does not account for
the large retained-coverage deficit. Stride-8 omits **9,668 accepted returns
(98.4722%)** and **49 occupied cells**, reducing clipped area by
**1.500884579 m² /15.0908 percentage points**. The off-lattice accepted pixels
alone contain the entire dense accepted cell union. The sensor footprint is
only partly observed even in this diagnostic; 29.2154% is not complete coverage.

Only **20.6258%** has confidence-2 support in the selected frames. The additional
cells that bring the accepted dense union above 25% include confidence-1
observations. The native policy permits those observations, but this is a reason
to audit fused support and repeated-view stability before adopting a density
change; it is not a reason to relax confidence or coverage guards.

### Per-frame trace

The exact selected refined-pose floor-support identities are:
`1115, 1501, 1545, 1569, 1595, 1618, 1661, 1704, 1748, 1772, 1797,
1988, 2054, 2080, 2103, 2128, 2155, 2208, 2243, 2266, 2291, 2319,
2342, 2385, 6485`.

| Original frame | Accepted local pixels | Confidence-2 pixels | Retained stride-8 local pixels |
|---|---:|---:|---:|
| 1545 | 923 | 775 | 9 |
| 1569 | 798 | 789 | 11 |
| 2080 | 965 | 960 | 17 |
| 1115 | 1 | 1 | 0 |
| 2266 | 1 | 0 | 0 |
| 6485 | 14 | 0 | 0 |

The three completely lost support views are weak local observations. Most
omitted pixels, however, occur in views that already have substantial accepted
and confidence-2 support; this is not just adding isolated noise frames.
`source_audit_final/audit.json` records counts, frame identities, original sensor
times, depth-count eligibility and residual histograms for all **6,899 frames**.
It also retains off-lattice pixel/depth/confidence/coordinate witnesses from
the selected supporting frames. `analysis.json` indexes their selected trace.

## Isolating frame-selection loss

The next table uses **original raw sensor poses in every row**, keeping the
fixed room polygon and plane. Unselected refined poses do not exist: no pose
interpolation, optimization or substitution is attempted.

| Original frames /accepted pixels | Local returns | Supporting frames | Cells | Clipped area | Coverage |
|---|---:|---:|---:|---:|---:|
| Selected 300, full accepted pixels | 9,909 | 25 | 92 | 2.905680142 m² | 29.2154% |
| Omitted 6,599, full accepted pixels | 229,885 | 525 | 133 | 4.352125108 m² | 43.7588% |
| All 6,899, full accepted pixels | 239,794 | 550 | 135 | 4.384869869 m² | 44.0880% |
| All 6,899, confidence-2 pixels only | 226,958 | 546 | 111 | 3.472125108 m² | 34.9107% |
| All 6,899, accepted stride-8 pixels | 3,562 | 514 | 99 | 3.095474958 m² | 31.1237% |

The selected subset omits **43 cells /1.479189726 m² /14.8726 percentage points**
from the all-frame accepted union under the same raw poses. Most source
floor-supporting views are outside it: 525 omitted versus 25 selected.
Cell unions overlap; the selected/omitted coverages must not be added.
These are repeated observations of one capture, not independent repeats.

The selected dense raw/refined unions have **exactly the same 92 cells and
clipped coverage**, despite 9,909 versus 9,818 return counts. Their stride-8
coverages are 14.2956% raw versus 14.1246% refined. That measured comparison
does not implicate pose refinement as the main coverage-loss mechanism.
It does not prove sensor poses or calibration are physically accurate.

![Fixed-geometry floor support through selection, sampling and fusion](../../demo/phase3_floor_support/floor_return_coverage.png)

## Fusion and occupancy parity

Original selected stride-8 projection, source confidences and native weights
produce **218,873 input points**. Calling the unchanged global
`layout.weighted_voxels` reproduces the saved **202,477 cloud points AND
their weight array bit-for-bit**. No resampling or local-only fusion replaces
the saved cloud.

The 150 local sampled returns occupy **148 native world-frame voxel IDs**.
All 148 remain inside the same plane/room support after weighted fusion:
**zero support voxels lost, zero gained; zero occupied cells lost or gained**.
The independent diagnostic cell calculation and unmodified native
`_horizontal_support` agree exactly on **148 /0.14124624752511566**.
Fusion is not responsible for losing the demonstrated off-lattice cells: those
pixels never enter it. A different TSDF backend is therefore not justified by
this failure. Dense global fusion has **not** been run or validated here.

## Classification, guards and preservation decision

| Candidate cause | Finding |
|---|---|
| Missing original observations | Not the main explanation for retained plane-1 coverage: available accepted source returns cover 29.2154% selected /44.0880% all raw. Physical floor identity/completeness remains unknown. |
| Depth/confidence extraction loss | Not reproduced: all selected sensor copies and source calibration/pose/timing values match. Confidence filtering is intentional and accounts for only 0.8044 points of selected coverage. |
| Sampling/frame selection | **Demonstrated software-addressable limitation.** Stride-8 loses 15.0908 points of selected coverage; frame selection loses another 14.8726 points in a separately controlled raw-pose comparison. |
| Fusion/occupancy logic | Not reproduced: exact point/weight replay, identical native occupancy, zero local support voxel/cell loss. |
| Coordinate/calibration issue | No extraction/frame-transform defect found; selected raw/refined dense occupancy is identical. Independent physical calibration accuracy and plane-model bias are not established. |
| Another concrete production defect | None demonstrated by this audit. Density/resource tradeoffs are not silently reclassified as a corrupt-data or guard bug. |

The **25% guard correctly rejects the retained cloud's 14.1246%**. Source data
shows the rejection is sensitive to the evidence retained by the sampling
policy; it does not prove the numerical guard is empirically optimal or should
be lowered. Keep it unchanged. A raw dense union above 25% is neither a native
fused acceptance result nor proof of a safe floor-to-ceiling measurement.

Prior research considered A's height-mode proposals, B's projection proposals
and Open3D/structural alternatives. A candidate floor plane already exists,
and this audit localizes lost observations before fusion. Preserve the current
calibration, geometry and observation policy; investigate a bounded support
control before adding any model/backend. No new external investigation or
alternative implementation is executed, and no direct reuse is made.

Production before/after remains **148 points /43 cells /14.1246%**, local floor
unaccepted and ceiling height/evidence unavailable. The historic footprint
change remains **0.702677028 m**, area **10.477367266 ->9.945719535 m²**,
removed area **0.531647731 m²**. This audit neither validates that perimeter
change nor establishes a measured ceiling. Floor-only coverage remains 25/176.

## Tests, evidence and reproduction

New read-only [auditor](../../scripts/audit_room_floor_returns.py) and
[tests](../../tests/test_room_floor_returns.py) enter no production module.
Sixteen cases cover validity/confidence separation, strict band/buffer semantics,
clipped concave cells, repeated-return versus union accounting, native point
minimum parity, exact fusion lineage, calibration and JSON-safe evidence.

- Final diagnostic unit tests: **16 passed in 1.41 s**.
- Focused floor/ceiling/intake/geometry suite: **82 passed in 5.37 s**.
- Full regression: **390 passed in 43.22 s**, zero final failures.
- Fresh full ceiling geometry replay: **15/15 exact checks**, 34.978 s.
- Original sensor/current-cloud audit: successful, **423.987 s** internal runtime.

The first diagnostic attempt was deliberately stopped after detecting that cell
keys contained NumPy integer scalars, before any completed report was produced.
A new serialization test reproduced **one failure**, then conversion to plain
JSON integers fixed it. The corrected 16 tests and completed audit pass. The
interrupted source snapshot and exit/log record are retained as superseded
diagnostic evidence; none of its partial results supports the conclusion.
This is a new diagnostic-output correction, not a production reconstruction fix.

```powershell
.\.venv\Scripts\python.exe scripts/audit_room_floor_returns.py --out demo/room2_floor_source_audit_fresh
.\.venv\Scripts\python.exe scripts/verify_layout_artifact.py demo/phase3_strip_trace/current_exterior/ceiling --out demo/room2_floor_geometry_fresh
.\.venv\Scripts\python.exe -m pytest -q tests/test_room_floor_returns.py tests/test_observed_ceiling_trace.py tests/test_ceiling.py tests/test_layout_artifact.py tests/test_ceiling_boundary_shift.py tests/test_rgbd.py tests/test_lidar_sampling.py
.\.venv\Scripts\python.exe -m pytest -q
```

Use fresh output directories. Records retain original PNG hashes, input/producer
hashes, stdout/stderr, runtimes and exit codes. Full local evidence is under
`demo/phase3_floor_support/`; [compact summary](../results/phase3_room_floor_support_summary.json)
indexes it. The preserved baseline and prior evidence are rechecked. These
commands require the retained local run/intake paths; clean-clone acceptance
and capture-linked physical measurements remain separate dependencies.

## Assessment impact and single next step

REQ-07/08/25 remain **partial**: local floor/ceiling outputs are still unavailable,
and no physical dimension or repeat gate is closed. REQ-42 gains reproducible
source-to-cloud evidence. Available observations are no longer conflated with
missing retained support. Measured perimeter/floor/ceiling truth, synchronized
surface annotations, independent repeats/calibration properties, three-tier
physical benchmark, consumer exports, scored Fix Loop and cold/walk-in evidence
remain outstanding. No complete geometry, centimetre accuracy or assessment
acceptance is claimed.

**Single next technical step:** run an isolated full-pixel **2 cm native-fusion
floor-support control on the same retained 300 frames**, keeping poses, intrinsics,
plane list, room polygon and native floor guards fixed; do not refit walls or
layout. Compare the resulting native plane-1 support with the retained
148/43/14.1246% baseline and inspect confidence/repeated-view support for added
cells before deciding whether a bounded floor-evidence change is justified.
The current raw dense-pixel union alone is insufficient for adoption.
