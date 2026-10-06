# Ordered plan to reach the floor-plan assignment goal

Updated 2026-10-06 from the assignment brief, current code and the latest
[incremental E2E results](ASSIGNMENT_E2E_STATUS.md). This plan follows one technical
phase at a time: agree the phase's evidence and acceptance checks, make its declared
change, run that phase's tests and end-to-end capture, inspect the measurements,
and close the phase before starting the next one.

The current code is a research prototype. Forty-four automated tests pass, but that
does not establish physical accuracy. The supplied company's LiDAR dataset has no
surveyed room/wall/opening/height truth. Current RGB-only 2/4/8-image trials fail to
make a sparse model, and the one room recovered from supplied LiDAR is partial.
Treat each item below as pending until its completion evidence is recorded here.

| Phase | Current state | Close condition |
| --- | --- | --- |
| 0. Acceptance data and definitions | **Prepared; pending external inputs.** Inventory and manifest/truth templates are checked in; current scans have no surveyed truth and the published schema/full Round 1 gates are absent. | Fill manifest with one surveyed 3+ room property shared across tiers; add truth, repeat, damage and consumer export; version external schema/gates. |
| 1. Sparse photos | **Failing baseline.** Supplied 2/4/8 RGB-only trials and an 8-image full-resolution trial yield no sparse model. | Held-out 2/4/8 photo capture yields metric room geometry or an honest capture-quality failure; pass photo wall/footprint gates. |
| 2. LiDAR geometry and ceilings | **Partial.** One supplied room, 36.6% coverage; two other raw scans have no closed plan; synthetic rooms lack ceilings. | Surveyed held-out rooms, full supported boundaries, correct topology, 1.5 cm ceiling error and 1 cm repeat spread. |
| 3. Video | **Partial.** Synthetic cached path works; public clip weakly registers; native phone video untested. | Held-out native phone video passes the 3% wall gate, ceiling and repeat checks. |
| 4. Property stitch | **Failing evidence.** Current controlled geometry has two rooms; no shared surveyed 3+ room property across tiers. | Same 3+ rooms and connector pass topology, overlap and 8% footprint gate in every tier. |
| 5. Damage and scope | **Experimental.** Heuristic candidates have observed false positives; photo/video surfaces are unevaluated. | Held-out segmented damage and scoped quantities meet declared detection/extent gates. |
| 6. Uncertainty | **Not calibrated.** Envelopes are labelled uncalibrated; calibration is not applied. | Held-out interval coverage reaches the agreed nominal level for every measurement group. |
| 7. Published contract and evaluator | **Partial.** Internal schema/evaluator only; external schema and one gate definition are missing. | External schema passes; every required gate emits evidence-backed pass/fail/pending. |
| 8. Full benchmark and declared fix | **Not run.** No repeat survey, consumer comparison or frozen physical worst-gate fix. | Same-property all-tier gates, ≥70% consumer beat/tie, independent repeat and predicted fix verified. |
| 9. Rehearsal and report | **Not demonstrated.** Current workstation runs only; no unseen-room operator or timed clean setup. | Clean machine under 15 minutes, unseen-room rehearsal and final report at six pages or fewer. |

## Completion rule for every phase

Before changing code, write a one-page fix declaration in `docs/fixes/` with the
observed failing metric, input hashes, baseline code and configuration, a specific
hypothesis, the predicted result, and a falsification condition. Keep evaluation
properties out of development data. Run the smallest relevant tests, then a fresh
end-to-end run on unchanged raw inputs. Report the prediction and measured outcome
whether the change succeeds or fails. Do not move to the next phase until the
current gate passes on its stated held-out evidence or is explicitly recorded as
blocked by a missing external input.

## Phase 0 — Freeze acceptance definitions and acquire truth

**Why first:** centimetre accuracy cannot be measured from the supplied scans alone.
The assignment HTML also refers to a published output schema and earlier Round 1
gates that are not included in the local copy.

**Work:**

- Obtain and version the published JSON schema and the missing Round 1 definitions.
- Build a stable benchmark manifest with property, room, wall, opening, surface,
  damage-region and capture IDs.
- Capture one furnished property with at least three rooms and a connector, plus a
  room with two staged damage classes. Capture the same spaces in photo, video and
  LiDAR tiers, and repeat one tier as an independently restarted capture.
- Record tape/laser wall lengths, every ceiling height, opening widths and heights,
  room footprint/adjacency, and damage-region dimensions. Retain raw readings and
  evidence images. Keep the survey separate from inference inputs.
- Select the consumer app and record version, device, actual export and measurement
  process. Do not compare against screenshots or a different room.
- Freeze provisional metrics only where the official brief is silent; label each
  assumption and keep it replaceable when the missing definitions arrive.

**Done when:** the dataset inventory has raw capture hashes and independent truth
for every scored item; development and held-out properties are disjoint; all tier
captures describe the same spaces; the schema and gate version are checked into
the repository. If the schema or earlier gates cannot be obtained, record that
specific external blocker and continue only with visibly provisional internal
contracts.

## Phase 1 — Make the 2–8 photo tier produce metric room geometry

**Current evidence:** intake accepts room folders, but the tested supplied RGB-only
subsets at 2, 4 and 8 images—including eight full-resolution frames—produce no
sparse model. The learned monocular-depth experiment disagreed with the supplied
LiDAR by 0.13–0.77 m mean absolute error per sampled frame. The controlled photo
pass uses 97 frames and measured scale references, so it does not cover this tier.

**Work:** use only the allowed photo inputs and the capture calibration/scale
information the assignment explicitly permits. Improve overlap-aware image
selection and camera matching/pose recovery; compare appropriate few-view geometry
methods before choosing one. Keep depth and sensor poses out of this tier. Resolve
metric scale under the actual assignment capture protocol and disclose every scale
prior. Produce a room-level point cloud/plan with traceable supporting views.

**Done when:** on held-out, surveyed rooms with 2, 4 and 8 photos, reconstruction
succeeds where the capture has adequate visible overlap, and reports an auditable
failure where it does not. The stated photo wall-length error is within ±8%; room
footprint error is within ±8%; wall/opening IDs and dimensions are measured against
survey; uncertainty is evaluated on held-out properties. The protocol, frame count,
runtime and all exclusions are recorded. If success depends on a scale marker or
manual input, verify that requirement against the published capture rules first.

## Phase 2 — Make the LiDAR tier close supported rooms and measure heights

**Current evidence:** the supplied single-room scan yields one partial proposal
with 36.6% camera coverage and unknown height. The floor-only capture has
insufficient vertical-wall support. The ceiling scan has four parallel wall
segments but no closed room. Controlled LiDAR produces two rooms, but neither
ceiling is observed. These captures cannot establish geometric accuracy without
survey.

**Work:** use the Phase 0 representative LiDAR capture and truth. Check stream
registration, units, intrinsics, sensor-pose axes, frame timing and confidence.
Improve robust floor/wall/ceiling evidence and room boundary support. Preserve
partial status for occlusion or unvisited areas. Measure repeat drift and test
pose correction on/off against surveyed truth; pose changes alone are not evidence
of improvement.

**Done when:** all surveyed rooms and connectors are placed with correct adjacency,
no interior overlap and no unsupported boundary presented as observed. Every room
has a ceiling-height estimate within 1.5 cm of truth. Repeated height spread is at
most 1 cm. Wall and footprint errors pass the official LiDAR gates once provided;
until then publish errors without claiming a LiDAR gate pass. The independent
repeat and pose-correction ablation show the same capture and truth IDs.

## Phase 3 — Make the video tier reconstruct consistently

**Current evidence:** synthetic video reuses a 97-image SfM cache and preserves its
two-room geometry. A public TUM clip only registers 3 of 12 sampled frames. No native
iPhone 15+ MOV/HEVC walkthrough has been demonstrated. The app-level video path still
needs independent metric-scale and timing evidence.

**Work:** test a real device clip, orientation metadata, frame timestamps, blur,
rolling shutter, exposure changes and dropped frames. Improve keyframe selection,
sequential/global matching and calibrated scale. Add the chosen drift correction
only if the Phase 0 ablation shows benefit without degrading room geometry.

**Done when:** on held-out surveyed video captures, wall-length error is within
±3%, room placement and adjacency pass, and each ceiling height meets 1.5 cm.
Repeated height spread is at most 1 cm. Video frame exclusions and cold runtime are
reported. A broken/low-overlap clip yields a useful partial report, not a fabricated
closed floor plan.

## Phase 4 — Stitch the same multiroom property across all tiers

**Current evidence:** current physical data has no common surveyed three-room
property at every tier. The controlled fixture has two rooms. The required
three-room-plus-connector behavior is unproven.

**Work:** build a property-level graph from independently reconstructed room
captures. Register shared doorway/connector evidence, preserve room identities,
resolve duplicate walls and reconcile global coordinates. Use identical truth
IDs for photos, video and LiDAR; do not align the output to survey for scoring.

**Done when:** the same three or more rooms and connector are reconstructed in all
tiers, every adjacency is correct, no room interiors overlap, property footprint
error meets ±8%, and each dimension remains traceable to its source captures.
Opening detection is scored separately so a missed door cannot be hidden by room
polygon overlap.

## Phase 5 — Detect and measure restoration evidence

**Current evidence:** RGB-D color/morphology rules emit inspection candidates, and
metric projection unions repeated views. Image review found candidates around
fixtures and shadows. These are not validated water/crack detectors. Photo/video
damage assessment is unevaluated when surface projection is unavailable.

**Work:** collect and annotate the staged damage classes, normal wall controls,
fixtures, shadows, trim, wet-look surfaces and concealed-risk examples. Select a
permitted model for segmentation and evaluate it on property-held-out images.
Project masks to metric surface coordinates, merge across frames, record evidence
and distinguish observations from rule-based concealed-risk flags. Build scope
items for the assignment's restoration actions and avoid double-counting openings
or overlapping regions.

**Done when:** damage class precision/recall and region overlap/area error meet
predeclared thresholds on held-out rooms; each damage region and scope item has a
surface ID, metric extent/quantity, source evidence and fired rule where applicable.
False positives, missed regions and concealed-risk false alarms are reported.
No concealed damage is stated as observed without direct evidence.

## Phase 6 — Calibrate every measurement interval

**Current evidence:** output currently carries explicitly uncalibrated geometric
envelopes. There is calibration code that groups residuals by independent property
and rejects a development/evaluation property collision, but it has no field
calibration data and is not applied to output measurements.

**Work:** after Phases 1–5 have stable errors, collect development residuals across
independent properties, tiers, measurement kinds and relevant capture conditions.
Fit property-level intervals, add them to every available dimension/area and
scope quantity, and keep unavailable measurements explicitly null. Freeze the
calibrator before held-out evaluation.

**Done when:** interval coverage meets the agreed nominal level on held-out
properties, interval widths are useful and reported by tier/measurement type, and
every output measurement either has a calibrated interval or an explicit reason it
cannot yet be calibrated. Do not call an engineering envelope a confidence interval.

## Phase 7 — Conform the deliverable and complete evaluator coverage

**Current evidence:** an internal JSON schema, HTML report, SVG/DXF/CSV and
provisional gate evaluator exist. The external schema is absent. The controlled
photo/video geometry passes provisional wall/opening/property/topology gates but
fails ceiling and interval gates; LiDAR wall tolerance is unresolved.

**Work:** adapt the internal model to the published schema once received. Validate
references between rooms, surfaces, openings, damage regions, measurements, flags
and quantities. Implement one-to-one opening matching with false positives and
misses; independent ceiling, repeatability, footprint, topology and interval gates.
Keep each evaluator versioned and emit raw measurements plus aggregate scores.

**Done when:** schema validation passes for ready, partial and failed runs; every
stated assignment gate has a machine-readable pass/fail/pending result with its
threshold and evidence; negative tests prove omitted outputs do not pass by default.

## Phase 8 — Execute the full benchmark and one prospective fix

Run every tier on the Phase 0 property, independent repeat, damage room, challenge
conditions and same-room consumer capture. Summarize every shared dimension; the
consumer comparison must meet the stated 70% beat/tie target. Choose the worst
measured official gate, declare a predicted fix before editing, and compare frozen
before/after runs on the same input and evaluator. Publish the diff and prediction
post-mortem.

**Done when:** the single worst-gate fix improves its predeclared score without
regressing other gates; all repeats, missed/phantom openings, damage failures and
runtime costs are visible in one report. A same-file rerun does not count as an
independent repeat.

## Phase 9 — Package and rehearse the demonstration

Pin a fresh Windows CPU setup and all optional tools/weights; use relative paths and
checksums. Time install/download separately from processing. Ask an operator to
follow the capture page in an unseen space and produce a report without tailored
code changes. Prepare a rendered technical report of at most six pages covering
architecture, tier/device choices, drift, error budget, prospective fix and failures.

**Done when:** a clean supported machine completes setup and a fresh capture in
under 15 minutes; the operator completes the unseen-space flow on the day; the
portable bundle regenerates outputs; the final report fits the page limit and
matches the actual run evidence.

## Recommended next focus

Phase 0's inventory, manifest skeleton, truth templates and missing-definition list
are now prepared in [docs/benchmark/PHASE0_INVENTORY.md](benchmark/PHASE0_INVENTORY.md).
Phase 0 cannot close from the existing data: the remaining work is the physical
survey/capture package and externally missing schema/gates. Once those inputs are
available, close Phase 0 before working only on Phase 1 until its photo gate is
measured. Do not start Phase 2 or add another model during Phase 1 unless a recorded
experiment shows it directly addresses that phase's failure.

The missing schema, Round 1 rules, surveyed truth and consumer export are input
dependencies; they are not implementation defects. Record each one as an external
blocker with the precise phase it affects and continue work on phases that do not
depend on it.
