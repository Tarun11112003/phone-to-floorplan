# Assignment compliance audit — 2026-10-06

**Implementation update, 2026-10-06:** The initial audit table below records the
pre-change baseline. Since then, `floorplan/assignment_gates.py` and
`evaluate-assignment` score the stated wall/opening/height/interval/footprint gates;
`floorplan/ingest.py` and `run-capture` normalize room photo folders, MOV/MP4 and
Stray Scanner-format RGB-D; [capture protocol](CAPTURE_PROTOCOL.md) and
[device matrix](DEVICE_MATRIX.md) document Route 2. The current test suite passes
28 tests. A two-photo capture produces an auditable failure because the existing
SfM backend requires five overlapping images. Frozen V3 plans fail the new
assignment gates for missing ceiling heights and intervals. Physical benchmark,
sparse 2-view geometry, metric RGB scale, 3+room stitch, damage/scope, interval
calibration and schema conformance remain incomplete.
The repository was initialized at this current-state baseline on 2026-10-06;
earlier local work has no recoverable commit history in this workspace. See
[incremental E2E evidence](ASSIGNMENT_E2E_STATUS.md) for the new checks.

Source of authority: [Applied AI.html](<Applied AI.html>), Cozmo AI Case Study, Aug 2026.
This audit supersedes earlier descriptions of assignment readiness. V3 is a useful
geometry prototype; it is not a compliant Round 1 submission. Its custom benchmark
passes are not passes against this newly supplied brief.

## Evidence inspected

- Current implementation under `floorplan/`, CLI, acquisition scripts and tests.
- `demo/v3_verified/*/plan.json` and `run.json`: two rooms per tier, all automatic
  ceiling heights null, RGB runs reuse sparse reconstruction caches.
- [V3 results](V3_RESULTS.md): controlled synthetic photos/video/depth, provisional
  real-phone laser-reference result, and incomplete held-out ICL geometry.
- Fresh baseline test: 18 passed in 18.42 seconds; record at
  `demo/assignment_audit_20261006_tests.xml`. No expensive reconstruction was rerun
  for this audit; previously generated results were inspected.
- `git status` and `git log`: this workspace is not a Git repository.

Status meanings: **partial** = reusable implementation with missing acceptance
evidence or behavior; **missing** = no matching implementation/artifact found;
**blocked definition** = external specification absent from the supplied brief.
An honest partial output is preferable to a fabricated value, but still fails a
required assignment output or gate.

## Requirement → code → artifact → status

| Requirement | Existing file(s) | Existing evidence / gap | Status |
|---|---|---|---|
| Installable capture route or one-page stock protocol | `scripts/prepare_arkit.py` | Public dataset adapter only; no operator-tested phone-to-PC protocol | Missing |
| Device matrix, including non-Pro iPhone 15+ | `docs/V3_IMPLEMENTATION.md` | CPU notes; no measured tier/device matrix | Missing |
| 2–8 photos per room, no depth/poses | `floorplan/sfm.py` | V3 uses 97 images; fewer than five total images rejected; no low-view fallback | Partial, required tier unproven |
| Per-room photo folders → whole property | `floorplan/sfm.py`, `stitching.py` | Images read from one flat folder; automatic separate-capture stitch requires RGB-D | Missing |
| Handheld video on iPhone 15+ | `sfm.py`, `openmvs.py` | Synthetic encoded clip tested; live iPhone MOV/HEVC/calibration not demonstrated | Partial |
| Pro LiDAR depth, intrinsics, poses | `rgbd.py`, `prepare_arkit.py` | Real ARKitScenes works; selected stock-app export importer absent | Partial |
| One command per fresh capture | `cli.py`, `workflow.py` | One command after manual manifest preparation; separate stitch command; no cold capture-bundle import | Partial |
| Dimensioned walls / floor area | `layout.py`, `pipeline.py` | JSON/SVG/DXF/CSV produced | Partial: geometry exists, assignment gates not established |
| Ceiling height per room | `layout.py:178` | Automatic pipeline writes `ceiling_height_m: None`; assisted example supplies it manually | Missing |
| Openings: detection, dimensions, surface association | `layout.py` | Traversed inter-room doorway gaps only; windows, untraversed doors, exterior openings not evaluated | Partial |
| Every room placed, correct adjacency, no overlaps | `layout.py`, `stitching.py` | Two-room controlled result; no 3+ rooms and connector photo-folder test | Partial |
| Per-surface damage class and metric extent | None | No damage model, masks, projection, surface IDs or damage evaluation | Missing |
| Concealed-damage flags and rule fired | None | No rules/evidence trace | Missing |
| Scope line items keyed to surfaces | `pipeline.py` | Room-level quantities are not restoration scope items | Missing |
| Confidence interval on every measurement | None | Depth confidence / RANSAC confidence are not calibrated output intervals | Missing |
| JSON conforms to published schema | Internal schema in `layout.py` | Published schema not supplied; internal version 2 cannot be assumed compatible | Blocked definition |
| Rendered whole-property plan | `pipeline.py` | SVG and DXF exist; confidence/damage/surface overlays absent | Partial |
| 3+ rooms plus connector, same rooms at every tier | `make_multimodal_fixture.py` | Synthetic two-room fixture with one door; no required physical benchmark | Missing |
| Furnished room with two staged damage classes | None | No such raw captures or annotations | Missing |
| Laser/tape truth on everything, raw files submitted | `annotate_laser_reference.py` | One provisional FARO room; no independent full wall/height/opening/damage survey of required rooms | Partial |
| Same room captured twice at same tier | None | Rerunning the same files is not repeat capture | Missing |
| Opening ≤2 cm on ≥85%, missed/phantom penalized | `benchmark.py:95` | Current gate is P95 ≤3 cm; matches by room pair; collapses adjacency into sets | Wrong evaluator |
| Ceiling ≤1.5 cm, repeated height spread ≤1 cm | None | Neither predictions nor gate | Missing |
| Wall repeatability ≤1 cm or 0.5% | None | No paired-capture measurement correspondence/evaluator | Missing |
| Drift correction and footprint on/off ablation | `mapping.py`, `rgbd.py`, `sfm.py` | Pose optimization exists; sensor path has no feature-verified historical loops; no required multi-room ablation | Partial |
| Photo walls ±8%, video walls ±3%, calibrated intervals | `benchmark.py:103` | Uniform absolute 3 cm wall P95 gate; no tier gates or interval calibration | Wrong evaluator |
| Photo property footprint ±8%, no overlaps | `benchmark.py` | Room areas evaluated; no explicit footprint-relative-error/overlap gate | Missing gate |
| Two-room consumer-app comparison, ≥70% beat/tie | None | No app/version, actual exports, matching dimensions or comparison table | Missing |
| Prospective one-page fix declaration | `docs/V3_RESULTS.md` | Retrospective diagnosis; no recorded prediction made before a new fix | Missing |
| Regenerable before/after and readable fix diff | `demo/v3_visibility_refit`, V3 artifacts | Useful lead, but no immutable source versions or packaged replay | Partial |
| Meaningful implementation commit history | None | No `.git` repository here; lost history cannot be manufactured | Missing |
| Clean machine running on fresh capture <15 min | `pyproject.toml`, installer | No timed clean-machine test; dependency ranges and absolute cache paths | Partial |
| Reproduction bundle, live path and deterministic cache | `workflow.py` | Input hashes exist; paths are machine-specific; no portable full bundle or determinism proof | Partial |
| Technical report ≤6 pages | Existing Markdown docs | Working notes exceed a final report's scope; no page-checked final report | Missing |
| Cold unseen capture, tier selected on the day | None | No complete rehearsal with external operator and independent ground truth | Missing |
| Mirrors/glass/wet-look/low light | Failure gates | No explicit labeled challenge coverage | Missing evidence |

## Consequences for the previous demo claim

The 0.57–0.87 cm controlled RGB wall errors remain valid for the tested inputs.
They use a dense overlapping capture, calibrated intrinsics and a simulated measured
scale. They do not establish performance on 2–8 unposed photos per room. Simulated
LiDAR has exact poses and cannot stand in for the required handheld sensor test.

The final V3 RGB timings (~195 s photos, ~179 s video) exclude sparse reconstruction
because they reuse caches. Future timing tables must distinguish cold full runs,
warm runs, cache replay, installation and download time.

Changing a synthetic texture fixed a fixture ambiguity; that is not a shipped
algorithm fix on unchanged assignment data. The visibility-filter experiment is a
more relevant same-input fix, but a retrospective prediction must not be invented.

## Definitions still needed

The HTML references earlier Round 1 gates and a published JSON schema without
including them. Request those definitions before declaring exact schema compliance
or asserting omitted damage, LiDAR wall, area and calibration thresholds. Freeze
provisional internal definitions visibly and replace them when the spec arrives.

The brief does not explicitly authorize a mandatory manual scale measurement or
marker for RGB capture. Earlier project permission to use scale controls is not
evidence that an examiner will supply them. Test the default no-depth/no-pose input
path; disclose metric priors and their error. Absolute monocular scale and disconnected
room placement cannot be guaranteed for arbitrary views without sufficient evidence.

For “1 cm or 0.5%” repeatability, report both absolute and relative differences;
provisionally use `max(0.01 m, 0.005 * reference wall length)` while flagging that
interpretation. Confirm the official opening-score denominator and the intended
footprint definition. Report component counts and alternative footprint measures
so a definition change does not require rerunning inference.

## Priorities by scoring exposure

Walk-in readiness (30%) and a prospective, reproducible fix (25%) are the largest
scoring risks. Sparse-photo feasibility and capture-to-contract integration must be
tested early. Real benchmark acquisition and consumer-app capture (10%) are external
data work that should start immediately, alongside code work. More synthetic tuning
alone cannot satisfy those rows.

Next implementation/test sequence: [Assignment update plan](ASSIGNMENT_UPDATE_PLAN.md).
