# Assessment component research and comparison

**Historical research record; development is frozen.** Current evaluator-facing
architecture/status are in [architecture](ARCHITECTURE.md), [validation](BENCHMARK_RESULTS.md)
and [compliance](ASSIGNMENT_COMPLIANCE.md). Earlier next-step instructions below
are superseded. Original private bytes are retained locally; published copies have separate hashes.

**Latest local-floor source audit:** [batch032](fixes/032_ROOM_FLOOR_SOURCE_SUPPORT_AUDIT.md)
traces all 6,899 original ceiling-scan depth/confidence pairs for fixed room_2 /
plane 1. The retained 300 frames contain 9,818 accepted local pixels in 92 cells:
29.2154% diagnostic coverage. Stride-8 retains 150 returns in 43 cells: 14.1246%.
Native fusion reproduces the 202,477-point cloud and weights bit-for-bit and
retains all 148 local support voxels/cells. Extraction/calibration/timing match
the originals. All-source accepted coverage is 44.0880% under raw poses;
confidence-2 alone gives 34.9107%. Frame selection and spatial sampling lose
available observations; original absence and fusion loss are not the main cause.
Selected dense confidence-2 coverage is only 20.6258%; pixel unions are not native
fused acceptance or physical accuracy. No production defect or safe adoption is
proven. Keep the 25% guard, production and geometry unchanged; no commit/push.
15/15 exact geometry checks, 82 focused and 390 full tests pass. Local floor/
ceiling remain unavailable; 0.702677 m footprint notch remains unvalidated;
floor-only stays 25/176. RGB registration stays CLOSED and XFeat experimental.
REQ-07/08/25 remain partial; REQ-42 gains source-to-cloud trace evidence.
Next run an isolated full-pixel 2 cm native-fusion floor-support control on the
same 300 frozen frames/poses/planes/polygon, without refitting walls/layout or
changing guards; inspect confidence/repeated-view support before adoption.
[Evidence](results/phase3_room_floor_support_summary.json). Earlier notices are historical.


**Latest observed-ceiling decision trace:** [batch031](fixes/031_OBSERVED_CEILING_DECISION_TRACE.md)
reproduces room_2's native floor/ceiling decisions on the fixed cloud, planes and
cameras. observed_ceiling exits at the missing-local-floor guard and visits zero
ceiling planes. Floor plane 1 has 148 local points in 43 occupied cells: 14.1246%
clipped coverage, below the unchanged 25% guard. 44 planes fail horizontal
alignment, six fail floor camera-height clearance and three fail reference-level
agreement. An above-camera plane already has 3,178 points /89.8986% coverage;
this supplementary inventory does not infer a ceiling height or bypass any guard.
Correct policy rejection; physical floor-support loss remains evidence-limited.
No reproducible production defect or justified parameter change is proven.
Two final native traces repeat byte-for-byte; 15/15 geometry checks, 74 targeted
and 374 full tests pass. Production, geometry and thresholds remain unchanged.
No commit or push. The 0.702677 m footprint notch remains unvalidated; area
stays 9.945719535 m² and ceiling height/evidence stay unavailable. Floor stays
25/176; RGB registration remains CLOSED and XFeat experimental.
REQ-07/08/25 remain partial; no physical or final acceptance is claimed.
Next trace original selected depth/confidence returns for plane 1 in room_2,
comparing the retained stride-8 lattice with other accepted pixels under fixed
calibration/poses to distinguish insufficient observations from sampling loss.
Do not rerun the rejected global stride-4 trial or alter the notch.
[Evidence](results/phase3_observed_ceiling_summary.json). Earlier notices are historical.



**Latest ceiling-boundary sensor audit:** [batch030](fixes/030_CEILING_BOUNDARY_SENSOR_AUDIT.md)
identifies the 0.702677 m change as a floor-plan notch in the ceiling-scan case,
not a ceiling-height change: area 10.477367 -> 9.945720 m². The added residual
horizontal plane joins an existing inner finite segment. Original selected PNGs,
per-frame calibration/raw poses and stride-8 fusion reproduce exactly; current
ceiling layout passes 15/15 exact checks. Local notch returns concentrate below
1.5 m; high-confidence crossing rays above them persist under raw/refined poses.
This supports local surfaces but cannot establish a full-height room perimeter
or validate either footprint without semantic/survey evidence. No reproducible
production defect or safe correction is proven. Keep production/geometry/guards
unchanged and retain the 0.702677 m accuracy warning; ceiling height stays null.
60 targeted /360 full tests pass. No production fix, commit or push.
Floor stays 25/176; RGB registration stays CLOSED and XFeat experimental.
REQ-07/08/10/25 remain partial; no physical or final acceptance is claimed.
Next trace _observed_ceiling rejection reasons for current room_2 with existing
cloud/planes/cameras, keeping geometry and thresholds fixed.
[Evidence](results/phase3_ceiling_boundary_summary.json). Earlier notices are historical.



**Latest LiDAR floor result:** [batch029](fixes/029_LIDAR_FLOOR_SAMPLING_CONTROL.md)
reproduces the supplied floor baseline exactly (15/15 checks), then evaluates
stride-4 depth sampling with identical 176 frames and frozen sensor poses.
Fused points increase from 116,480 to 360,845; camera coverage rises from 25/176
to 79/176, with one observed polygon and three inferred cells. The accepted
baseline polygon is not preserved in the known common coordinate frame.
Reject a production density change: more inferred coverage does not justify
changed boundaries. Production floor coverage remains 25/176; no new connecting
wall is introduced. 69 targeted /343 full tests pass. No production change,
commit or push; prior evidence and unrelated work are preserved.
REQ-07/10 remain partial. RGB registration is CLOSED and XFeat experimental.
The 0.702677 m ceiling-boundary shift and physical acceptance remain unvalidated.
Next audit original versus shifted ceiling-scan boundary against confident depth
surface/ray evidence; do not reopen registration or infer independent cm accuracy.
[Evidence](results/phase3_lidar_sampling_summary.json). Earlier notices are historical.


**Final registration-chain status: CLOSED, inconclusive.**
[Batch028](fixes/028_FINAL_FRAME31_REPLAY.md) replays frame31 once from snapshot26.
The input model state reproduces exactly, with unchanged RGB/frontend rows and
fixed intrinsics, but the control ends30 views/6045 points versus snapshot27's
30/6055 and emits37 solver warnings versus0 in the original frame31 interval.
Exact output reproduction fails; intermediate geometry must not be interpreted.
The34/37 landmarks remain first observable in trusted snapshot27 after frame31
registration/refinement. The new run cannot localize their original substage.
Prior inherited-model-bias evidence remains a hypothesis, not a proven defect.
Do not replay earlier frames or extend this diagnostic chain. Keep XFeat
experimental, production SIFT/guards unchanged.144 targeted /326 full tests pass;
1329 prior pinned entries remain intact. No production fix, commit or push.
REQ-03/05/10/27/29 remain partial; floor25/176, ceiling0.702677m shift and physical
acceptance remain unresolved. [Evidence](results/phase3_frame31_final_summary.json).
Earlier next-step notices below are historical and are superseded by this closure.


**Latest registration-support evidence:** [batch027](fixes/027_REGISTRATION_SUPPORT_AUDIT.md)
audits83 visible features /87 distinct candidate rows /37 accepted associations
without running a pose solver. Only1 accepted feature has competing landmark IDs;
accepted source tracks have no repeated-image identities. Their hull covers3.40%
of the target image;28 landmarks have only2 prior views. A systematic1.194292x
native/sensor-reference depth discrepancy persists outside flagged identities;
27->31 input motion already disagrees by4.206027deg and1.318052x normalized length.
Most rejected support is sensor-inconsistent, but two unambiguous rejected wall
observations have3.150/9.808px held-out sensor predictions versus81.737/64.738px
native residuals. Evidence favors inherited geometry bias plus concentrated
support; no concrete solver defect or deterministic production change is proven.
Keep XFeat experimental and SIFT/guards unchanged.129 targeted /311 full tests
pass; both read-only audits repeat exactly and1301 prior entries remain unchanged.
No new commit/push. Floor25/176, ceiling0.702677m shift and physical acceptance
remain unresolved; REQ-03/05/10/27/29 stay partial. [Evidence](results/phase3_registration_support_summary.json).
34 of37 accepted landmarks first appear at frame31's snapshot27. Next replay
frame31 from29-view snapshot26, capturing registration/triangulation before local
and global refinement and requiring snapshot27 reproduction. Sensor poses remain
post-hoc only. Earlier notices are historical checkpoints.


**Latest pre-local-refinement evidence:** [batch026](fixes/026_NATIVE_REGISTRATION_STAGE.md)
resumes frame34 from the saved30-view state twice, without sensor poses or any
frontend/guard changes. Accepted registration already disagrees with odometry
by7.842073deg; triangulation preserves poses; local refinement reduces disagreement
to6.590696deg and reproduces the retained31-view model state exactly. Four native
binaries match; every image record byte matches with output order alone different.
All five stage binaries and audited metrics repeat exactly between controls.
No concrete software defect or production fix is established; keep XFeat
experimental and SIFT unchanged.116 targeted /298 full tests pass;1147 prior
pinned entries remain unchanged. No new commit/push. Floor25/176 and ceiling
0.702677m shift remain unresolved; REQ-03/05/10/27/29 and physical acceptance stay
partial. [Evidence](results/phase3_registration_stage_summary.json). Next audit
83 visible frame34 registration candidates /37 accepted observations against
saved30-view landmark geometry, retaining the native solver and post-hoc sensors.
Earlier notices are historical checkpoints.


**Latest stage-history evidence:** [batch025](fixes/025_NATIVE_REGISTRATION_SNAPSHOTS.md)
replays the same32-view mapping with only native snapshot output enabled. Both
final models and all30 intermediate models reproduce exactly.31->34 disagreement
already measures6.590696deg after frame34 registration/local refinement, becomes
6.272886deg after frame37, and ends6.520814deg. No global refinement occurs in the
first joint interval. Raw PnP versus immediate local refinement remains unresolved;
no production fix or matcher adoption is justified.99 targeted /281 full tests pass.
Native timing source is checked once; prior reviewed alternatives/matcher research is reused.
Next isolate the pre-local-refinement registration pose with native stage replay,
requiring reproduction of the saved post-refinement state before interpreting it.
Earlier next-step notices below are historical. Floor/ceiling/physical holds remain.

Purpose: preserve the read-only research from the side conversation as a reference for later engineering decisions. Refer to this document alongside the assessment, current code, latest validation evidence, and approved implementation roadmap.

**The strongest direction is to preserve the existing validation and geometry safeguards, then evaluate alternatives at specific bottlenecks.** Close-fit projects worth investigating include **XFeat, LIMAP, MapAnything, PolyLayout, and RTAB-Map**, but none of the inspected projects delivers the entire assessment by itself.

## Scope, evidence, and limitations

**Subsequent measured evidence (not part of the original read-only research):**
[Batch 024](fixes/024_LATE_LANDMARK_SUPPORT_AUDIT.md) audits saved31->34 support,
without inference or guard changes.97 shared landmarks have adequate parallax
and zero native identity collisions;96 are direct verified associations.82 have
only late31/34/37 observations; just15 extend earlier. Frame34 has21 earlier-
connected points over3.35% of the image. Seven local cycle conflicts do not
isolate the sensor disagreement; unflagged rows also disagree. Weak temporal
anchoring/structural ambiguity is the strongest hypothesis, not a proven mapper
defect. Exact read-only repeats;88 targeted /270 full tests pass. **Keep XFeat
experimental and SIFT unchanged.** Next collect native per-registration snapshots
to locate the missing registration/adjustment history, rather than pruning tracks
or rerunning matcher alternatives. Earlier notices are historical checkpoints.

[Batch 023](fixes/023_MAPPING_ONLY_FIXED_INTRINSICS.md) completes the mapping-only
ablation: all original 496 two-view rows (236 positive) remain exact, with no
matching or verification rerun and no sensor poses. Fixed calibration alone
recovers 32 views and reduces 24->27 rotation/direction disagreement to
4.319124/9.482126 deg; length ratio 1.035232. This establishes a mapping calibration
contribution independently of changed inlier selection. Late orientation still
reaches 16.690768 deg, direction p95 worsens versus batch022, and 52 solver
warnings/raw conflicts remain. **Keep XFeat experimental; retain production SIFT.**
81 targeted / 263 full tests pass; no production change or commit. Next audit
saved 31->34 landmark identity/parallax support for its 6.520814 deg orientation
error. Earlier notices below are historical checkpoints, not pending reruns.

[Batch 022](fixes/022_FIXED_INTRINSICS_CONTROL.md) reuses retained XFeat candidates
with supplied per-frame intrinsics fixed and all sensor poses withheld. Exact
fresh repeats register 32 views; 24->27 rotation/direction disagreement improves
24.77/34.60 -> 5.20/10.24 deg and relative length ratio 1.496 -> 1.080. Focal
collapse disappears, but later frame-37 orientation error reaches 18.71 deg and
track conflicts/solver warnings persist. **Keep XFeat experimental and SIFT in
production.** 249 full tests pass. Calibration-dependent verification changes
60 inlier-count rows, so next isolate mapping effects with original verified
inliers held fixed. This is a new causal question, not another matcher rerun.

[Batch 021](fixes/021_TRANSITION_ODOMETRY_AUDIT.md) audits the saved 29-view model
with sensor poses withheld from inference. Exact RGB pixel witnesses establish
the playback index +1 sensor mapping. Across frames 24->27 relative rotation
disagrees by 24.77 deg, translation direction by 34.60 deg, and relative length
by 1.496x versus the pre-transition reference. Agreement worsens at frame 28.
The late focal collapse accompanies the disagreement, but causation is untested.
**Reject this joint geometry for production; retain SIFT.** Two audits are exact;
232 full regression tests pass. Next test a bounded intrinsics-only remapping
control, without sensor poses. This is sensor evidence, not physical ground truth.

[batch 020](fixes/020_XFEAT_LIGHTERGLUE_CONTEXT.md) runs pinned XFeat/LighterGlue
twice on the retained 32 RGBs with unchanged downstream guards. It recovers an
exactly repeatable 29-view joint camera model faster than the retained DISK trial,
but large raw track conflicts, 24.80% triangle contradictions, no native
group-spanning point and solver warnings prevent production adoption. The next
question is sensor-consistent joint pose geometry, using existing timing evidence
and withholding odometry from inference. This does not demonstrate physical
accuracy. Original shortlist rankings below remain research hypotheses.

- The research session made no file changes, installations, commits, or pushes and ran no reconstruction experiments. This Markdown file was subsequently created at the user's explicit request to preserve the research.
- Fresh retrieval of Reference Repositories A and B failed. Their findings below come from the current repository's recorded source reviews at pinned revisions, rather than a fresh executable audit.
- Public-project recommendations are based on documentation and selected source inspection. They are **candidates to benchmark, not demonstrated replacements**.
- This is a broad, targeted survey, not an exhaustive inventory of every public repository.
- Recorded baseline results are historical evidence at the time of research. Re-check current artifacts before making a decision; newer verified results supersede this snapshot.
- This document does not authorize implementation, change acceptance criteria, or establish assessment acceptance.
- Distinguish software implementation, internal consistency, sensor agreement, independent dimensional accuracy, and full assessment acceptance.

## 1. What the assignment actually demands

The source is [Applied AI.html](<Applied AI.html>). Its scope is substantially broader than producing a plausible floor-plan image.

| Area | Explicit assessment requirement |
|---|---|
| Photos | **2–8 RGB stills per room**, without supplied depth or poses; automatically produce a stitched whole-property plan. |
| Video | Handheld walkthrough on an iPhone 15+. Unlike photos, the document does not explicitly prohibit genuinely captured poses or IMU. |
| LiDAR | Pro-device depth, poses, and intrinsics. |
| Geometry | Per-room walls, ceiling height, floor area, openings, and correct property adjacency. |
| Measurements | Opening widths within **2 cm on at least 85%**; missed and phantom openings count as failures. |
| Ceiling | Within **1.5 cm per room**, with repeat spread at most **1 cm**. |
| RGB accuracy | Photo walls within **±8%**; video walls within **±3%**; photo property footprint within **±8%**. |
| Repeatability | Per-wall repeat spread within **1 cm or 0.5%**; at least one independent second capture. |
| Drift | Actual correction and a correction-on/off footprint ablation. Using supplied poses unchanged is insufficient. |
| Damage | Surface-linked damage class and metric extent, concealed-damage flags with fired rules, and surface-keyed scope items. |
| Uncertainty | Confidence intervals for every measurement, with calibration demonstrated across tiers. |
| Benchmark | Same property across all tiers: **three rooms plus a connector**, furnished staged damage involving two classes, and independent measurements. |
| Consumer comparison | Two LiDAR rooms; beat or tie the named consumer app on at least **70% of shared dimensions**. |
| Fix Loop | A predeclared worst measured gate, shipped fix, and reproducible before/after evidence. |
| Delivery | One command, published-schema JSON, rendered plan, reproduction bundle, and clean-machine fresh result in **under 15 minutes**. |
| Walk-in | Unseen space and examiner's phone/machine, following the literal capture protocol. |

Two distinctions should guide every library decision:

- **Metric depth does not establish centimetre accuracy.**
- **More matches, more reconstructed points, or more covered camera positions do not establish correct dimensions.**

The HTML also references Round 1 definitions and a published schema that it does not contain. The local schema and gates remain provisional where those official definitions are unavailable.

The assessment defines success; the practical Windows/CPU baseline comes from existing project decisions and should not be confused with an explicit universal hardware requirement in the assessment.

## 2. What the current implementation already does well

The strongest components distinguish supported reconstruction from plausible completion.

| Existing component | Strength worth preserving |
|---|---|
| [capture_sync.py](../floorplan/capture_sync.py) and [ingest.py](../floorplan/ingest.py) | Frame identity, timing checks, per-frame calibration, and explicit exclusion of unavailable observations. |
| [sfm.py](../floorplan/sfm.py), reconstruct_rgb | Existing COLMAP integration, reproducible settings, geometric diagnostics, and honest partial-registration outcomes. |
| [mapping.py](../floorplan/mapping.py), optimize_poses | Verified ICP/loop constraints, bounded corrections, and separation of raw pose priors from verified constraints. |
| [stitching.py](../floorplan/stitching.py), stitch_runs, and [pose_graph.py](../floorplan/pose_graph.py) | Visual overlap verification, ICP refinement, cycle consistency, disconnected-component reporting, and room-identity checks. |
| [layout.py](../floorplan/layout.py), extract_layout | Finite wall support, bounded junctions, observed floor/ceiling evidence, traversal checks, and explicit inferred-boundary status. |
| [openings.py](../floorplan/openings.py), detect_wall_openings | Multiple-view and structural evidence rather than interpreting every missing-depth region as a doorway. |
| [damage.py](../floorplan/damage.py), merge_surface_regions | Surface-coordinate fusion, repeated-view deduplication, shared-wall face handling, and evidence-linked inspection rules. |
| [uncertainty.py](../floorplan/uncertainty.py), fit_calibration | Property-level calibration scores, disjoint development/calibration/audit sets, producer fingerprints, and explicit insufficient-data outcomes. |

The architecture is suitable for selective improvements. There is no demonstrated reason to replace it wholesale.

### Recorded failures that alternatives must address

These are **existing recorded results**, not tests rerun in the research session.

| Bottleneck | Recorded evidence | Implication |
|---|---|---|
| RGB video connectivity | Baseline: **68 views, 139 verified pairs**, eight nontrivial components and eight isolated views; selected model **10/68**. | Correspondences and verified pairs are not yielding a complete reconstruction. |
| Denser video sampling | 8 Hz trial: **78 views / 169 pairs**; 16 Hz: **88 / 222**. Both produced **zero target-group connections**. | Increasing sampling density alone did not solve the transition. |
| Low-detail transition | Failing native SIFT transitions retained **4–14 candidates**, below the existing minimum of 15. | An alternative correspondence frontend is justified as an experiment. |
| Floor completeness | **25/176 camera samples** covered by accepted floor polygons; 151 uncovered. | This is a camera-position coverage diagnostic, not a measured floor-area accuracy percentage. |
| Ceiling boundary | Coverage increased to **295/300**, but one boundary moved **0.702677 m**. | The geometry change remains unvalidated; coverage improvement cannot certify it. |
| Learned metric depth | Recorded MoGe trial against available sensor depth showed substantial discrepancies. | Learned scale should remain an explicitly experimental proposal. |
| Damage | Colour/morphology candidates require review. | Surface projection exists; reliable damage classification remains insufficiently validated. |

The latest recorded regression result at this snapshot is **182 passing tests**. That supports regression stability, not physical assessment acceptance. Evidence: [PHASE3_IMPLEMENTATION_STATUS.md](PHASE3_IMPLEMENTATION_STATUS.md).

Do not treat the pending DISK+LightGlue transition experiment as a successful result unless later retained evidence establishes that outcome.

## 3. Supplied dataset: useful, with important limits

The research checked the local file inventory and frame identities under [Given_dataset](../datasets/Given_dataset).

| Case | Depth files | Confidence files | Odometry rows | Available matching depth/confidence identities |
|---|---:|---:|---:|---:|
| single_room | 1,715 | 1,715 | 1,715 | 1,715 |
| single_scan_floor_only | 5,251 | 5,251 | 5,251 | 5,251 |
| single_scan_with_ceiling | 6,899 | 9,745 | 9,745 | 6,899 |

The ceiling case has **2,846 confidence identities without corresponding local depth files**. Existing reports already log and exclude these unpaired observations; this is not a newly discovered reconstruction defect.

The official StrayScanner format describes 256×192 depth in millimetres, confidence levels 0/1/2, metric poses, and per-frame intrinsics. Its standalone camera matrix represents the final frame, so per-frame calibration matters. [StrayScanner format](https://github.com/strayrobots/scanner/blob/main/docs/format.md)

### What the dataset can exercise

- Synchronization and calibration handling.
- Depth/confidence extraction and missing-frame handling.
- Tracking, registration, and drift correction.
- Wall/floor/ceiling support and reconstruction completeness.
- Cross-view depth consistency and free-space contradictions.
- RGB-only experiments with sensor sidecars withheld.

### What it cannot independently establish

- Laser/tape dimensional accuracy.
- The required same-property three-tier physical benchmark.
- Independent repeatability without verified capture identities.
- Damage-class and extent accuracy without annotations.
- Consumer-app superiority.
- Calibrated deployment intervals from adequate independent properties.

Agreement with its LiDAR is useful development evidence; it is not independent survey truth. Case names and timestamps alone do not establish that the three cases are the same property or independent repeats.

## 4. Open-source options relevant to the actual problems

License notes describe inspected project terms. **Code, checkpoints, datasets, and bundled dependencies can have different terms.** Re-check the selected revision and artifact before integration.

### A. Correspondences, low-texture reconstruction, and video

| Project | Useful part | Fit and limitations | Recommendation |
|---|---|---|---|
| [COLMAP / PyCOLMAP](https://github.com/colmap/colmap) | Geometric verification, SfM, bundle adjustment, MVS. | Already integrated; established foundation. Monocular reconstruction alone does not determine absolute scale. | **Keep as baseline.** |
| [LightGlue](https://github.com/cvg/LightGlue) | Learned matching with DISK, ALIKED, SIFT, and other features. | Small frontend substitution is possible. Code/LightGlue weights are Apache-2.0; feature-model terms differ. More matches need downstream verification. | Evaluate the retained transition experiment before adoption. |
| [XFeat / LighterGlue](https://github.com/verlab/accelerated_features) | Lightweight sparse/semi-dense features and matching. | Particularly relevant to Windows/CPU constraints. Official CPU results are promising, but local throughput and transition success are unmeasured. Apache-2.0 repository. | **Highest-value additional CPU matcher candidate.** |
| [HLoc](https://github.com/cvg/Hierarchical-Localization) | Modular extraction, matching, retrieval, and COLMAP integration. | Useful adapter patterns; little reason to replace the entire orchestration. | Study/import only the needed frontend idea. |
| [LoFTR](https://github.com/zju3dv/LoFTR) | Detector-free correspondence generation. | Relevant if sparse keypoint detection is the bottleneck; runtime and repetitive planar matches require care. | Second-line correspondence experiment. |
| [LIMAP](https://github.com/cvg/limap) | Point–line–plane reconstruction and hybrid SfM. | Strong fit for structural interiors. Current documentation describes COLMAP-compatible output and Windows support. BSD-3-Clause core; frontend extras add dependencies. | **High-value structural reconstruction alternative.** |
| [DeepLSD](https://github.com/cvg/DeepLSD) | Line detection/refinement. | Useful for wall junctions and opening edges. MIT code/models; full refinement adds native dependencies. | Targeted line proposals, not standalone reconstruction. |
| [GlueStick](https://github.com/cvg/GlueStick) | Joint point-and-line matching. | Relevant conceptually; official implementation uses a noncommercial SuperPoint backbone despite MIT wrapper code. | Study or use only under appropriate terms. |
| [VidMap](https://github.com/cvg/vidmap) | Temporal tracks, loop closures, metric-depth priors, global video mapping. | Closely matches plain-video reconstruction. Current setup is Linux/NVIDIA-oriented, source-built COLMAP, and approximately **9 GB** of checkpoints. | Strong algorithmic reference; costly near-term dependency. |

For XFeat, the research inspected [XFeat.detectAndCompute, match_xfeat, and match_lighterglue](https://github.com/verlab/accelerated_features/blob/main/modules/xfeat.py). They expose keypoints and match indices suitable for an adapter into existing verification. **Its 64-dimensional descriptors should not be passed through a path that assumes native SIFT descriptors.**

For LIMAP, a compiled core wheel is not the complete reconstruction pipeline: its documented image frontend still needs additional components. This lowers its priority relative to a bounded matcher trial, despite its strong structural fit.

### B. Learned multi-view geometry and metric proposals

| Project | What it offers | Relevant limitation | Decision |
|---|---|---|---|
| [MapAnything](https://github.com/facebookresearch/map-anything) | Joint metric geometry from images, optionally conditioned on intrinsics, poses, and depth; COLMAP export. | CPU inference path is documented, but practical Windows/CPU runtime is unverified. Metric predictions still need independent measurement validation. | **Strongest broad learned-backend candidate to test.** |
| [Depth Anything 3](https://github.com/ByteDance-Seed/Depth-Anything-3) | Multi-view geometry with or without poses; separate metric and relative-depth variants. | Small/Base multi-view models are not equivalent to its metric-depth model. Checkpoint terms vary. | Worth comparing against the existing learned-depth approach. |
| [VGGT](https://github.com/facebookresearch/vggt) | Joint cameras, depth, point maps, tracks; COLMAP export and optional bundle adjustment. | Practical GPU/memory considerations. Commercial-friendly checkpoint differs from the original restricted checkpoint. | Optional learned initialization benchmark. |
| [Pi3 / Pi3X](https://github.com/yyfz/Pi3) | Joint geometry; Pi3X supports optional geometric conditioning and approximate metric scale. | BSD code, noncommercial weights; approximate scale is not survey accuracy. | Research candidate with explicit checkpoint constraints. |
| [MoGe 2 / MoGe 3](https://github.com/microsoft/MoGe) | Monocular metric geometry, normals, focal information. | Existing MoGe 2 experiments have not validated the required accuracy. MoGe 3 adds Triton/FlexGEMM dependencies. | Preserve the pinned MoGe 2 experiment; avoid blind upgrades. |
| [DUSt3R](https://github.com/naver/dust3r) / [MASt3R](https://github.com/naver/mast3r) | Learned pair geometry, matching, alignment. | Restricted terms and substantial learned-model runtime; no guaranteed absolute dimensional accuracy. | Useful comparative references. |
| [Fast3R](https://github.com/facebookresearch/fast3r) | Feed-forward multiview reconstruction. | Less direct fit to the immediate CPU and sparse-photo constraints. | Lower priority. |
| [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2) | Relative depth, with distinct metric models. | Existing trials did not establish needed measurement quality. | Keep experimental; do not replace sensor geometry by default. |
| [Depth Pro](https://github.com/apple-aiml-research/ml-depth-pro) | Monocular metric depth and focal estimation. | Custom terms, runtime, and indoor measurement bias need evaluation. | Secondary monocular comparator. |
| [PromptDA](https://github.com/DepthAnything/PromptDA) | RGB-guided refinement of low-resolution depth; explicit StrayScanner workflow. | Requires depth input, so belongs to LiDAR—not strict photos or RGB-only video. Sharper edges may still be displaced. | **Relevant LiDAR/opening refinement experiment.** |

MapAnything is particularly interesting because its [infer API](https://github.com/facebookresearch/map-anything/blob/main/mapanything/models/mapanything/model.py) explicitly controls whether calibration, depth, and poses are used. That supports separate, auditable tier experiments. Its Apache-licensed checkpoint is distinct from the default noncommercial checkpoint.

A model-exported COLMAP file does not automatically establish verified feature tracks or safe property connectivity. Those still require evaluation.

### C. Floor boundaries, room topology, walls, and ceiling

| Project | Input → output | Fit to the assignment | Decision |
|---|---|---|---|
| [PolyLayout](https://github.com/ghanning/PolyLayout) | **Posed perspective images → jointly optimized multiroom layouts.** | One of the closest task matches found. Requires poses; assumes Manhattan structure. | **Highest-value direct layout candidate.** |
| [PixCuboid](https://github.com/ghanning/PixCuboid) | Posed multiview images → cuboid room layout. | Useful simpler comparator, but cuboid assumptions are restrictive. | Controlled baseline, not general property replacement. |
| [RoomFormer](https://github.com/ywyue/RoomFormer) | Point-cloud density map → multiple room polygons; semantic extensions. | Fits geometry extraction after reconstruction. Official environment uses Linux/CUDA and compiled operators. | Parallel polygon-proposal benchmark. |
| [PolyRoom](https://github.com/3dv-casia/PolyRoom) | Point-cloud-derived input → room polygons/topology. | Targets missing corners, overlaps, and polygon structure. Adds RoomFormer/MMDetection integration complexity. | Compare only if simpler geometry approaches remain insufficient. |
| [Floor-SP](https://github.com/woodfrog/floor-sp) | Structured floor-plan reconstruction with roomwise shortest-path optimization. | Useful objective formulation for boundary selection. | Algorithmic reference for supported closure. |
| [FloorNet](https://github.com/art-programmer/FloorNet) | RGB/point-cloud/density processing → floor plan. | Relevant historically; older dependency stack increases integration cost. | Lower-priority reference. |
| [HorizonNet](https://github.com/sunset1995/HorizonNet) | Equirectangular panorama → room layout. | Input differs from native perspective photos; scale assumptions need attention. | Only for an explicitly supported panorama experiment. |
| [HouseLayout3D / MultiFloor3D](https://houselayout3d.github.io/) | Structural layout benchmark and training-free reconstruction baseline. | Valuable walls/floors/ceilings/openings reference; raw-data rights and available code need separate checking. | Prioritize benchmark and pipeline study. |
| [Apple RoomPlan](https://developer.apple.com/augmented-reality/roomplan/) | Live LiDAR-assisted capture → structured room geometry. | Proprietary SDK; relevant to Pro capture/consumer comparison, not offline all-tier reconstruction. | Optional route/comparator, not universal solution. |

**PolyLayout deserves a closer experiment than generic monocular depth alone.** Its source exports room layouts, and its configuration jointly optimizes rooms with shared floor and ceiling constraints. The runner includes a CPU selection path, although local environment/runtime remains untested. [Runner](https://github.com/ghanning/PolyLayout/blob/main/pixloc/run_PolyLayout.py), [configuration](https://github.com/ghanning/PolyLayout/blob/main/pixloc/pixlib/configs/eval_polylayout_scannetpp.yaml)

Its shared-height assumptions must be checked against actual rooms. They should not erase a genuine ceiling-height difference.

RoomFormer and PolyRoom produce **proposals**. Raster coordinates must retain their metric transform, and final dimensions should be refined against original observations. For example, an 8 m span represented by 256 pixels has approximately **3.1 cm per pixel**; direct pixel snapping cannot establish the opening-width gate.

### D. LiDAR fusion, registration, and capture

| Option | Relevant benefit | Recommendation |
|---|---|---|
| [Open3D TSDF integration](https://www.open3d.org/docs/release/tutorial/pipelines/rgbd_integration.html) | Combines posed depth observations into a surface representation; already within the dependency ecosystem. | Compare as a bounded fusion backend if noise/fragmentation is demonstrated. Preserve raw support and unknown-space distinctions. |
| [TEASER++](https://github.com/MIT-SPARK/TEASER-plusplus) | Robust registration with outlier-heavy 3D correspondences. | Consider only when registration outliers are measured. It cannot identify the correct room from ambiguous repeated geometry. |
| [RTAB-Map](https://github.com/introlab/rtabmap) | Graph-based mapping, loop closure, multisession support, ARKit capture. | **Investigate as a stock capture route and independent mapping comparator.** |
| [ORB-SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3) | Visual, RGB-D, and visual-inertial SLAM. | Relevant conceptually; GPL/native integration cost and sensor synchronization reduce immediate fit. |
| [DROID-SLAM](https://github.com/princeton-vl/DROID-SLAM) / [DPVO](https://github.com/princeton-vl/DPVO) | Learned video tracking/odometry. | Optional GPU comparators; neither supplies the complete measured floor-plan contract. |
| [StrayScanner](https://github.com/strayrobots/scanner) | Raw phone RGB/depth/confidence/calibration/pose capture. | Preserve the current adapter and synchronization work. |

RTAB-Map's maintainer confirms that ARKit odometry is used **with or without LiDAR**; without LiDAR, tracked visual features are supplied. The app advertises raw ARKit recording and database export. [Maintainer explanation](https://github.com/introlab/rtabmap/discussions/1155), [official app listing](https://apps.apple.com/us/app/rtab-map-3d-lidar-scanner/id1564774365)

This could materially improve **future video inputs**, subject to validating the actual base-iPhone export and protocol. It would be a capture-route improvement—not evidence that the existing MP4-only reconstruction was fixed.

### E. Openings, damage, and uncertainty

| Project | Useful role | What it does not establish |
|---|---|---|
| [Grounding DINO](https://github.com/IDEA-Research/GroundingDINO) | Door/window and descriptive-region proposals. | Centimetre jamb locations, validated damage diagnosis, or metric extent. |
| [SAM 2](https://github.com/facebookresearch/sam2) | Segmentation and video mask propagation. | Damage class, concealed moisture, or measurement calibration. |
| [Grounded SAM 2](https://github.com/IDEA-Research/Grounded-SAM-2) | Detection plus mask proposals. | A validated restoration damage assessor. |
| [CVAT](https://github.com/cvat-ai/cvat) | Annotation of damage/openings and held-out evaluation data. | Independent physical dimensions unless collected separately. |
| [MAPIE](https://github.com/scikit-learn-contrib/MAPIE) | Conformal uncertainty tooling and risk-control methods. | Missing calibration properties or valid assumptions automatically. |

The most useful combination is **semantic proposals + the existing metric surface projection and fusion**.

The opening detector explicitly lacks closed-door appearance detection. Semantic proposals could address that recall gap, followed by structural edge refinement and dimensional verification.

For damage, replacing the colour/morphology frontend is more justified than replacing surface fusion. The current code already prevents repeated views from multiplying damage quantity. A SAM mask must be projected onto a supported surface; image pixel count is not damage area in square metres.

Property-grouped calibration should remain. An off-the-shelf interval library should not downgrade it to treating correlated walls as independent observations.

## 5. Current code versus A, B, and public alternatives

Reference comparisons below use the recorded pinned reviews:

- [comparative source](https://github.com/Vatsalya001/cozmo-ai-assignment): **d5105858440bdb549626845948bc51da8a8b9f02**.
- [comparative source](https://github.com/kush07upadhyay/Cozmo_AI_Assignment): **c9dfacbed60ddb6554a7c9b6721696dfb748013a**.

Evidence: [OPEN_SOURCE_DECISIONS.md](OPEN_SOURCE_DECISIONS.md) and [PHASE3_REMAINING_PASS.md](PHASE3_REMAINING_PASS.md). These are recorded source-review findings, not freshly verified execution or comparative benchmarks.

| Component | Current implementation | Recorded reviewed alternatives approaches | Public alternatives | Research decision |
|---|---|---|---|---|
| Strict photos | SfM plus experimental metric geometry and verified roomwise registration; incomplete. | A lacks actual SfM/autostitch in its photo path. B assumes camera height/levelness. | MapAnything, DA3, VGGT, LIMAP. | **Public alternatives offer more relevant hypotheses than reviewed alternatives photo shortcuts.** |
| Video | MP4-derived SfM; transition connectivity failure measured. | A requires external poses. B uses VIO and per-frame calibration. | XFeat, LightGlue, VidMap, RTAB-Map capture. | Compare matchers for existing MP4; separately evaluate genuine posed-video capture. |
| LiDAR ingestion | Per-frame calibration and explicit synchronized identity handling. | Recorded proportional/index-based assumptions are weaker. | StrayScanner format. | Preserve the existing approach. |
| Wall candidates | Raw-supported finite plane/segment pipeline. | A: height-band density/Hough; B: projection-mode wall candidates. | Open3D, structural line proposals. | Useful reviewed alternatives ideas are already represented in bounded experiments; no whole-module replacement justified. |
| Room boundaries | Bounded joins; inferred geometry flagged. | A erosion/watershed; B bounding-pair/raw-extent fallback. | PolyLayout, RoomFormer, PolyRoom, Floor-SP. | Evaluate proposals, retain support verification; reject unsupported rectangles. |
| Ceiling | Observation-based measurement. | A height histogram is useful; fixed fallback heights are unsuitable. | Plane fitting, PolyLayout joint constraints. | Preserve observed-height policy; independently resolve the boundary shift. |
| Stitching | Visual verification, ICP, cycles, room identities. | A raster registration is ambiguous in repetitive rooms. B requires connectors and lacks equivalent cycle closure. | HLoc/LIMAP frontends, TEASER++ where justified. | Preserve the graph; improve legitimate constraints upstream. |
| Openings | Conservative structural/multiview detector. | A coverage necks; B empty runs/edge refinement. | Grounding DINO + SAM + raw geometric refinement. | Expand proposal recall without treating holes as proof. |
| Damage | Weak candidate classifier, stronger metric fusion. | B surface-linked scope is useful; automatic remediation from candidates is unsupported. | Segmentation and annotation tooling. | Improve classification; keep fusion and explicit rules. |
| Calibration | Independent-property conformal path. | Fixed bias/error bars cannot demonstrate calibrated coverage. | MAPIE cross-check. | Preserve the approach; acquire adequate independent evidence. |
| Reproduction | Ledgers, fingerprints, explicit failures. | A's artifact accounting is useful; local symlinks do not prove a clean-machine run. | Existing packaging/tooling. | Complete actual cold-run evidence; no architecture rewrite. |

**Neither reference repository is a demonstrated overall winner.** Their useful contributions are specific proposal-generation and capture ideas; several apparent simplifications would weaken assessment compliance.

### Recorded reference code locations for follow-up review

These pointers support later inspection; their names and conclusions come from the local pinned reviews.

| Repository | File/function | Useful idea or limitation |
|---|---|---|
| Alternative 1 | scanplan/geometry/walls.py: density, wall_mask, dominant_orientations | Height-band density/Hough candidates; verify against raw finite 3D support. |
| Alternative 1 | scanplan/geometry/planes.py | Height-histogram floor/ceiling proposals; reject a fixed ceiling fallback as a measurement. |
| Alternative 1 | scanplan/geometry/rooms.py: split_rooms, openings | Erosion/watershed and coverage-neck proposals; insufficient alone for measured opening evidence. |
| Alternative 1 | scanplan/ingest/photos.py, ingest/video.py, geometry/register.py | Photo path does not provide strict SfM/autostitch; video external poses require actual admissible capture; repetitive-room raster alignment needs verification. |
| Alternative 1 | bench/clean_clone_check.sh | Artifact accounting is useful; local dataset links do not establish clean-machine reproduction. |
| Alternative 2 | cozmoscan/geometry/manhattan_room.py: _pick_bounding_pair, _detect_openings | Projection modes/edge proposals may help; raw-extent rectangles and empty runs are not sufficient evidence. |
| Alternative 2 | cozmoscan/capture/photo_tier.py, video_tier.py | Assumed photo camera height/levelness is unsuitable; genuine video VIO and per-frame calibration can be useful. |
| Alternative 2 | cozmoscan/geometry/stitching.py | Connector dependence and missing equivalent cycle closure do not justify replacing the current graph. |
| Alternative 2 | cozmoscan/damage/scope.py | Surface-linked scope is useful; automatic remediation from visual candidates is unsupported. |

## 6. Best datasets for meaningful comparisons

| Dataset | Best use | Important limitation |
|---|---|---|
| **Supplied StrayScanner cases** | First source for synchronization, sensor support, completeness, and RGB ablations. | No independent dimensional survey or verified full benchmark composition. |
| [ARKitScenes](https://github.com/apple/ARKitScenes) | Phone RGB-D and high-quality reference assets, including FARO-related raw assets where available. | Structural truth must be extracted/vetted; not every scan provides every required annotation. |
| [ScanNet++](https://scannetpp.mlsg.cit.tum.de/scannetpp/documentation) | Registered iPhone data and independent laser scans. | Access/data terms, storage, and preprocessing; does not replace assignment physical evidence. |
| [MultiViewRoomLayout](https://github.com/ghanning/MultiViewRoomLayout) | Layout truth, wall recall, IoU, Chamfer, and pixel-wise geometry evaluation; includes multiroom scenes. | Standard tuples often exceed 2–8 views and supply poses. Create compliant photo subsets and withhold poses for strict-photo inference. |
| [Structured3D](https://github.com/bertjiazheng/Structured3D) | Exact synthetic structure, topology, openings, clutter-controlled regressions. | Synthetic success is not physical accuracy. Data terms differ from MIT tooling. |
| [HouseLayout3D](https://houselayout3d.github.io/) | Complex real structural layouts, doors/windows, multifloor stress cases. | Matterport-derived inputs and separate rights; acquisition differs from native phone captures. |
| [TUM RGB-D](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/rgbdslam_eval) | Tracking, trajectory drift, and correction evaluation. | Trajectory truth is not a measured floor-plan/damage benchmark. |

**Best complementary pair:** ScanNet++ for phone/laser geometry, plus MultiViewRoomLayout for explicit structural layout evaluation.

Do not use similarity alignment that rescales predictions when reporting metric acceptance. Scale-aligned geometry can be reported as a separate diagnostic, but it can conceal precisely the scale error being assessed.

## 7. Ranked shortlist for subsequent experiments

This ranking reflects task fit and integration practicality—not measured superiority.

| Rank | Candidate | First question it should answer | Adoption condition |
|---:|---|---|---|
| 1 | **XFeat + LighterGlue**, alongside the existing DISK trial | Can the retained transition produce legitimate additional verified connections on CPU? | Connected target views in a geometrically valid, reproducible model; acceptable runtime. |
| 2 | **LIMAP structural features** | Are wall/junction lines useful where point correspondences fail? | Better pose/reconstruction completeness without false room connections. |
| 3 | **MapAnything Apache checkpoint** | Does joint multiview metric geometry outperform independent learned-depth proposals? | Better held-out geometry/scale results and viable deployment cost. |
| 4 | **PolyLayout** | Can posed RGB observations produce stronger supported room topology? | Improved wall/layout metrics while preserving observed geometry and height differences. |
| 5 | **RTAB-Map capture route** | Can base-iPhone video export genuine RGB, calibration, timestamps, and odometry reproducibly? | Literal stock-app protocol and verified export, followed by measured downstream validation. |
| 6 | **Open3D TSDF** | Is fusion noise/fragmentation losing usable structural support? | Better observed surface estimates, without smoothing away openings or filling unknown regions. |
| 7 | **Grounding DINO/SAM proposals** | Can closed-door/opening recall and damage masks improve? | Held-out detection/extent improvement, with existing metric fusion retained. |
| 8 | **PromptDA** | Can depth-guided refinement improve measured opening edges? | Independent edge/dimension improvement; no unsupported replacement of sensor evidence. |
| 9 | **RoomFormer** | Does point-density layout prediction offer better topology proposals? | Useful gain sufficient to justify its environment/compiled dependency cost. |

VidMap is highly relevant scientifically, but its current setup cost makes it less practical than the first bounded candidates.

## 8. How to decide whether to retain, adapt, or replace a component

Every candidate needs the same evaluation discipline:

1. **Freeze inputs and baseline.** Retain frame identities, input hashes, versions, checkpoints, preprocessing, and evaluator.
2. **Change one meaningful component.** Avoid changing matching, mapping, scale, and layout simultaneously.
3. **Measure the relevant failure.**
4. **Check regressions and reproducibility.**
5. **Compare runtime and cold setup cost.**
6. **Adopt only if the improvement survives the required evidence.**

| Component | Required comparison |
|---|---|
| Matching | Candidates, verified inliers, geometric classifications, target-group connections, components, isolated views, registered views, triangulation and reprojection quality. |
| Metric reconstruction | Raw metric scale error, wall/height errors, cross-view consistency, independent reference-surface error. |
| Boundaries | Wall recall, unsupported edges, false closure, overlaps, room identities, boundary displacement, measured footprint. |
| Stitching | Correct adjacency, false merges, cycle residuals, connector evidence, drift-on/off result. |
| Openings | Missed/phantom count, width errors, jamb/header support, open versus closed-door cases. |
| Damage | Class precision/recall, mask quality, metric extent errors, surface assignment, deduplication. |
| Uncertainty | Held-out coverage, interval width, independent-property splits, backend fingerprints. |
| Delivery | Clean-machine setup plus fresh result, original-input regeneration, failures reported correctly. |

The floor case currently has evidence against inventing the queried connecting wall. A learned layout proposal must not override that measured free-space contradiction merely to close a polygon.

Before any later experiment, verify the current implementation and newest artifacts. The historical minimum of 15 candidates belongs to the current point-matching path; a different structural estimator still requires a justified validation design, not an arbitrary relaxation to force connectivity.

## 9. What should deliberately remain unchanged

- Geometric verification and acceptance guards while comparing matchers.
- Explicit disconnected-model outcomes.
- Finite observed wall support and bounded junction handling.
- Separation of observed and inferred boundaries.
- Per-frame calibration and synchronization checks.
- Cycle consistency and room-identity verification.
- Shared-wall damage visibility and quantity deduplication.
- Truth withheld from inference.
- Property-level calibration and insufficient-data reporting.
- Reproduction ledgers and honest partial/failure status.

Avoid default ceiling heights, assumed photo camera height, raw point-cloud bounding rectangles, manual adjacency hidden inside automation, and concatenating disconnected models. These can produce attractive demonstrations while failing the assignment's measurement requirements.

Generative scene completion is similarly unsuitable as measurement evidence: an invented wall can look architecturally plausible and still be dimensionally wrong.

## 10. Reuse rights and the practical conclusion

Restricted projects were included in the research because their algorithms can be informative. However, **unlicensed is different from permissively licensed**: GitHub states that absence of a license does not grant ordinary reproduction or derivative-work rights. [GitHub licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)

For direct integration, choose compatible code **and** checkpoints, preserve required attribution, and disclose pretrained tools as the assignment requests. Where rights are unsuitable, study the published approach and use a permitted alternative or an independent implementation where appropriate.

**Recommendation:** retain the common pipeline and concentrate comparative experiments on correspondence quality, joint multiview geometry, and supported layout estimation. The most promising additions from this research are XFeat, LIMAP, MapAnything, and PolyLayout; RTAB-Map offers a potentially valuable future video capture route.

The remaining acceptance work still requires independent dimensions, damage annotations, repeat captures, calibrated intervals, consumer exports, and cold-run evidence. No inspected open-source project supplies those on behalf of the submission.

## Related local decision and evidence documents

- [Assessment execution roadmap](ASSESSMENT_EXECUTION_ROADMAP.md)
- [Assignment brief map](ASSIGNMENT_BRIEF_MAP.md)
- [Open-source decisions and actual earlier experiments](OPEN_SOURCE_DECISIONS.md)
- [Phase 3 implementation plan](PHASE3_IMPLEMENTATION_PLAN.md)
- [Phase 3 implementation status](PHASE3_IMPLEMENTATION_STATUS.md)
- [Phase 3 remaining pass](PHASE3_REMAINING_PASS.md)
- [Supplied-data pass](PHASE3_SUPPLIED_DATA_PASS.md)
- [Synchronization and boundary pass](PHASE3_SYNC_BOUNDARY_PASS.md)
- [Dataset readiness](DATASET_READINESS.md)

When using this document later, distinguish **researched option**, **implemented experiment**, **measured improvement**, and **accepted assessment evidence**. Update a conclusion only when new retained evidence supports it.
