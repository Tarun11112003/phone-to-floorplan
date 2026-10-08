# Phase 3 implementation status

**Historical engineering record. Development is closed. Current requirements/status and evaluator commands are in [compliance](ASSIGNMENT_COMPLIANCE.md) and [README](../README.md).

**Historical engineering ledger — superseded by the development freeze.**
See [index](INDEX.md), [architecture](ARCHITECTURE.md), [validation](BENCHMARK_RESULTS.md)
and [compliance](ASSIGNMENT_COMPLIANCE.md) for the final handoff. Recorded results
remain historical evidence; further experiment suggestions are not active work.

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


**Current native stage-history audit:** [batch025](fixes/025_NATIVE_REGISTRATION_SNAPSHOTS.md)
produces30 per-registration snapshots in two unchanged mapping-only controls.
All snapshot binaries/metrics and final baseline binaries/metrics/database rows
repeat exactly.31->34 rotation disagreement is6.590696deg at the first joint
post-registration/local-refinement state,6.272886deg after frame37 and6.520814deg
after final refinement. No global refinement occurs in the first joint interval.
The missing distinction is raw registration versus immediate local refinement;
no concrete mapper bug or production fix is established.99 targeted /281 full
tests pass (44.35s); all800 older evidence hashes and pre-existing production
working-file bytes are unchanged. XFeat remains experimental; SIFT/guards stay.
Three completed backlog milestones were committed as9d75ab6/061625b/8aaca9f;
no push. New diagnostics remain uncommitted. Floor25/176 and ceiling0.702677m
shift remain unresolved; physical acceptance and REQ-03/05/10/27/29 remain partial.
[Evidence](results/phase3_registration_snapshots_summary.json). Next capture the
frame34 native registration pose before local refinement, with stage reproduction.

**Current read-only audit:** [batch024](fixes/024_LATE_LANDMARK_SUPPORT_AUDIT.md)
identifies97 saved31->34 shared landmarks,96 direct verified associations, zero
native identity collisions and median8.475789deg pair parallax.82 landmarks have
only late observations;15 extend earlier. Frame34's21 earlier-connected points
cover3.352610% of the image. Seven local triangle conflicts do not explain the
error uniquely; unflagged rows also disagree with sensor geometry. Strongest
hypothesis: weak earlier anchoring of a locally planar late chain. Exact PnP
inliers/pre-post BA states were not retained;52 warnings belong to the earlier
frame27 stage. No concrete mapper defect, intervention, production change or
commit. **Keep XFeat experimental; preserve SIFT/guards.** All735 prior hash
entries remain unchanged;88 targeted /270 full tests pass (44.67s). Baseline stays
32 views,6187 points,1.480503px and6.520814deg target disagreement. REQ-03/05/10/27/29
remain partial; floor25/176 and ceiling shift0.702677m remain unvalidated holds.
[Evidence](results/phase3_late_landmarks_summary.json). Next observational replay
captures native registration snapshots to locate when the pose error appears.

**Current experiment:** [batch 023](fixes/023_MAPPING_ONLY_FIXED_INTRINSICS.md)
maps the exact original XFeat verified rows with fixed supplied intrinsics,
without matching/re-verification or sensor poses. Two fresh runs reproduce one
32-view/6,187-point model at 1.480503 px residual. 24->27 rotation/direction errors
are 4.319124/9.482126 deg; relative length ratio 1.035232. This is partial geometric
improvement, not connectivity alone. Later frame-37 orientation remains
16.690768 deg; common direction p95 worsens to 39.849600 deg and solver warnings
rise to 52. **Keep XFeat experimental; preserve production SIFT.** Mapping camera
calibration contributes, but no remaining mapper defect is established. All 632
previous pinned hash entries are preserved. **81 targeted / 263 full tests pass
(45.05 s)**. No production change, commit or push. REQ-03/05/10/27/29 remain partial;
floor25/176 and the unvalidated ceiling shift0.702677 m remain unchanged.
[Evidence](results/phase3_mapping_only_summary.json). Next audit saved 31->34
landmark identity/parallax support for its 6.520814 deg orientation error.
Older notices below are historical checkpoints.

**Latest experiment:** [batch 022](fixes/022_FIXED_INTRINSICS_CONTROL.md) fixes
supplied per-frame calibration in an isolated XFeat remapping control, with no
sensor poses. Both fresh controls reproduce one 32-view/6,360-point model and
1.470216 px mean residual exactly. All 32 intrinsic vectors remain exact. The
24->27 sensor rotation/direction errors improve to 5.199806/10.235933 deg, and
relative length ratio to 1.080450. Residual drift at frame 37 reaches 18.706806 deg;
raw track conflicts and 23 solver warnings persist. **Keep XFeat experimental;
retain production SIFT.** Calibration is a contributor, not the entire cause.
Verification/mapping thresholds are unchanged; six intrinsic-policy fields differ
as intended and 60 verified-inlier count rows change under calibrated verification.
Next mapping-only ablation holds the original verified inliers fixed to isolate
that effect. Tests: **67 targeted / 249 full passed (43.68 s)**. 528 old unique
hashes preserved; no production change, commit or push. REQ-03/05/10/27/29 remain
partial; floor 25/176 and unvalidated ceiling shift 0.702677 m remain unchanged.
[Evidence](results/phase3_fixed_intrinsics_summary.json).

**Latest validation:** [batch 021](fixes/021_TRANSITION_ODOMETRY_AUDIT.md) audits
the saved 29-view XFeat model without rerunning inference or importing poses.
All 64 RGB pixel witnesses match; timing uniquely supports playback index +1.
24->27 disagrees with odometry by 24.771982 deg in rotation, 34.595082 deg in
translation direction and 1.496456x in relative displacement magnitude. At
24->28 these become 34.735237 deg, 66.479466 deg and 3.721359x. Classification C:
across-transition geometry is contradicted by sensor evidence. Early local
agreement does not validate the bridge. Late focal collapse is an observed
diagnostic, not a proven cause. **Retain SIFT; candidate stays experimental.**
Two read-only audits are exact excluding runtime; 383 unique old hashes remain
unchanged. Tests: **50 targeted / 232 full passed (64.60 s)**. No production bug,
logic change, completed production milestone, commit or push. Next: isolated
fixed per-frame intrinsics remapping control, still withholding sensor poses.
[Evidence](results/phase3_transition_odometry_summary.json). REQ-03/05/10/27/29
remain partial. Floor 25/176 and unvalidated ceiling shift 0.702677 m are retained.

**Latest frontend experiment:** [batch 020](fixes/020_XFEAT_LIGHTERGLUE_CONTEXT.md)
evaluates pinned Apache-2.0 XFeat/LighterGlue on the same 32 RGBs without changing
production. Two fresh runs reproduce 236 verified pairs, one 29-view joint camera
model, 5,455 points and 1.486099 px mean residual exactly in 396.151/391.438 s.
Raw triangle contradictions rise to 24.80%; no native point track spans the
original groups, and direct group matches provide zero shared saved landmarks.
Both logs retain 149 solver warnings. **Reject production adoption for now.**
44 targeted tests pass; no new full-suite run because production is unchanged.
An interrupted initial trial and stopped quadratic diagnostic are excluded from
completed-repeat evidence. Memoized audit criteria are unchanged. Next audit
joint relative poses against supplied odometry through verified timing mappings.
[Hashed evidence](results/phase3_xfeat_context_summary.json). No commit or push.
Floor 25/176 and unvalidated ceiling displacement 0.702677 m remain unchanged.

**Latest context experiment:** [batch 019](fixes/019_RGB_TRANSITION_CONTEXT.md)
retains all 24 views and adds the eight declared RGB anchors. SIFT grows to an
11-view local model; learned matching produces separate 15/11-view models with
25 unique registered views, but neither produces a joint target-group model.
Both repeats are exact. Learned cross-group edges remain suspicious; its shared
model overlap has only one reconstructed feature. **No production adoption or
commit.** Tests: 33 targeted / 205 full passed (54.96 s). The initial SHM integrity
false alarm is corrected while preserving DB/WAL hashes. Next evaluate the
already researched XFeat + LighterGlue option on these same 32 RGBs.
[Measured evidence](results/phase3_transition_context_summary.json).
Floor 25/176 and unvalidated ceiling displacement 0.702677 m remain unchanged.

**Previous audit:** [batch 018](fixes/018_TRANSITION_TRACK_SAFETY.md) revalidates the
retained 24-view comparison and adds feature-track safety diagnostics. LightGlue
has 978 conflicting tracks versus 36 for SIFT; all four endpoint-spanning tracks
are conflicting and none is clean. Pairwise connectivity does not yield a joint
model. Two fresh diagnostic runs and retained matcher/model repeats are exact.
**Retain SIFT; no production change or commit.** Tests: 26 targeted and 198 full
passed (61.08 s). [Evidence](results/phase3_transition_track_safety_summary.json).
Next remains the bounded 32-view context comparison under unchanged guards.
Floor 25/176 and unvalidated ceiling displacement 0.702677 m remain unchanged.

**Previous matcher checkpoint:** [batch 017](fixes/017_DISK_LIGHTGLUE_TRANSITION.md) compares
the exact retained 24 RGBs using pinned DISK + LightGlue and unchanged downstream
guards. Verified pairs improve 39 → 109, components 3+7 isolates → one 24-view
component, but neither endpoint registers in a joint model. Learned mapping stays
2/24 with 67 points; its native initialization-suitable pair count is zero versus
one for SIFT. Both matcher repeats reproduce feature/database/model contents
exactly. **Do not adopt**: successful 2D matching is insufficient 3D reconstruction.
Production source/geometry bytes are unchanged. Tests: **20 targeted passed;
192 full passed in 53.67 s**. [Hashed results](results/phase3_transition_matcher_summary.json).
Strict RGB and Phase 2 remain incomplete; next evaluate eight existing registered
RGB anchors as a bounded 32-view context trial, without prior optimized poses.
Floor coverage remains 25/176; the 0.702677 m ceiling shift remains unvalidated.

**Previous batch 016 checkpoint:** follow [the assessment execution roadmap](ASSESSMENT_EXECUTION_ROADMAP.md).
The [RGB bridge trial](fixes/016_RGB_VIDEO_BRIDGE_TRIAL.md) is complete: unchanged
guards with ten/twenty additional original views create 30/83 verified pairs,
but neither sampling recipe connects the two target groups or creates a joint
sparse model. Both fresh-database repeats reproduce table contents, components
and binary sparse models exactly. The native matcher audit finds insufficient
local candidates across the failed transition; no production algorithm or
acceptance guard is changed. Strict RGB registration is still incomplete.
Full suite: **182 passed in 58.04 s**; targeted diagnostics: **10 passed in 1.26 s**.
Next test pinned DISK+LightGlue on the retained 24-view transition chain, keeping
COLMAP verification/mapping guards and requiring both endpoints in one model.
See [hashed video results](results/phase3_video_bridge_summary.json). Floor remains
25/176 with 151 uncovered samples; the earlier ceiling shift remains unvalidated.

**Previous batch 015 checkpoint (historical next-step declaration):**
The [lower adjoining-span audit](fixes/015_LOWER_ADJOINING_SPAN_TRACE.md) is complete.
Byte-identical sensor payloads and exact fusion/proposal replay reveal only 29
fused wall-height points and nine residual points, with 132,289 confident depth
rays crossing the query. All raw odometry frames corroborate four crossings.
No solid connecting boundary is justified; no production source was changed.
Floor remains 25/176 covered, with 151 uncovered; ceiling remains 295/300, and
its earlier 0.702677 m boundary shift remains unvalidated. Fresh frozen floor
and ceiling replays each pass 15/15 exact checks. Full regression: **179 passed
in 56.94 s**; corrected targeted run: **23 passed in 30.68 s**.

The next roadmap gap was investigated: RGB video's 139 verified pairs split
into eight nontrivial components plus eight isolated images. Two disjoint models
contain nine and ten views; the selected model remains 10/68. Next execute one
RGB-only bridge-view trial around source times 11.55-13.066667 s before changing
mapping/stitching. [Hashed current evidence](results/phase3_adjoining_span_summary.json).
No whole requirement or physical acceptance gate closes in this diagnostic batch.

**Previous batch 014 checkpoint (historical results and next-step declaration):**
The [per-frame exterior-strip trace](fixes/014_EXTERIOR_STRIP_SENSOR_TRACE.md)
verifies identical raw depth/confidence payloads and exact fusion replay. Thirteen
frames contribute voxels near the residual fitted plane. Original quota truncation
followed by residual-bin dilution is software-addressable; generic original-seed
replay was rejected after a 28.48% prior-cell area loss. The selected bounded retry
only considers original modes outside the represented wall-family span and retains
all plane guards and the existing accepted quota. Floor segments increase 67 → 69,
but coverage stays 25/176 and **151** uncovered samples remain. The updated audit
has **82** incomplete directional-support samples and **65** unbounded finite
enclosures, plus two degenerate and two below the area guard.

Fresh reproduction passes **16/16 cases, 60/60 software checks**, including exact
prior residual-policy replay and preservation of all prior cell corners and
connections on frozen inputs. No extra ceiling boundary change occurs; the
historical 0.7027 m shift is still unvalidated. Single/dense coverage and the
two-room control remain. Four supplied raw runs retain assignment exit 1 and
every assignment contract stays incomplete. See the linked ledger for tests and
hashed metrics. The next task is the lower adjoining span near z=4.44, x=-2.73
to -0.44, before any connector or junction change.
Final serial regression passes **174/174 in 58.08 s**, including rejection when
an original seed has no unexplained support. The earlier 173-pass suite precedes
that added test. [Hashed results](results/phase3_exterior_strip_summary.json)
retain raw-native numeric differences separately from exact frozen controls.

The preceding 171-test audit checkpoint is retained below with its source revision.
The [151-sample floor audit](fixes/013_FLOOR_SAMPLE_WALL_AUDIT.md) precedes
reconstruction changes and reproduces premature accepted-plane quota termination.
The selected bounded residual search retains original proposals and all support
guards. Full regression passes **171/171 in 145.59 s**. Fresh reproduction verifies
**15/15 cases, 45/45 software claims**, including five frozen-input controls and
five exact current-producer artifact replays. Four supplied raw runs retain exit 1
for incomplete assignment contracts; the generated benchmark passes its development
checks but also has an incomplete assignment contract.

Floor segments increase 63 → 67, while its cells and **25/176** coverage remain
unchanged: **151 uncovered samples remain**. The updated audit classifies 94 with
incomplete extracted support, 53 without enclosure inside finite extents, two
degenerate and two below the unchanged area guard. No lost supported junction is
identified. The ceiling gains 147 covered centres, **49.33% → 98.33%**, but stays
partial with 8 observed cells/4 inferred hypotheses and zero adjacency. One prior
observed-cell boundary moves **0.7027 m**; its accuracy impact remains unknown.
Single/dense coverage and generated two-room/one-adjacency control are preserved.
All polygons are valid and nonoverlapping in the saved outputs. Native numerical
camera differences remain recorded, not accepted as repeatability or accuracy.
No whole assessment requirement closes. [Compact hashed evidence](results/phase3_floor_wall_audit_summary.json)
records current metrics. The next technical task is the left exterior strip's
per-frame depth/confidence and residual-seed audit, before further extraction edits.

The preceding mixed-cell checkpoint is retained below with its original producer.
This focused batch fixes mixed observed/partial cell selection: an observed
cell no longer suppresses a separately supported hypothesis. Observed geometry
is retained, inferred cells remain review-only, and inferred edges cannot establish
adjacency. Targeted tests pass **21/21 in 71.01 s**, and final serial regression
passes **166/166 in 115.70 s**. Five fresh sensor/control reconstructions and five
exact artifact replays pass their execution claims. Floor/ceiling camera coverage
increases from 5.11%/29.00% to 14.20%/49.33% through flagged hypotheses; all
supplied geometry remains partial. Four strict raw comparisons fail at numerical
differences up to 7.02e-14 m; their failed inventory is retained (11/15 cases,
41/45 claims). Separately, all five frozen-geometry comparisons pass exactly
with observed walls/cells/adjacency unchanged (20/20 claims). No physical
requirement is closed. See
[the correction record](fixes/012_PARTIAL_CELL_COMPLETENESS.md).

The preceding synchronization/boundary checkpoint is retained below.
Scanner encoded-timeline pairing, local spatial wall support, fragment-height
checks, bounded candidate search, original finite-corner bounds, numerical noding,
RGB pixel-center conversion and exact geometry artifact retention are implemented.
That checkpoint's serial broad suite passes **157 tests in 47.31 s**. The preceding
155-pass/one-failure regression was reproduced and corrected, not waived.
Fresh raw supplied replays and current-source six-case integrations verify
execution but retain incomplete contracts. Open3D/density/semantic alternatives
have not established a complete correct boundary model. RGB sampling reached
4/45 and 10/68 registered views; shared-camera 68-view registration remains 10.
Pose-correction evidence includes auditable sequential ICP graph constraints.
Current-source on/off validation verifies four accepted sequential ICP constraints
and actual pose changes, without measured accuracy improvement. Five unchanged
float64 geometry artifacts now replay exactly after fixing the verifier's JSON
representation comparison; the earlier failed verifier run is retained. The
controlled semantic experiment shows no benefit and is not promoted. Supplied
room identity, physical dimensions and accuracy remain unverified.
See [the current evidence ledger](PHASE3_SYNC_BOUNDARY_PASS.md).
Earlier results below retain their historical producers and do not incorporate
the newly corrected RGB/depth pairing. No new acceptance claim is made.

Updated . The [saved plan](PHASE3_IMPLEMENTATION_PLAN.md) is the agreed
scope; [architecture and decisions](PHASE3_DESIGN.md) describe current paths.
Requirements come from [Applied AI.html](Applied%20AI.html).

The latest [supplied-data pass](PHASE3_SUPPLIED_DATA_PASS.md) continues the
[earlier remaining-gap pass](PHASE3_REMAINING_PASS.md). Historical checkpoint
numbers below refer to their frozen producer revisions.
Previous source: **133 tests passed in 25.63 s** in an isolated copy. The three
supplied sensor replays verify **12/12 declared execution checks** and now yield
one partial room each, with only 34.78%, 10.29% and 8.00% camera coverage.
The supplied RGB-only video registers 2/24 views and yields no closed room.
No supplied result has complete geometry or independent accuracy validation.
The latest ledger also records an overlapping native-workload test failure
(4 failed / 127 passed), followed by the successful serial regression run.
The final-source four-case checkpoint reproduction additionally verifies all
25 claims, preserving the generated two-room/one-adjacency control. Photo and
video regressions still have no closed room; all assignment contracts remain
incomplete. Consult the linked ledger for exact artifacts and timings.

**The assignment is not complete.** This phase adds contract, inference,
validation and evidence machinery. Component tests cannot establish centimetre
accuracy, capture independence or unseen-room readiness. Existing local changes
were preserved; this implementation session has made no commits or pushes.

## Change-by-change checkpoint

| Change | Implemented | Remaining acceptance work |
|---|---|---|
| 01 Common contract | Internal v2 property union footprint/graph, shared physical openings, metric status; canonical/v1/legacy evaluation; finite values/IDs/references/units; provisional rules | Actual published schema/Round 1 definitions; all-tier physical output proof |
| 02 Reliable execution | Strict profile rejects assistance/truth; structured failures; failed assessment cannot report success; completeness blockers; small portable test fixtures | Successful strict assignment output, beyond research proposals |
| 03 CPU deployment | Dependency pins, nondestructive Windows bootstrap, producer/model-checked cache, memory status, OpenMVS budget and two-view fallback | Genuine clean-machine install/live result under 15 minutes; model deployment timing |
| 04 Physical benchmark | Composition/split/photo-count/hash/repeat/consumer-export audit; survey importer preserves direct measurements and hashes raw evidence | Same property all tiers; independent survey, staged damage, repeat, consumer export and calibration/audit properties |
| 05 Capture normalization | Original and normalized photo metadata/orientation, explicit room groups, strict profile; timestamp/selection accounting; video CLI frame budget honored; supplied Stray adapter; generated HEIC smoke check | Actual native HEIC/MOV and current-app golden export; distortion-domain verification |
| 06 Strict RGB | Pinned/checksummed CPU MoGe-2 experiment; camera-conditioned depth, robust multi-view scale, unordered verified registration, explicit model_scaled provenance; serial seeded matching | Experiment unpromoted; native 2/4/8 photos and full-property accuracy/calibration; supplied RGB remains incomplete |
| 07 Walls/ceilings | Fitted-plane residuals/finite lines, bounded intersections; bounded raw-support wall proposals; per-room floor/ceiling cells; origin-invariant ceiling heights and observed slope range | Closed supplied geometry/wall semantics and surveyed ceiling/wall/repeat gates; multi-level floors and scalar sloped-ceiling scoring |
| 08 Openings | Multi-camera through-ray candidates; raw jamb/header/sill refinement independent of ceiling availability; attachment/dedup; unknown height withholds net area | Physical instance/width/height audit, closed doors, occlusion/furniture, misses and phantoms |
| 09 Video/drift | Source timestamp/selection accounting; on/off propagated to RGB; retained tracking boundaries; historical-loop verification separated from consecutive motion limits; union footprint, survey gates and pose-delta ablation | Native full property, wall accuracy and effective identical-input on/off drift evidence; synthetic control has no verified loops |
| 10 Property stitching | Verified cycle constraints; merged normalized views/poses for damage/openings; one-to-one source-room identities; partial/disconnected children rejected | Strict-photo automatic property identities/shared surfaces; physical continuous video/LiDAR property |
| 11 Damage/scope | Shared-wall face visibility; registered-view selection before budget; room floor datum; surface coverage status; measured annotation extents kept separate from polygons; misses/phantoms/clean controls; conservative rules | Two-class/clean-control annotation/extent validation; candidates remain experimental |
| 12 Calibration | Frozen-artifact record builder; producer-bound property-grouped 90% fitting; split checks; unavailable groups stay null; independent audit coverage/width/sample interval | Nine independent calibration properties per tier/kind/unit for finite groups; untouched audit and refit after producer change |
| 13 Evaluation/evidence | Canonical gates; collinear wall normalization; phantom/miss penalties; consumer exact ties/all dimensions; benchmark integration; prospective fix snapshot/replay/diff | Full surveyed benchmark/consumer; own worst measured gate declared before fixing; raw before/after regeneration |
| 14 Packaging/rehearsal | Plan/design/status MDs, commands, verified artifact accounting; three-page artifact-driven technical checkpoint PDF generator | Final surveyed benchmark/report, raw bundle, clean/unseen rehearsals, real milestone commits |

## Verification

- Baseline: 52 tests passed before this phase.
- Expanded suite before the final geometry replay: **85 tests passed in 20.91 seconds**.
- After geometry regression fixes: **87 tests passed in 19.66 seconds**. A further
  reproduction guard test has since been added; its final run is recorded below.
- Bootstrap PowerShell syntax parsed without errors; installation is untested.
- Isolated source/test copy excludes private `datasets/` and historical `demo/`
  assets passed **85 tests in 19.73 seconds** before the last geometry/reproduction
  changes. The final source copy is retested below. It reuses installed
  workstation dependencies and cannot establish a clean-machine installation.

Tests cover shared-door identity/v1 adjacency, missing opening height, finite
confidence/units/references, false success, truth leakage, cache tampering,
calibration sample count/producer/split/audit, ceiling support, fitted walls,
apertures, crack quantities, consumer omissions, regenerated claims and prospective
fix integrity. Synthetic fixtures are software evidence only.

## End-to-end evidence

Fresh frozen runs are recorded below after completion. Earlier experiments remain
in `demo/phase3_e2e/`; some overlap source edits. Only a ledger with
`code_changed_during_run: false` provides a frozen producer checkpoint. These
already implemented changes must not receive retrospective Part 4 declarations.

The supplied Stray data contain no independent survey truth. Their extracted RGB
frames test the RGB-only interface but are not Native Camera stills. Public
synthetic RGB and a TUM video clip are development controls, not field acceptance.

| Frozen checkpoint | Result | Reconstruction seconds | Interpretation |
|---|---|---:|---|
| `frozen_photos/result` | incomplete_geometry; 1/4 derived views tracked; no plan | 48.07 | Supplied full-resolution extracted RGB; zero registered SfM views; experimental fallback insufficient |
| `frozen_video/result` | partial; 6/12 original frames registered, all 6 derived views tracked; no plan | 54.58 | Public six-second TUM proxy; original timestamps 0.0 through 5.5 seconds; incomplete walls/coverage |
| `frozen_lidar/result` | incomplete_geometry; 115/115 sampled frames tracked; no plan | 12.47 | Real supplied sensor intake works; supported boundaries do not close |
| `frozen_icl_photos/result` | failed; 3/4 registered; metric prior inconsistent across verified tracks | 26.94 | Public synthetic RGB-only development control rejects unsupported global metric scale |

All four ledgers record unchanged source during their execution and written
assessment/report artifacts. Runtime excludes initial asset/model download and
does not prove clean-machine or phone performance.

### Regression discovered during incremental E2E

The generated two-room LiDAR control initially failed closure after fitted-line
changes (`frozen_control_lidar`, 8.43 s). Fitted line selection had used axis
projection spread, which includes point noise. Resolving inclination from the
fitted plane's lateral displacement (development 6 mm span) restored one room
(`control_noise_resolution`, 9.33 s), exposing a second numerical topology issue.
Bounded endpoint intersections also needed to trim small overshoots and assign
identical intersection coordinates, rather than extending outside endpoints only.

The corrected replay `control_bounded_endpoints` tracks 97/97 frames and restores
**two rooms, one adjacency, 100% camera coverage, SVG/DXF/CSV and a research-ready
proposal in 9.32 s**. Ceiling observations remain unavailable and the calibrated
assignment contract remains incomplete. Gap bounds are still 15 cm; unsupported
large gaps are not closed. Reduced noisy wall evidence and inclination/noise tests
now cover the regression. This is a synthetic regression fix, not a declared
physical worst-gate Part 4 result.

### Artifact regeneration

The first full reproduction attempt (`regenerated_checkpoint`) correctly recorded
four failures: the tool had placed its own command log inside each fresh output,
triggering the capture runner's nonempty-output guard. Logs now stay outside case
outputs; a guard regression test covers this. The failed attempt is retained.
The corrected replay uses [the checkpoint manifest](benchmark/phase3_checkpoint_reproduction.json)
and records outcomes under `regenerated_checkpoint_v2`; its final summary is
added below. Regenerated failed captures are verified development evidence, never
assessment successes. Large proxy assets remain separate from Git.

The corrected regeneration **verified all four artifacts and all 24 claims**:
photo/video/LiDAR failures and the two-room control with canonical scoring. Every
run recorded unchanged source. The control also passes its historical geometry
targets, while canonical ceiling/calibration/full assignment acceptance remain
unmet. The manifest does not count this synthetic result as field validation.

Final isolated-source verification: **89 tests passed in 26.02 seconds**. Its
package import was explicitly checked to resolve inside the isolated copy.
It contains no private dataset or previous demo outputs. An initially misplaced
test assertion was corrected before this passing run.
The last added check rejects changed evaluator source even when its declared
version label stays the same, protecting prospective before/after comparisons.

### Earlier Phase 3 frozen artifacts

| Regenerated case | Outcome | Reconstruction s | Total capture s |
|---|---|---:|---:|
| Photos | no plan, 1/4 derived views tracked | 50.93 | 52.33 |
| Video | partial, no plan, 6/6 derived views tracked from 6/12 originals | 52.81 | 53.28 |
| Supplied single-room LiDAR | no plan, 115/115 tracked | 11.23 | 33.06 |
| Generated two-room control | research proposal, two rooms/one adjacency | 9.11 | n/a: normalized input |

The other supplied scans were also replayed with the final inference source:

- `final_floor_only`: 175/175 tracked, insufficient supported vertical walls,
  no plan; 21.11 s reconstruction / 74.07 s including intake. One video-tail frame
  is explicitly omitted from 5,251 raw odometry rows.
- `final_with_ceiling`: 300/300 tracked, observed wall segments do not close a
  room, no plan; 43.80 s reconstruction / 203.13 s including intake. The raw
  9,745 odometry rows have 6,899 depth/confidence pairs; 2,846 unpaired rows are
  logged and excluded.

Both have unchanged-source ledgers, written assessment/report and nonzero exits.
These two additional replays are outside the four-case reproduction manifest;
their commands are the `run-capture` LiDAR command with the corresponding supplied
folder, fresh output, assignment profile and frame budgets 180/300. Physical
property identity across the provided scans remains unverified. No scan supplies
independent dimensional truth.

The [three-page technical checkpoint](../demo/phase3_e2e/technical_checkpoint_final/technical_checkpoint.pdf)
is generated from the four regenerated cases and was visually checked page by
page. Its companion `report_metadata.json` contains complete source hashes,
producer status, blockers and timings. It is explicitly a development checkpoint,
not the final physical assessment submission.

## Holds before submission

1. Strict native RGB reconstruction, automatic property stitching and surveyed
   accuracy/calibration must pass. Returned model depth does not prove cm accuracy.
2. Collect the same-property benchmark, actual independent repeat, staged damage
   annotation, consumer export and adequate calibration/audit properties.
3. Obtain the official schema and missing Round 1 acceptance definitions.
4. Complete the prospective worst-gate fix, raw reproduction, timed clean-machine
   and unseen-phone rehearsals; build final reports from those artifacts.

Do not substitute manual connectors, laser scale in strict photo inference,
assumed heights or widened gap closure for missing evidence.
