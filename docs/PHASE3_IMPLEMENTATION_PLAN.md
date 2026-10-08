# Phase 3 implementation plan — validated against the assessment

**Historical engineering record. Development is closed. Current requirements/status and evaluator commands are in [compliance](ASSIGNMENT_COMPLIANCE.md) and [README](../README.md).

This is the agreed Phase 3 plan retained for reference. It describes intended work, not completed implementation. Actual progress and test evidence belong in `PHASE3_IMPLEMENTATION_STATUS.md`.

## 1. Basis, corrections, and completion criteria

The plan is grounded in the working tree, [Applied AI.html](Applied%20AI.html), and researched alternative implementations. The available HTML is the assessment source; the unavailable PDF, published schema, and earlier Round 1 rubric are not treated as reviewed material.

Phase 2 made no file changes, patches, test runs, or commits. Preserve pre-existing uncommitted changes during implementation.

Reference revisions reviewed:

- comparative source: `d5105858440bdb549626845948bc51da8a8b9f02` at https://github.com/Vatsalya001/cozmo-ai-assignment.
- comparative source: `c9dfacbed60ddb6554a7c9b6721696dfb748013a` at https://github.com/kush07upadhyay/Cozmo_AI_Assignment.

### Corrections to the earlier analysis

| Earlier interpretation | Validated conclusion | Planning consequence |
|---|---|---|
| Scope requires automatic demolition/remediation | The supplied assessment requires scope keyed to surfaces; inspection items satisfy that behavior when correctly generated | Preserve inspection scope; prescriptions are optional |
| Video must exclude supplied poses | Only photos explicitly forbid poses/depth | Preserve posed video; stock-camera route must work on base iPhones |
| Ceiling estimation is entirely missing | `layout._observed_ceiling` exists | Improve support and accuracy rather than duplicate it |
| Drift correction is missing | `mapping.optimize_poses` exists | Preserve verified registration and strengthen integration/evidence |
| Automatic stitching has no implementation | `stitching.stitch_runs` handles independent RGB-D runs; assisted stitching exists | Extend automatic stitching across tiers; assisted tests are not strict-photo proof |
| Supplied scans contain no repeats | Nearby timestamps and A's same-flat report suggest candidate repeat walks, but local identity metadata is absent | Mark UNCLEAR, verify, and collect a documented independent repeat |
| Global rigid evaluation alignment leaks truth | One rigid transform resolves origin/heading without changing scale | Retain it; forbid rescaling and independent per-room alignment |
| Better matching solves the failing photo case | Recorded LightGlue trial increased matches but still failed registration | Retain SIFT; matching alone is insufficient |
| Learned metric depth solves centimetre scale | Recorded MoGe/Depth Anything errors are substantial | Only a bounded separately labelled feasibility experiment may be promoted after acceptance |
| Many walls imply many calibration samples | Existing calibration correctly groups by independent property | Preserve grouping; nine properties per group minimum for finite 90% quantile |
| Adverse-condition coverage requires dedicated detectors | Conditions must be covered in the submission | Capture/evaluate/document them; dedicated detectors optional |
| References prove compliance | Both have useful ideas and material gaps | Adopt selected principles, not architectures/claims wholesale |

### Target state

Retain the Python CLI and Route 2 stock-capture architecture. Deliver a live path for all three mandatory tiers; one shared measurement/surface contract; a whole-property plan with adjacency, dimensions, ceilings and physical openings; surface damage, fired concealed-damage rules and inspection scope; calibrated intervals; reproducible benchmark/fix/consumer evidence; clean-machine and unseen rehearsals; concise submission documents.

**Completion requires evidence, not just functions.** Strict RGB reconstruction remains high risk. The missing official schema and Round 1 rules remain external acceptance holds.

### Fixed decisions

- Route 2; no custom iOS app or web application.
- Windows CPU; no mandatory GPU or private hosted service.
- Native Camera photos/video; Stray Scanner LiDAR on compatible Pro hardware.
- Consumer comparison: magicplan; record actual installed version and original export.
- Treat the user's iPhone 16 as base unless confirmed otherwise; borrow a Pro device for same-property LiDAR.
- Assignment confidence 90%, grouped by property. Preserve existing 95% calibration defaults for compatibility.
- Laser measurements are evaluation inputs, not hidden inference scale.
- Version provisional rules and visibly retain unavailable official acceptance items.

Stray requires LiDAR hardware: https://apps.apple.com/us/app/stray-scanner/id1557051662. magicplan Auto-Scan requirements: https://help.magicplan.app/auto-scan-your-floor-plan.

## 2. Exact changes

Effort is engineering size; excludes property access, surveying and downloads.

### CHANGE-01 — Unify the assessment contract and evaluator

**P0; REQ-05, 07–16, 24–29, 33, 42.** Files/functions: `assessment.build_assessment`, `contracts.validate_assessment`, `assignment_gates.evaluate_assignment`, assessment schema.

Current: entity-linked assessment measurements and legacy evaluator structures differ; opening extraction is inconsistent; explicit footprint/graph are missing. Problem: wrong scoring, duplicated physical openings and omitted measurements.

Approach: canonical `internal-assessment-v2`, physical openings linked to adjacent surfaces, property footprint/adjacency/provenance/status, v1/legacy adapters, SVG/DXF/CSV from the same geometry, versioned acceptance registry. Keep internal validation separate from official schema verification. Gate states: pass, fail, not_evaluated, external_spec_missing. Unknown observations are unavailable, never zero or pass.

Reason: fix producer/consumer mismatch without a new architecture. References provide no replacement contract worth adopting. Dependencies: foundation. Risk: Medium, migration/IDs. Tests: legacy/v1/v2 equivalence; one shared doorway; missing height/interval/truth; unresolved official acceptance.

### CHANGE-02 — Correct command status, failure handling and portable tests

**P0; REQ-17, 34–35, 42.** `cli.main`, `workflow.reconstruct`, contracts, assignment tests.

Current: run-capture may return success after assessment generation fails; preflight errors lack structured ledger; a regression test reads ignored data. Approach: failing status for assessment failure, structured safe-output intake failures, preserve geometry `floor_plan_ready`, add `contract_complete`, retain false accuracy status without measured evidence, validate scope source/rule references, track small test snapshots, report monitoring dependency failures.

Reason: concrete reliability and fresh-checkout defects; no reference replacement needed. Dependencies: 01. Risk: Low–Medium; incomplete runs now fail correctly. Tests: forced report failure, malformed intake, missing dependency, references, fresh-directory protection, no ignored test inputs.

### CHANGE-03 — Reproducible Windows setup, assets, caches and runtime bounds

**P0; REQ-34–35, 38–39, 41–42.** pyproject, workflow, OpenMVS, MoGe probe; new bootstrap/reproduction scripts.

Current: selected cache fields checked; optional imports in required paths; long stage timeouts. Approach: tested CPU PowerShell bootstrap; pin code/models/binaries; verify hashes before loading; fingerprint preprocessing, producer code, dependencies, seed, config, weights and outputs; reject incompatible caches; fetch large assets or supply volume; bound/cancel subprocesses. Ten-minute processing is an internal target, not the rubric; measure complete clean-machine fresh-result time under fifteen minutes. Inventory each artifact as regenerated, skipped with reason, or historical.

Adopt A's `bench/clean_clone_check.sh` artifact accounting, not local-data symlink proof. Dependencies: 01–02. Risk: Medium. Tests: clean setup, offline volume, corrupt weights, producer changes, timeout/cancellation, cold live run, deterministic cache replay.

### CHANGE-04 — Physical benchmark and independent truth

**P0; REQ-19–23, 25–26, 30, 38, 40–41.** Capture protocol, benchmark manifest/inventory, survey records.

Current: integration/public/controlled data do not constitute full surveyed same-property evidence. Collect at least three rooms PLUS a separate connector; furnished staged two-class damage; same spaces all tiers; at least one documented independent same-tier room repeat. Record property/room/capture/device/app/conditions. Survey every scored wall, opening, ceiling and damage extent. Keep original readings and a third reading when two exceed predeclared tolerance. Truth stays outside inference. Verify supplied repeat candidates. Include mirror/glass/wet-look/low-light cases.

Validation design: two development properties, at least nine independent calibration properties per tier/measurement group, three untouched audit properties. This count is our calibration design, not an assessment requirement. Inadequate groups remain uncalibrated. Public data only supplements adequate truth/provenance; synthetic rooms and trajectory truth do not replace required physical benchmark.

Dependencies: 01 plus initial 03/05 preflight; collect alongside software. Risk: High, access/hardware/samples. Tests: composition, survey consistency, identities, tier correspondence, repeat independence, truth separation.

### CHANGE-05 — Capture identity and current export calibration

**P0; REQ-01–04, 06, 17, 39, 42.** `ingest.prepare_photos/prepare_video/prepare_stray_scanner`, workflow manifest validation.

Current: normalized photos lose camera metadata; video lacks complete source-time mapping; distortion exports rejected. Preserve original metadata/dimensions/orientation/room/hash; video presentation timestamps/keyframe mapping; versioned capture adapter preserving v2. Assignment profile rejects photo depth, poses, measured scale and manual adjacency; research/assisted remain. Add current Stray golden fixtures and domain-correct calibrated distortion handling. Do not apply a depth-camera LUT indiscriminately to RGB or already rectified depth; reject unsupported combinations explicitly.

Stray optional LUTs/per-frame calibration: https://github.com/strayrobots/scanner/blob/main/docs/format.md. Exporter uses capturedDepthData while scene depth is separate: https://github.com/strayrobots/scanner/blob/main/StrayScanner/Helpers/DistortionEncoder.swift.

Retain existing validation rather than A's proportional indexing. Dependencies: 01–03. Risk: Medium–High, coordinate/domain conventions. Tests: HEIC/JPEG, mixed sizes, variable-rate video, per-frame K, LUT identity/nonidentity, depth alignment, older exports.

### CHANGE-06 — Strict photo reconstruction: bounded feasibility gate

**P0; REQ-02, 05, 07–10, 28–29, 41–42.** SfM, dense scale/dense reconstruction, OpenMVS, metric depth, workflow.

Current: successful RGB reconstruction needs measured controls; sparse pose initialization fails; learned-depth trials do not justify cm claims. Keep seeded SIFT/COLMAP, explicit room groups and all-input accounting. Preserve camera calibration and uncertainty. One bounded experiment: pinned MoGe-2 small, native photos processed at fixed 1024-pixel long edge; score registered multi-view structures rather than raw depth alone. Registered SfM: one positive scale from consistent predicted depths and reconstructed feature depths. Failed SfM: verified-correspondence robust point-map rigid registration. Require observed support, otherwise fail honestly. Use two-view dense path for two images, not fixed three-view fusion. Label learned geometry model_scaled, distinct from sensors.

Development correction must freeze before calibration/audit; laser truth never selects inference scale. Promotion requires native 2–8-photo property outputs and applicable wall/footprint/topology/opening/ceiling/calibration/runtime gates on untouched audit. The old low-resolution MoGe failure stays a failure; this new structural experiment is planned, not demonstrated. Project: https://github.com/microsoft/MoGe.

Neither reference proves this workflow. Do not adopt assumed camera height/disconnected placement. Dependencies: 03–05; 07–10 shared integration. Risk: High. Tests: preselected 2/4/8 views, planar/panoramic, unknown K, concavity, strict no-input-depth/poses/controls, held-out metrics. **If experiment fails, RGB compliance stays open; assisted substitution is forbidden.**

### CHANGE-07 — Supported walls and per-room ceilings

**P0; REQ-07–08, 25–26, 40, 42.** layout, observed ceiling, supported cells, RGB-D.

Current: polygon/ceiling functions exist but convex hull can overstate observed coverage and captures remain partial. Preserve concave supported polygons; add occupied-cell ceiling coverage/distribution/occlusion checks and per-room floor/ceiling evidence. Improve planes with development truth/residuals. Unobserved ceiling stays unavailable. Never widen gap closure to force completeness. Separate bias/repeat spread. Sloped ceilings report geometry/range and retain unknown scoring-definition hold.

Evaluate A's broad support idea, not fixed ceiling fallback. Dependencies: 04–06. Risk: Medium–High. Tests: furnished/partial ceilings, beams, disconnected support, slopes, L rooms, open boundaries, repeats.

### CHANGE-08 — Physical opening detection and dimensions

**P0; REQ-09–10, 14, 24, 42.** layout, assessment, opening scorer, shared detector.

Current: traversed-door proposals, incomplete exterior doors/windows/heights. Candidates in wall coordinates; observed jamb/header/sill or compatible multi-view evidence; distinguish doors/windows/occlusions/gaps; raw-observation edge refinement; width/observable height; deduplicate physical instances; link both room faces; count missed/phantom detections.

Adopt coarse proposal/raw edge-refinement principle from B's `geometry/manhattan_room.py::_detect_openings/_refine_opening_edges`, not claimed gate passes/fixed intervals. Dependencies: 01, 05–07. Risk: High. Tests: doors/windows, furniture gaps, multiple openings, duplication, partial jambs, false positives/negatives.

### CHANGE-09 — Stock video and drift accountability

**P0; REQ-03, 07–10, 27, 29, 41.** intake, SfM, mapping, pose ablation.

Current: stock video shares scale blocker; verified correction mainly RGB-D; ablation sums room areas. Use timestamp keyframes and accepted RGB backend; ordered verified loops; correction before fusion; posed-video variant remains. Identical-input on/off runs compare UNION footprint, overlap/topology/pose changes and surveyed error where available. No verified loop/zero change is reported as such, not demonstrated correction.

Do not replace current graph with A's proximity-only loops/yaw regularization. Dependencies: 05–08, 10 integration. Risk: High. Tests: return loops, corridors, variable rates, tracking interruptions, false loops, ablation identity.

### CHANGE-10 — Automatic whole-property graph, every tier

**P0; REQ-05, 10, 19, 21, 27–28.** stitching, assisted pipeline, layout, workflow.

Current: RGB-D verified stitching/conditional assisted tests; no complete strict-photo property proof. Shared graph: room transforms, observed surfaces, physical openings, verified constraints. Photo folders use shared doorway/cross-room features; continuous video/LiDAR use corrected transitions. Optimize and check cycles. Reject unverified links/overlap, disclose disconnected incomplete components. Render coherent property. Ask for doorway context in protocol, never hidden manual adjacency.

Neither A's side-by-side rooms nor B's manual connectors proves automatic stitching. Dependencies: 06–09. Risk: High. Tests: three rooms+connector, repeated doors, cycles, insufficient overlap, wrong identities, concavity, overlap.

### CHANGE-11 — All-tier surface damage projection

**P0 tier coverage/metric projection; P2 further prescriptions; REQ-05, 11–14, 20, 42.** RGB-D damage, segmentation, surface union, inspection scope.

Current: experimental sensor-path candidates/rules/inspection, unverified class/extent. Shared view geometry: K, corrected poses, visibility, depth provenance, surfaces. Project RGB to wall with occlusion checks; retain union deduplication; stain area and crack centreline length, not bounding-box extent. Independent two-class annotation validation. Named conservative rules and evaluated-no-damage vs not-evaluated distinction. Uncertainty on quantities. Keep classical masks unless measured failures justify replacement.

B surface-linked actions are future reviewed options; no unconditional demolition/structural inference. Dependencies: 01, 04–10. Risk: Medium–High. Tests: staged marks, duplicate views, clean controls, shadows, surfaces, rules, units.

### CHANGE-12 — Integrate property-grouped calibration

**P0; REQ-14–15, 28–29, 42.** uncertainty, assessment, CLI.

Current fitter not wired; engineering envelopes uncalibrated. Preserve property maximum by tier/kind/unit. Assignment 90%, minimum nine independent properties per group for finite quantile. Artifact contains backend/config/units/count/splits/revision; reject mismatch/leakage; calibrate required quantities; disclose unavailable groups. Audit property-level simultaneous coverage and widths on untouched properties; refit after measurement changes. Three audit properties are limited evidence: report uncertainty/sample size and public-domain exchangeability assumptions, no population-proof claim.

Preserve grouping rather than pooled residuals. Dependencies: frozen 06–11, 04 data. Risk: Medium. Tests: 8 vs 9 at 90%, 19 at 95%, property grouping, units/missing groups, mismatch/split leakage.

### CHANGE-13 — Full benchmark, consumer and declared fix loop

**P0; REQ-19–31, 35–36, 38, 42.** benchmark, gates, repeatability, ablation; comparison/fix runners.

Current separate partial tools; no full own consumer/fix bundle. Canonical outputs vs isolated survey truth; one rigid no-scale alignment; all instances counted, not skipped for different vertex counts. Every gate/tier, missing truth/unknown rule separate. Same two rooms: own LiDAR vs actual magicplan export. Every eligible shared dimension with reasons for exclusion/missing; exact error tie with numerical epsilon, not centimetre allowance; ≥70% beat/tie required.

Fix loop: freeze full development baseline/producer; select worst measured required gate (ties: openings, ceiling, walls, repeatability, photo stitch, drift); write failing number/evidenced root cause/intended change/numeric prediction BEFORE implementing chosen fix; ship; regenerate identical-input/rule before/after; readable source/config diff; honest prediction post-mortem; refit calibration then untouched audit. Do not invent a predicted number during planning without baseline.

Adopt B's reproducible variant comparison (`fix_loop/run_fix_loop.py`), not permissive phantom accounting/pass claims. Dependencies: 01–12; baseline infrastructure begins earlier. Risk: Medium–High. Tests: missing/phantom/unmatched entities, repeat identity/same-file evidence rejection, consumer mapping, baseline replay/input equality.

### CHANGE-14 — Documents, reproduction and unseen rehearsal

**P1 with mandatory acceptance; REQ-01, 06, 32–41.** README, existing docs, render_reports, report/bundle scripts.

Current documentation has historical/stale statements. Update design MD with Mermaid; artifact-driven compliance, literal one-page protocol/device matrix, current architecture figures. Technical PDF ≤6 pages using existing plotting stack; every number linked to artifact, raw truth/consumer exports included. Clean setup/fresh live capture timed; unseen all-tier rehearsal follows page without verbal assistance. Commit real implementation milestones, never fabricated timestamps/history, preserve unrelated dirty files. Distinguish considered/implemented/tested/rejected/validated and disclose third-party provenance.

A concise PDF principle useful; no new frontend framework. Dependencies: 01–13. Risk: Low–Medium. Tests: pages/links/assets, clean reproduce, literal protocol, runtime, unseen results.

## 3. Strengths to preserve and approaches not to adopt

| Existing component | Preserve | Requirements |
|---|---|---|
| mapping.optimize_poses | Verified visual/geometry constraints | 27 |
| stitching.stitch_runs | Verified registration, explicit disconnected components | 10,42 |
| supported_cells | Evidence thresholds, no arbitrary closure | 07,10,42 |
| layout.extract_layout | Nonrectangular polygon support | 07,10 |
| observed_ceiling | Observed estimates/unavailable values | 08,25 |
| dense.measured_scale | Labelled validated assisted controls | Research/regression |
| uncertainty.fit_calibration | Property grouping/finite samples | 14–15 |
| opening scorer | One-to-one matching/phantom penalties | 24 |
| benchmark | Global rigid no-scale evaluation | 28–29,42 |
| workflow | Hashes, fresh output, timing, failure artifacts | 17,35 |
| damage union/inspection | Deduplication/conservative named rules | 11–13 |
| Assisted/public workflows | Labelled development/regression | 35,42 |

| Source/location | Do not adopt | Reason |
|---|---|---|
| A pipeline photo document | Disconnected room placement | No property adjacency proof |
| A room document | Fixed ceiling/hardcoded opening wall | Unsupported measurement |
| A video ingest | Proportional indexing/fixed image assumptions | Calibration/time errors |
| A drift | Unverified proximity loops | Weaker than verified graph |
| A fresh-clone script | Local data symlink as independent proof | Reviewer needs raw bundle |
| A depth correction | Dataset-specific constant | Cannot transfer blindly |
| B photo tier | Capture-root dependence/assumed height | Not strict independent stills |
| B stitch_rooms | Manual connectors | Conditional tests only |
| B room box | Mandatory rectangle | Corridors/concavity lost |
| B scope | Unsupported strong restoration prescriptions | Not required/validated |
| B evaluation | Missing-height/phantom omissions/permissive ties | Weaker scoring |
| Both architecture | Wholesale replacement | No demonstrated benefit |

No direct code copying is planned. Future reuse requires appropriate permission and attribution.

## 4. Dependency-aware sequence

1. 01–02 acceptance/reliable baseline before trusting results.
2. 03 actual CPU deployment before model behavior.
3. 04–05 verified exports, survey and normalization; collect alongside code.
4. 06 strict RGB feasibility early, not deferred to packaging.
5. 07–08 shared geometry/openings on development truth.
6. 09–10 video correction and property integration.
7. 11 damage after stable surfaces/view geometry.
8. 12 calibration after measurement freeze.
9. 13 complete development benchmark, declare targeted fix before implementation, consumer/audit.
10. 14 reviewer packaging/cold unseen rehearsal.

Focused integration checks after every subsystem; repeated E2E as tiers become usable.

## 5. Testing and evidence

Unit tests: compatibility/references; failing exit status; orientation/K; timestamps; depth units/quaternions/LUT domain; disconnected ceiling support; opening identities/edges; registration/cycles; damage units/dedup; finite grouped calibration; missing truth/measurements/phantom scoring.

Integration: raw→normalized→geometry→assessment→render; shared doorway from two faces; corrected poses→fusion→footprint; RGB/sensor surfaces; deterministic cache; calibration→interval→evaluator; stage failures→ledger/nonzero status.

| E2E | Proof |
|---|---|
| Photos | Preselected 2/4/8 strict inputs, full adjacency/nonoverlap, ±8% walls/footprint, other applicable gates |
| Video | Native live walkthrough, ±3% walls, complete property |
| LiDAR | Original current Pro export, calibrated intake, known/unknown official gates |
| Repeat | Independent identities, wall agreement, ceiling spread/bias |
| Drift | Same-input on/off property footprint |
| Damage | Furnished annotations, class/metric/surface/rule/scope |
| Consumer | Same two rooms, own LiDAR, actual export, dimension table |
| Fix | Prior declaration, regenerable before/after |
| Clean machine | Fresh live result <15min |
| Unseen rehearsal | Literal protocol, no truth-driven correction |

Edge cases: low texture/rotation/blur/light, reflective/wet surfaces, furniture, closed doors, narrow corridors/repeated doors, partial/sloped ceilings, lost tracking, incomplete exports, units/confidence, missing calibration/overlap. Honest failure still counts as failed assessment case.

Regression: supplied Stray coordinates; synthetic/public RGB-D; assisted/stitch; render formats; unavailable observations; registration rejection; truth read after inference. Small fixtures tracked, large raw assets bundled.

Each requirement needs source and behavior artifact. Render is not accuracy, interval presence is not calibration, replay is not independent repeat, supplied connectors are not automatic stitching, synthetic success is not phone proof, copied output is not regeneration.

## 6. Risks

| Change | Risk | Mitigation |
|---|---|---|
| 01 | Medium migration/identity | Version adapters/equivalence |
| 02 | Low–Medium status changes | Document status, retain geometry semantics |
| 03 | Medium portability/cache | Pinned assets/hash/cold checks |
| 04 | High field/hardware/sample access | Collect early, explicit holds |
| 05 | Medium–High calibration/time | Golden exports/domain validation |
| 06 | High scale/observability/model bias | Bounded promotion gate |
| 07 | Medium–High geometry/topology | Support evidence/regression/survey |
| 08 | High phantom/boundary error | Multi-view raw edge/penalties |
| 09 | High drift/runtime | Verified constraints/ablation/budget |
| 10 | High ambiguous connections | Overlap/cycles/disconnection |
| 11 | Medium–High appearance/projection | Annotations/visibility/conservative rules |
| 12 | Medium incompatible/insufficient calibration | Fingerprints/refit |
| 13 | Medium–High leakage/reproduction | Frozen inputs/audit/producer snapshots |
| 14 | Low–Medium claims/live mismatch | Artifact claims/cold rehearsal |

No distributed service/concurrency layer required. Local capture processing with bounded cancellable subprocesses.

## 7. Updated requirement coverage

Current status is the full requirement, not function presence. IMPLEMENTED* is a conditional target only after acceptance evidence. Failed/insufficient cases stay partial. 01–41 explicit; 42 strongly implied validity/evidence. Optional work excluded.

| REQ | Requirement | Current | Changes | Expected | Priority |
|---|---|---|---|---|---|
| 01 | Stock route | PARTIAL | 04,05,14 | IMPLEMENTED* literal rehearsal | P1 |
| 02 | Independent 2–8 stills | PARTIAL | 05,06,10 | IMPLEMENTED* strict acceptance | P0 |
| 03 | Base iPhone video | PARTIAL | 05,06,09 | IMPLEMENTED* native acceptance | P0 |
| 04 | LiDAR depth/pose/K | IMPLEMENTED supplied | 05 | IMPLEMENTED* current export | P0 |
| 05 | Common all-tier output | PARTIAL | 01,06–12 | IMPLEMENTED* | P0 |
| 06 | Honest device matrix | PARTIAL | 04,14 | IMPLEMENTED* measured | P1 |
| 07 | Walls/floor area | PARTIAL | 06,07,10 | IMPLEMENTED* all tiers | P0 |
| 08 | Room ceiling | PARTIAL | 07 | IMPLEMENTED* surveyed | P0 |
| 09 | Opening instances/dimensions | PARTIAL | 08 | IMPLEMENTED* | P0 |
| 10 | Property adjacency | PARTIAL | 10 | IMPLEMENTED* all tiers | P0 |
| 11 | Surface damage class/extent | PARTIAL | 11 | IMPLEMENTED* validated | P0 |
| 12 | Concealed fired rules | IMPLEMENTED local | 01,11 | IMPLEMENTED* all tiers | P0 |
| 13 | Surface scope | IMPLEMENTED inspection | 01,11 | IMPLEMENTED* all tiers | P0 |
| 14 | Every measurement interval | PARTIAL | 01,12 | IMPLEMENTED* | P0 |
| 15 | Every tier calibration | PARTIAL | 04,12,13 | IMPLEMENTED* sufficient groups | P0 |
| 16 | Published schema | UNCLEAR | 01+external | UNCLEAR until supplied | P0 hold |
| 17 | One command | PARTIAL | 02,05 | IMPLEMENTED* | P0 |
| 18 | Rendered plan | IMPLEMENTED supported | 01,10,14 | IMPLEMENTED* all tiers | P1 |
| 19 | 3 rooms PLUS connector | UNCLEAR | 04,13 | IMPLEMENTED* identified benchmark | P0 |
| 20 | Furnished staged two classes | MISSING | 04,11 | IMPLEMENTED* | P0 |
| 21 | Same spaces all tiers | MISSING | 04 | IMPLEMENTED* | P0 |
| 22 | Independent repeat | UNCLEAR | 04,13 | IMPLEMENTED* | P0 |
| 23 | Truth everything | PARTIAL | 04,13 | IMPLEMENTED* | P0 |
| 24 | Openings 2cm/85% incl misses/phantoms | PARTIAL | 01,08,13 | IMPLEMENTED* measured pass | P0 |
| 25 | Ceilings 1.5cm/repeat1cm | PARTIAL | 07,13 | IMPLEMENTED* measured pass | P0 |
| 26 | Wall repeat1cm or .5% | PARTIAL | 07,09,13 | IMPLEMENTED* measured pass | P0 |
| 27 | Drift correction/ablation | PARTIAL | 09,10,13 | IMPLEMENTED* | P0 |
| 28 | Photo stitch/±8%/calibration | PARTIAL | 06,10,12,13 | IMPLEMENTED* strict measured pass | P0 |
| 29 | Photo ±8%, video ±3% walls | PARTIAL | 06,09,12,13 | IMPLEMENTED* measured pass | P0 |
| 30 | 2-room LiDAR consumer≥70% | MISSING | 04,13 | IMPLEMENTED* measured pass | P0 |
| 31 | Declared shipped regenerable fix | PARTIAL | 13 | IMPLEMENTED* bundle | P0 |
| 32 | Real commit history | PARTIAL | 14 | IMPLEMENTED future; no fabrication | P1 |
| 33 | Compliance matrix | PARTIAL | 01,14 | IMPLEMENTED* | P1 |
| 34 | Clean fresh <15min | PARTIAL | 03,14 | IMPLEMENTED* timed | P0 |
| 35 | All numbers/live reproducible | PARTIAL | 03,13,14 | IMPLEMENTED* | P0 |
| 36 | Benchmark reports/timing | PARTIAL | 13,14 | IMPLEMENTED* | P1 |
| 37 | Technical report≤6pages | MISSING final | 14 | IMPLEMENTED* | P1 |
| 38 | Raw logs/truth/app exports | PARTIAL | 04,13,14 | IMPLEMENTED* | P0 |
| 39 | Consumer/disclosure/no own infra | PARTIAL | 03,05,14 | IMPLEMENTED* | P1 |
| 40 | Adverse conditions covered | PARTIAL | 04,07–11,14 | IMPLEMENTED* evidence | P1 |
| 41 | Unseen cold readiness | UNCLEAR | 06–14 | IMPLEMENTED* rehearsal; defense external | P0 |
| 42 | Validity/isolation/provenance | PARTIAL | 01–13 | IMPLEMENTED* integrity checks | P0 |

Missing Round 1 rules are an additional external hold. Do not invent LiDAR/calibration rules to make the matrix green.

## 8. Minimal change set and priority

**MUST:** contract/evaluator; false status/portable tests; strict RGB; full openings/ceilings/property; all-tier damage/calibration; surveyed same-tier/repeat/consumer benchmark; declared regenerable fix; live deployment/submission evidence.

**SHOULD:** producer-aware caches/current exports; artifact accounting; additional RGB repeats; runtime diagnostics; unseen rehearsal.

**COULD:** reviewed scope expansion; reflection detectors; learned/GPU backends after measured need; convenience reports.

**SHOULD NOT:** replace core CLI/verified graph/property calibration/truth isolation/supported polygons/honest nulls/labelled research paths.

| Priority | Change | Files | Reason | Risk | Effort |
|---|---|---|---|---|---|
| P0 | 01 Contract | assessment/contracts/gates/schema | Trustworthy scoring | Medium | Medium |
| P0 | 02 Baseline | cli/workflow/tests | No false success/local-only tests | Low–Medium | Small |
| P0 | 03 Deploy | pyproject/workflow/openmvs/scripts | Reproducible reviewer execution | Medium | Medium |
| P0 | 04 Physical | protocol/benchmark | Required proof missing | High | Large field |
| P0 | 05 Intake | ingest/workflow | Identity/calibration | Medium–High | Medium |
| P0 | 06 Strict RGB | sfm/dense/metric_depth/workflow | Largest blocker | High | Large uncertain |
| P0 | 07 Geometry | layout/supported_cells/rgbd | Tight measurement gates | Medium–High | Medium–Large |
| P0 | 08 Openings | detector/layout/assessment | Detection/width gate | High | Large |
| P0 | 09 Video | ingest/sfm/mapping/ablation | Live drift accountability | High | Large |
| P0 | 10 Graph | stitching/layout/workflow | Required product | High | Large |
| P0 | 11 Damage | damage/assessment | All-tier contract | Medium–High | Medium–Large |
| P0 | 12 Calibration | uncertainty/assessment/cli | Statistical intervals | Medium | Medium+data |
| P0 | 13 Proof | benchmark/gates/repeat/runners | Accuracy/fix/consumer evidence | Medium–High | Large |
| P1 | 14 Deliver | README/docs/reports/bundle | Defensible submission | Low–Medium | Medium |

Sequence: acceptance baseline → reproducible environment → capture/survey → strict RGB feasibility → geometry/openings → video/property → damage → calibration → declared fix/consumer/audit → packaging/cold rehearsal.

Executive decision: preserve the architecture and strengthen measurement/evidence paths. Reference ideas do not resolve principal compliance risks. Completion requires measured strict RGB success, required physical evidence, and resolution of official acceptance inputs. Alternative design options must never be described as implemented/tested without actual artifacts.
