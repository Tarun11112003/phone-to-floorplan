# Final assignment compliance matrix

Source: [Applied AI.html](Applied%20AI.html), inspected at finalization.
Current worktree is the baseline. **Full assessment acceptance is NOT DEMONSTRATED.**
Statuses use PASS, PARTIAL, FAIL, NOT DEMONSTRATED and INCONCLUSIVE as defined in
[validation](BENCHMARK_RESULTS.md). Software output/scorers are not physical passes.
Evidence IDs below refer to [the manifest](evidence/final_state.json) and the
separate handoff's original records. No unavailable specification is invented.

## Inputs and capture

| Requirement | Implementation /evidence | Status | Notes /limitation |
|---|---|---|---|
| Photos: 2–8 stills/room, iPhone 15+, no depth/poses | `ingest.prepare_photos`, `workflow.read_manifest`; SfM and strict-profile tests | PARTIAL | Intake/profile supported; reliable metric whole-property output not demonstrated |
| Video: handheld native walkthrough | `prepare_video`, `sfm.reconstruct_rgb`; transition records019–028 | PARTIAL | Media/timing supported; supplied RGB property model incomplete; registration investigation inconclusive |
| LiDAR: Pro depth/poses/intrinsics | `prepare_stray_scanner`, `rgbd.reconstruct_rgbd`; supplied scans and batch032 | PARTIAL | Real supplied raw sensor data exercised; complete physical geometry and cold device route not proven |
| Route 2: named stock tools and literal one-page protocol | [protocol](CAPTURE_PROTOCOL.md), [device matrix](DEVICE_MATRIX.md) | PARTIAL | Operational candidate; no novice/unseen rehearsal |
| Hardware/accuracy matrix | device matrix | PARTIAL | Availability stated; independently measured per-device/tier accuracy absent |
| Calibration, synchronized frames and metric provenance | intake/capture_sync/rgbd; batch030/032 exact checks | PARTIAL | Per-frame extraction verified; physical depth/distortion/pose calibration unverified |

## Outputs and contract

| Requirement | Implementation /evidence | Status | Notes /limitation |
|---|---|---|---|
| Dimensioned per-room plans and walls | layout/export; plan/diagnostic artifacts | PARTIAL | Supported dimensions/proposals available; supplied properties remain incomplete |
| Floor area | polygon/quantity output | PARTIAL | Computed from inferred/observed boundaries, not independently surveyed |
| Ceiling height | `_observed_floor`, `_observed_ceiling`; records030–032 | PARTIAL | room_2 height unavailable; no fabricated global-floor/constant-height fallback |
| Opening detection/dimensions | openings module, multiview/raw-edge tests | PARTIAL | Missing/phantom scoring implemented; closed doors/occlusion/physical edge truth absent |
| Whole-property stitch and correct adjacency | `stitch_runs`, pose_graph, controlled chain tests | PARTIAL | Verified constraints exist; strict-photo/physical full-property result not demonstrated |
| Per-surface damage class and metric extent | damage/assessment/damage_evaluation; shipped registered-view fix | PARTIAL | Candidates and metric projection exist; independent two-class/clean-control validation absent |
| Concealed flags and fired rules | damage scope and assessment rule IDs | PARTIAL | Conservative rule flags exist; hidden damage is not directly observed |
| Scope keyed to surfaces | assessment/scope output | PARTIAL | Inspection items available; field classification/scope validation absent |
| Confidence interval on every measurement | uncertainty and calibration record builders | PARTIAL | Missing/unsupported groups remain unavailable; required field calibration absent |
| One command per capture and review artifacts | `run-capture`, JSON/HTML/conditional SVG/DXF/CSV | PASS | Command/interface behavior only; many captures correctly fail readiness |
| JSON to published schema | internal schema/contracts tests | NOT DEMONSTRATED | Published schema absent; internal v2 is provisional |

## Benchmark composition and evidence

| Requirement | Evidence /artifact | Status | Notes /limitation |
|---|---|---|---|
| Three or more rooms plus connector | benchmark manifest auditor/templates; controlled chain fixture | NOT DEMONSTRATED | Synthetic chain is not required physical property |
| Furnished room, two staged damage classes | damage evaluator/templates | NOT DEMONSTRATED | Qualifying captures/annotations not supplied |
| Same rooms at all three tiers | benchmark composition checks | NOT DEMONSTRATED | Supplied cases do not establish verified same-property/tier benchmark |
| Same room captured twice at same tier | repeat evaluator | NOT DEMONSTRATED | Temporal frames or identical replay are not independent capture repeats |
| Laser/tape truth for everything | survey importer/templates | NOT DEMONSTRATED | No qualifying independent property measurement set |
| Submit raw data/measurements | original supplied data +indexed local evidence | PARTIAL | Supplied raw sensor case exists; required own raw benchmark/truth/app exports absent |
| Benchmark/timing report | validation ledger +run monitoring | PARTIAL | Software/audit timings retained; complete capture/install/runtime table absent |
| Mirrors, glass, wet-look surfaces, low light | conservative failure paths | NOT DEMONSTRATED | Required condition-specific capture and scoring evidence absent |

## Accuracy and acceptance

| Requirement /gate | Implementation /evidence | Status | Notes /limitation |
|---|---|---|---|
| Openings <=2 cm on >=85%; misses/phantoms scored | assignment_gates, opening scorer tests | NOT DEMONSTRATED | No detection-aware independent physical scores |
| Ceiling <=1.5 cm/room | ceiling scorer | NOT DEMONSTRATED | Missing local heights and independent measurements |
| Repeated ceiling spread <=1 cm | repeatability scorer | NOT DEMONSTRATED | Independent repeats absent |
| Wall repeats within 1 cm OR0.5% | repeatability scorer | NOT DEMONSTRATED | Software scoring tested; field agreement absent |
| Drift accountability; on/off footprint ablation | mapping/ablation, matched-input checks | PARTIAL | Mechanism exists; effective measured correction/qualifying property ablation not proven |
| Photo whole-property adjacency/no overlaps/footprint +/-8% | property/assignment scorers | NOT DEMONSTRATED | Strict RGB property reconstruction incomplete |
| Photo wall lengths +/-8% with calibrated intervals | assignment/uncertainty | NOT DEMONSTRATED | No qualifying physical tier benchmark/calibration |
| Video wall lengths +/-3% with calibrated intervals | same evaluator paths | NOT DEMONSTRATED | Current video transition evidence cannot certify wall accuracy |
| Calibration scored at every tier | property-grouped calibration/audit software | NOT DEMONSTRATED | Adequate independent fitting/audit properties absent |
| LiDAR accuracy /earlier Round 1 gates | provisional evaluator | NOT DEMONSTRATED | Earlier definitions absent; do not invent a LiDAR wall tolerance |
| Consumer comparison: two same rooms, app/version/export, >=70% beat/tie | compare-consumer/metadata and tie logic | NOT DEMONSTRATED | No original qualifying export or physical comparison table |
| Worst-gate prospective fix declaration, shipped fix, regenerable before/after | fix_evidence utility; engineering loops | NOT DEMONSTRATED | No qualifying measured benchmark/declaration; prior software fixes cannot be retroactively predeclared |

## Delivery, process and walk-in

| Requirement | Evidence /artifact | Status | Notes /limitation |
|---|---|---|---|
| Clean machine: README to fresh capture <15 min | bootstrap/requirements/operations | NOT DEMONSTRATED | No timed clean install/live-capture success |
| Reproduction bundle for every reported number | source snapshot, curated evidence manifest, original records | PARTIAL | Integrity/readability packaged; raw/model/absolute-path regeneration and missing physical evidence explicitly limited |
| Live path plus deterministic cache | producer/input/model cache checks | PARTIAL | Supported software path; no full three-tier cold/live demonstration |
| Max six-page technical report | [five-page report](TECHNICAL_REPORT.pdf) | PASS | Document/page-cap delivery only; not acceptance of its unresolved gates |
| Incremental process history and live defense | genuine existing commits +focused final documentation commits | PARTIAL | History preserved; defense not yet conducted and early history not fabricated |
| No infrastructure dependence, disclosed external assets | local CPU pipeline, source decisions | PARTIAL | Download/offline preparation needed; deployment rehearsal absent |
| Unseen capture on examiner's iPhone 15+, tier chosen on day | capture route and interface | NOT DEMONSTRATED | All-tier reliable cold results not established |

Scoring is 30% walk-in, 25% Fix Loop, 15% three-tier accuracy, 10% compliance,
10% consumer comparison, 5% capture route and 5% process. Documentation does not
earn a physical gate or replace a shipped measured fix. The final status remains
**partial implementation with reproducible software evidence and material acceptance gaps**.
