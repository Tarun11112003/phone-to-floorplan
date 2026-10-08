# Validation results and engineering decisions

This is the short evidence-led account of the work performed. Production SIFT
and conservative RGB-D geometry remain the final implementation. Experimental
connectivity, internal consistency and physical accuracy are separate claims.
The [benchmark ledger](../benchmarks/report.md) gives the complete status table;
the [evidence manifest](../benchmarks/manifests/final_state.json) identifies saved
source fields and hashes. No experiment was rerun to prepare this document.

## Supplied assessment data

All three supplied cases were exercised in the recorded reconstruction work.
The rows below use the retained exterior-support comparison, not different
frame budgets or a combination of unrelated runs.

| Supplied case | Camera samples inside proposed cells | Observed / inferred cell hypotheses | Adjacency connections | Status |
|---|---:|---:|---:|---|
| `single_room` | 40/115, 34.78% | 0 / 1 | 0 | PARTIAL |
| `single_scan_floor_only` | 25/176, 14.20% | 1 / 1 | 0 | PARTIAL |
| `single_scan_with_ceiling` | 295/300, 98.33% | 8 / 4 | 0 | PARTIAL |

Source: [retained comparison](../benchmarks/results/exterior_strip_summary.json),
`cases[*].after`. Camera containment measures traversal inside proposed
footprints. It is not surveyed floor-area coverage, dimensional accuracy or a
verified physical room count. Inferred cells remain explicitly labelled.

The final documented ceiling-scan command separately processed **300 frames into
202,477 points**, generated JSON, HTML, SVG, DXF and CSV, and exited **1 / partial**.
It wrote **zero accepted ceiling heights and zero adjacency connections**.
Command time was **221.196 s**; the reconstruction ledger reported **69.057 s**.
A committed-checkout run with fresh dependencies returned the same aggregate
readiness/counts in **211.239 s**. Source:
[workflow QA](../benchmarks/manifests/final_qa.json). These timings exclude physical
capture and transfer; the two runs are not an independent physical repeat.

## Shipped geometry improvement and its limit

| Metric, same retained floor input | Before | After | Interpretation |
|---|---:|---:|---|
| Wall proposals | 28 | 29 | Additional supported finite proposal recovered |
| Retained wall fragments | 67 | 69 | Two fragments added |
| Camera containment | 25/176 | 25/176 | Floor completeness did not improve |
| Prior accepted corners and connections | Baseline | Exact in controlled comparison | Existing supported geometry preserved |
| Runtime | 17.386 s | 17.419 s | Recorded comparison timing; no speedup claim |

Sensor tracing separated missing observations from residual-seed dilution. The
bounded seed/support change retained existing proposals and recovered finite
evidence without inventing a connecting wall. It is a shipped production
improvement, but its assessment outcome remains partial.
[Comparison](../benchmarks/results/exterior_strip_summary.json),
[detailed trace](engineering/investigations/014_exterior_strip_sensor_trace.md),
[Fix Loop](fix_loop.md).

## Video: more frames did not solve the transition

| Retained recipe | Input views | Verified pairs | Nontrivial groups / isolated views | Joint target-group model |
|---|---:|---:|---:|---|
| Baseline | 68 | 139 | 8 / 8 | No |
| 8 Hz transition bridge | 78 | 169 | 8 / 13 | No |
| 16 Hz transition bridge | 88 | 222 | 9 / 13 | No |

Both denser recipes reproduced their verified-pair totals on repeated trials.
Neither created a target-group connection under the existing guards. The
diagnostic localized insufficient stable SIFT support across the low-detail
transition; groups were not concatenated to inflate coverage.
[Saved bridge trials](../benchmarks/results/video_bridge_summary.json).

## Matched 32-view correspondence alternatives

The same RGB context was evaluated with the existing verification/mapping
thresholds. Sensor poses were withheld from RGB inference.

| Matcher | Candidate matches | Verified pairs | Graph components / isolates | Unique registered views | Joint target-group model |
|---|---:|---:|---:|---:|---|
| SIFT | 15,299 | 68 | 12 / 8 | 11 | No |
| DISK + LightGlue | 63,059 | 167 | 1 / 0 | 25 across separate models | No |
| XFeat + LighterGlue | 86,525 | 236 | 1 / 0 | 29 | Yes, experimental |

| Matcher | Sparse model result | Mean reprojection residual | Union-track conflicts / triangle contradictions |
|---|---|---|---:|
| SIFT | 11 views, 1,012 points | 0.636201 px | 59 / 46 |
| DISK + LightGlue | Separate 15/11-view models, 1,931/1,404 points | 1.449190 / 1.337805 px | 960 / 6,760 |
| XFeat + LighterGlue | 29 views, 5,455 points | 1.486099 px | 778 / 17,644 |

Conflict counts describe the union correspondence graph, not the number of
invalid landmarks accepted by the native mapper. Separate models cannot be
summed into one property. Source:
[matched context evidence](../benchmarks/results/xfeat_context_summary.json),
`runs`. The older 1,484-point conversational figure is not the authoritative
DISK 32-view result.

Recorded runtimes were 32.874 s for the cached SIFT diagnostic, 1,449.757 s for
DISK/LightGlue and 396.151 s for XFeat/LighterGlue. The stages/cache scopes differ;
these are not a controlled live speed ranking. DISK was not adopted because it
failed joint reconstruction. XFeat required independent post-hoc geometry audits
before any adoption decision.

## Fixed-intrinsics controls: useful improvement, insufficient adoption evidence

| XFeat control | Registered views | Sparse points | Mean reprojection residual |
|---|---:|---:|---:|
| Free intrinsics | 29 | 5,455 | 1.486099 px |
| Fixed intrinsics with reverification | 32 | 6,360 | 1.470216 px |
| Mapping-only fixed intrinsics, original verified rows | 32 | 6,187 | 1.480503 px |

| Post-hoc 24→27 comparison against supplied odometry | Free intrinsics | Fixed + reverification | Mapping-only fixed |
|---|---:|---:|---:|
| Rotation disagreement | 24.7720° | 5.1998° | 4.3191° |
| Translation-direction disagreement | 34.5951° | 10.2359° | 9.4821° |
| Relative-length ratio | 1.496456 | 1.080450 | 1.035232 |

Source: [mapping-only control](../benchmarks/results/mapping_only_summary.json),
`metrics` and `transition_metrics`. The mapping-only ablation preserved the
original verified inlier rows; no matching or verification was rerun. Odometry
was used only after reconstruction. The relative-length ratio uses the audit's
reference pair and is not an absolute metric scale or centimetre-accuracy result.

Later **31→34 rotation disagreement remained about 6.520814°**. Native replay
found disagreement immediately after accepted registration, before later local
refinement. Support auditing favored inherited geometry/concentrated support;
the final frame-31 replay did not reproduce the required snapshot because native
intermediate binaries differed. Causality remained **INCONCLUSIVE** and the
registration investigation was **CLOSED**. XFeat and fixed-intrinsics controls
remain experimental; no production solver fix was justified.
[Final audit](../benchmarks/results/frame31_final_summary.json).

## LiDAR support, sampling and ceiling acceptance

| Investigation | Before / retained | Diagnostic or candidate result | Final decision |
|---|---|---|---|
| Global stride-4 sampling | 25/176 containment | 79/176, but accepted polygon changed | Rejected; production stride retained |
| Ceiling-scan footprint selection | 148/300 containment; affected area 10.4774 m² | 295/300; area 9.9457 m²; boundary difference 0.702677 m | Boundary accuracy unvalidated |
| Native room_2 floor support | 148 points, 43 cells, 14.1246% | Below unchanged 25% guard | Floor/ceiling unavailable |
| Dense selected-frame floor returns | Native 14.1246% | 9,818 accepted returns, 92 cells, 29.2154% diagnostic union | No native acceptance fix tested/adopted |
| Full available raw floor returns | Selected 300-frame subset | 239,794 accepted returns, 135 cells, 44.0880% | Additional evidence exists; not physical truth |
| Native floor fusion | 150 returns, 148 local voxels | 148 retained voxels; zero occupied-cell loss | Sampling/frame selection, not fusion loss |

The ceiling-source audit inventoried 6,899 paired depth/confidence frames;
300 were selected. Selected confidence-2-only support was **20.6258%**, still
below 25%; dense accepted support above it includes confidence-1 observations.
Extraction and fusion reproduced exactly: **218,873 samples → 202,477 points**.
The 0.703 m change is a **floor-plan notch**, not a ceiling-height measurement;
height was unavailable before and after. Crossing rays do not independently
establish the physical perimeter.

Sources: [sampling](../benchmarks/results/lidar_sampling_summary.json),
[boundary](../benchmarks/results/ceiling_boundary_summary.json),
[ceiling decision](../benchmarks/results/observed_ceiling_summary.json),
[original floor returns](../benchmarks/results/room_floor_support_summary.json).

## What was finalized

Production retains SIFT, calibrated RGB-D extraction/fusion, supported finite
geometry and conservative acceptance. Shipped pixel-centre and registered-damage
guards have software regression evidence; field damage accuracy is not measured.
Denser sampling, learned matching and intrinsics ablations were not promoted.
The [engineering index](engineering/README.md) provides deeper traces and commands.

Independent measured three-tier accuracy, complete adjacency/ceilings, physical
repeatability, calibrated field intervals, consumer comparison and the qualifying
prospective worst-gate Fix Loop remain **NOT DEMONSTRATED**. See
[compliance](compliance_matrix.md) and [limitations](limitations.md).
