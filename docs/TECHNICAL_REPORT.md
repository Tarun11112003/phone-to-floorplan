# Phone to Floorplan — final technical report

Development freeze: 8 October 2026. [Five-page PDF](TECHNICAL_REPORT.pdf).
Source: `docs/Applied AI.html`; [evidence index](evidence/final_state.json).
Final status: **partial implementation; physical assessment acceptance not demonstrated**.

<!-- PAGE 1 -->
## 1. Objective and implemented architecture

The assignment asks for dimensioned, stitched property plans from phone photos,
video and LiDAR, with openings, damage, confidence and independently measured
accuracy. The intended users are property restoration teams. This submission is
a local Python command-line prototype using a stock-phone capture route.

The implemented sequence is capture intake and provenance, sensor-specific
reconstruction, supported structural geometry, optional verified stitching,
room/surface assessment, openings and damage, uncertainty/contract checks, and
review exports. Missing support produces unavailable measurements or partial
results. Reporting success and geometric acceptance are separate decisions.

<!-- FIGURE architecture -->

`workflow.run_capture` orchestrates intake, `reconstruct` and assessment writing.
`ingest` preserves frame identity and metadata; `sfm`/`rgbd` supply reconstruction;
`layout` handles finite walls and local floor/ceiling support. `stitching` is an
explicit operation, not an automatic guarantee. `assessment`, `openings`,
`damage` and `uncertainty` produce the internal contract. `assignment_gates`,
`repeatability` and consumer evaluators compare outputs with external references.

Outputs include JSON and offline HTML; supported geometry adds SVG, DXF, CSV,
cloud/trajectory and diagnostic artifacts. The published assignment schema was
not supplied, so internal schema validation is provisional.

Conservative acceptance preserves observed geometry and withholds unsupported
ceilings, scale and connections. CPU execution and explicit source/model hashes
favor inspection and reproducibility; limited observations and optional native
dependencies constrain completeness and startup time.

<!-- PAGE 2 -->
## 2. Input tiers, calibration and uncertainty

| Tier | Implemented path | Current boundary |
|---|---|---|
| Photos | Room folders, EXIF/HEIC handling, SIFT/COLMAP sparse cameras and tracks | Strict RGB scale/property placement unresolved; no measured all-room acceptance |
| Video | Original MOV/MP4, timestamped frame sampling, same production RGB path | Low-detail transition remains unresolved; investigation closed as inconclusive |
| LiDAR | Stray depth/confidence, per-frame intrinsics and odometry; calibrated backprojection/fusion | Real supplied data exercised; partial rooms and missing local floor/ceiling support |

SIFT remains production. Learned metric-depth inference and XFeat/LightGlue,
fixed-intrinsics and mapping ablations remain experimental. Sensor poses were
withheld from the RGB transition reconstruction and used only in post-hoc audits.
No experimental connectivity gain is promoted to a production accuracy claim.

The supplied three cases contain RGB video, depth/confidence and camera/IMU/
odometry CSVs. They exercise calibration extraction, synchronization, fusion,
support and failure behavior. They do not supply certified room dimensions,
physical damage labels, independent repeats or qualifying consumer exports.

Metric LiDAR scale is sensor-derived. Strict RGB cannot obtain absolute scale
from arbitrary photos alone; measured-reference research controls are separate.
Distortion/aspect-ratio checks and producer-bound calibration prevent silent
mixing of incompatible evidence. A camera matrix is a projection calibration,
not proof of physical measurement accuracy.

Depth-backed verified registration and pose-graph/loop mechanisms exist, but an
effective physical drift correction and qualifying footprint on/off benchmark
have not been demonstrated. Interval fitting/auditing is property-grouped and
producer-bound; adequate independent calibration properties are absent.

Local support, reprojection error, calibrated coverage and physical accuracy are
different quantities. Uncalibrated/unsupported measurements remain explicit.
Base iPhone hardware supports RGB; depth capture requires compatible Pro hardware.
The novice/cold-device Route 2 rehearsal and timed clean installation are pending.

<!-- PAGE 3 -->
## 3. Validation evidence and benchmark results

Evidence sources are immutable detailed records indexed by SHA-256 and JSON
field path. Controlled tests establish software invariants. Supplied-sensor
audits establish internal consistency; they do not replace laser/tape truth.

| Claim /metric | Recorded result | Status /scope |
|---|---|---|
| Software regression, batch032 | 390 tests pass; 43.22 s | PASS, current worktree only |
| Fixed ceiling-layout replay | 15/15 exact checks | PASS, same saved artifact |
| Native sensor fusion | 218,873 samples; 202,477 points, bit-identical arrays | PASS, internal consistency |
| Floor-only containment | 25/176 camera samples | PARTIAL, not floor-area accuracy |
| Ceiling-scan containment | 295/300 camera samples | PARTIAL, inferred geometry included |
| room_2 local floor | 148 points /43 cells; 14.1246% support | PARTIAL, below unchanged 25% guard |
| Independent dimensions/repeats | Required truth absent | NOT DEMONSTRATED |

<!-- FIGURE validation -->

The floor-source audit found 29.2154% diagnostic occupancy from accepted pixels
in the same 300 selected frames, versus 14.1246% after stride-8 sampling.
All-source raw-pose support reached 44.0880%. Fusion lost zero local occupied
cells. This identifies sampling/frame-selection loss, not a proven extraction
defect or a validated dense-floor fix. Production geometry/guards are unchanged.

The 0.702677 m discrepancy is a floor-plan footprint notch, not a ceiling-height
shift: area changed 10.477367 to 9.945720 m²; 0.531648 m² was removed. Height was
unavailable before and after. Crossing rays and exact fusion do not independently
identify the physical perimeter. Both interpretations remain unvalidated.

Recorded audit times exclude capture, transfer and installation. No qualifying
same-property three-tier physical benchmark, consumer score or cold walk-in
runtime is available. The compliance matrix preserves each unmet gate.

<!-- PAGE 4 -->
## 4. Fix loops, rejected approaches and engineering judgment

<!-- FIGURE fix_loop -->

| Completed engineering milestone | Evidence /result | Remaining limit |
|---|---|---|
| COLMAP/OpenCV pixel-center correction, 9d75ab6 | Remove analytical 0.5 px sampling offset; identity/resized-image regression | No measured wall-error improvement claimed |
| Finite wall/seed support, 061625b | Final bounded step: 67 to 69 fragments; prior cells preserved | Floor containment stays 25/176; completeness unresolved |
| Registered damage evidence, 8aaca9f | Reject unregistered/inconsistent surface observations; tested guards | No independently scored two-class field validation |

These are shipped software milestones. Their prospective physical worst-gate
prediction was not recorded. They cannot retrospectively satisfy the scored
Fix Loop, which requires a measured failing gate, advance prediction, shipped
fix and reproducible matched before/after evidence.

The matched 32-view DISK/LightGlue trial produced 167 verified pairs and one
graph component, but separate 15/11-view models with 1,931/1,404 points and
1.449190/1.337805 px residuals. No joint target-group model formed. Production
adoption was rejected. The retained SIFT control had 68 pairs and an 11-view
model with 1,012 points and 0.636201 px residual; this is also incomplete.

Experimental XFeat mapping-only fixed intrinsics registered 32 views and 6,187
points at 1.480503 px residual, but later relative orientation disagreed with
odometry by approximately 6.520814°. Final frame31 replay did not reproduce the
trusted snapshot; causality remained unresolved. The registration investigation
is closed. No production solver defect or physical tolerance was established.

Denser LiDAR sampling increased containment to 79/176 but moved accepted
geometry, so it was rejected. Floor/ceiling source audits justified retaining
the guard and unavailable height. Diagnostic restraint protects defensibility;
negative results are retained rather than marketed as fixes.

<!-- PAGE 5 -->
## 5. Reproduction and final assessment status

The source-and-evidence handoff includes the current worktree snapshot, curated
records, supplied raw data and integrity manifests. Documentation commits and
Git HEAD are distinct: pre-existing uncommitted implementation is preserved in
the source snapshot. External model weights/environments are excluded; usage
terms, pins and separate prerequisites are disclosed.

Setup uses `scripts/bootstrap_windows.ps1`; run the CLI help and `python -m
pytest -q` from the extracted source root. `run-capture` accepts a tier/source,
fresh output and assignment profile. A nonzero readiness result must remain
visible. Packaging and report commands are documented in PHASE3_OPERATIONS.md.
Historical absolute producer paths and omitted native assets limit portable
exact experiment regeneration. The bundle is PARTIAL against every-number
live reproduction, not a proven clean-machine installation.

| Assessment area | Final status | Missing evidence /impact |
|---|---|---|
| Full property geometry and strict RGB metric plan | PARTIAL | Supplied floor completeness, adjacency and RGB scale unresolved |
| Openings, ceiling heights, damage and concealed scope | PARTIAL | Guarded paths exist; missing local height and independent field scoring |
| Opening <=2 cm /85%; ceiling <=1.5 cm; repeats | NOT DEMONSTRATED | Detection-aware laser/tape truth and separate repeat captures |
| Photo +/-8%, video +/-3%; interval calibration | NOT DEMONSTRATED | Same-property tiers and independent calibration/audit properties |
| Consumer >=70% beat/tie; mandatory scored Fix Loop | NOT DEMONSTRATED | Original app exports; measured benchmark and prospective declaration |
| Boundary and registration causality | INCONCLUSIVE | Physical perimeter truth /reproducible causal solver evidence absent |
| Cold walk-in and setup time | NOT DEMONSTRATED | Unseen phone/tier rehearsal and timed fresh-machine live output |

Earlier Round 1 LiDAR tolerances and the official output schema were not
included; no substitute is invented. Real observations of at least three rooms
plus a connector, furnished/staged damage, same rooms at every tier, repeated
capture, laser/tape survey and consumer exports remain necessary for acceptance.

Final conclusion: the current implementation is packaged for honest engineering
evaluation, with traceable production fixes, experimental results and material
limitations. Software consistency is demonstrated on stated inputs. Independent
centimetre-level accuracy, full completeness and assessment acceptance are not.

Canonical detail: ARCHITECTURE.md, BENCHMARK_RESULTS.md, ASSIGNMENT_COMPLIANCE.md,
FIX_LOOP.md, LIMITATIONS.md, PHASE3_OPERATIONS.md and evidence/final_state.json.
