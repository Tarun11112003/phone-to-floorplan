# Phase 3 synchronization and boundary continuation

The subsequent [partial-cell completeness batch](fixes/012_PARTIAL_CELL_COMPLETENESS.md)
continues from this frozen baseline. Results here retain their original producer;
the newer batch preserves observed geometry and records separate inferred cells.

Implementation authorized against
[the execution roadmap](ASSESSMENT_EXECUTION_ROADMAP.md). Existing dirty files
were preserved. No commits or pushes.

## Phase 0: confirmed decoder defect and implemented correction

The preceding full read-only audit compared every RGB timestamp in all three
supplied scans. Default playback decoding dropped the initial encoded keyframe,
leaving 1714/5250/9744 RGB frames versus 1715/5251/9745 sensor rows. Same-index
timestamp cadence was inconsistent; decoded index +1 fitted the sensor cadence.
Ignoring MP4 edit lists restored all encoded frames, the initial keyframe and
same-index correspondence. Full affine clock-fit maximum residuals were
0.030/0.122/0.361 ms. These are timestamp residuals, not physical accuracy.

`ingest.prepare_stray_scanner` now ignores playback edits **only for raw scanner
exports**, audits every decoded integer PTS in the extraction pass, and rejects
internal frame/cadence mismatches or missing initial keyframes. It retains depth
IDs, per-frame intrinsics and original sensor poses. Source PTS/sensor times,
clock fit and omissions are retained in `sync_audit.json` and intake mappings.
Ordinary photo/video playback semantics remain. The clock fit checks identity;
it does not change sensor poses, certify optical registration or calibrate scale.

Timing thresholds are development identity guards: <=1000 ppm clock-rate
difference and residual bounded by half a video tick or one-quarter of the
minimum sensor interval, whichever is smaller. They are not assessment gates.
The new timing module is included in cache/measurement producer fingerprints.

Six timing regressions plus intake/reproduction tests pass: **22 passed in
7.23 s**. They cover exact integer PTS, clock rate/origin, internal omissions,
initial keyframe rejection, disclosed tail loss, extra RGB and invalid clocks.

The full artifact-writing audit completed under
`demo/phase3_sync_boundary/sync_audit`. All three encoded timelines restore every
sensor frame and the initial keyframe; all three playback timelines fail
same-index cadence consistency. JSON records retain full integer PTS and raw
video/CSV hashes. **139 regressions passed in 24.80 s** after the correction and
boundary diagnostics. The subsequent codec-content regression and related
timing/intake/geometry/reproduction checks passed: **27 passed in 9.95 s**.
No physical benchmark or cm-level claim.

## Phase 1: stage diagnostics

Boundary extraction now records global/secondary/proposed planes, segment
retention, doorway candidates/traversal rejections, junction network, cut edges,
dangles, invalid rings, accepted cells and exact polygon rejection reasons.
The original geometry thresholds and fallback policy are unchanged at this
diagnostic checkpoint. Frozen diagnostics render the recorded network/basis,
rather than refitting or inserting survey geometry.

Reference A's height-band projection and Reference B's projection modes are
already considered in the prior supplied-data pass. Neither scanner parser fixes
this RGB decoder issue. No claim that a reference method outperforms ours is made
without a controlled result. Rectangle filling, unrelated fixed depth bias,
fixed final-frame intrinsics and fallback poses/confidence are not adopted.

Remaining: closure diagnosis/fix, RGB registration and all
subsequent roadmap phases. Full measured acceptance remains open.

## Raw replay checkpoint (completed)

Fresh raw single intake retains 115/115 views; reconstruction is partial, one
fallback room and 34.78% camera coverage (14.07 s reconstruction / 47.47 s total).
Its network has 31 dangles; the sole observed polygon is below the existing
area guard. Correct synchronization does not resolve the independent closure
failure. Source is frozen during reconstruction.

Fresh floor intake restores the final sample, retaining 176 views rather than
the old 175. It is still partial, 9.09% coverage, seven rejected raw polygons,
49 dangles and one fallback cell (19.47 s reconstruction). More retained frames
and valid pairing are not an accuracy improvement claim.

| Raw case | Paired retained views | Observed cells / fallback cells | Camera coverage | Dangles | Reconstruction / complete command time |
|---|---:|---:|---:|---:|---:|
| single | 115 | 0 / 1 | 34.78% | 31 | 14.07 / 47.47 s |
| floor | 176 | 0 / 1 | 9.09% | 49 | 19.47 / 103.91 s |
| ceiling | 300 | 1 / 0 | 8.00% | 45 | 28.98 / 187.00 s |

All three reconstruction commands correctly returned non-acceptance (exit 1).
The reproduction harness passed **3/3 cases and 15/15 declared checks**;
`code_changed_during_run` is false for each. This proves reproducible execution
and honest status, not successful reconstruction. Fresh ceiling diagnostics are
in `demo/phase3_sync_boundary/ceiling_diagnostic`, including the finite network
and rejected cells. Older normalized inputs remain historical.

## Alternative wall-proposal comparisons

The bounded local Open3D planar-patch comparison was executed.
It uses the same frozen cloud/trajectory, existing global-equivalent support,
2.5 cm residual, vertical/extent/orientation checks, no bounding-box room fill,
and the original finite-boundary rules. It is a development comparison and cannot
promote a backend merely by increasing camera coverage.

| Same frozen ceiling cloud | Accepted extra plane proposals | Observed cells | Camera coverage | Dangles | Decision |
|---|---:|---:|---:|---:|---|
| Existing proposals | 0 | 1 | 8.00% | 45 | Preserve baseline |
| Open3D patches, global-equivalent support | 6 | 1 | 8.00% | 50 | Do not integrate |
| Open3D patches, bounded local spatial support | 13 | 1 | 7.67% | 67 | Do not integrate |
| Height-band density/Hough + local raw 3D checks | 12 | 2 | 14.33% | 53 | Experimental only; still incomplete |
| Narrower-band/48-seed local projection | 43 | 6 | 64.00% | 104 | Experimental only; more cells do not establish room identity |

The minimal support correction was subsequently selected based on a reproduced
invariance failure, not a camera-coverage accuracy claim. It keeps the original
band/seed budget and adds raw-point/spatial-cell acceptance. Same-cloud comparison
with the retained historical support policy gives 1 to 2 observed cells and
8% to 24% coverage; both remain incomplete, zero adjacency. Full regressions
pass **143/143 in 57.34 s**. See [the correction record](fixes/011_LOCAL_WALL_SUPPORT.md).
Raw all-case replays after this production change completed under
`demo/phase3_sync_boundary/local_support_raw_replay`: **3/3 cases, 15/15 checks**.

| Raw case after local acceptance | Observed / fallback cells | Camera coverage | Dangles | Reconstruction / complete command time |
|---|---:|---:|---:|---:|
| single | 0 / 1 | 34.78% | 46 | 21.16 / 55.75 s |
| floor | 0 / 1 | 9.09% | 97 | 34.95 / 120.10 s |
| ceiling | 2 / 0 | 36.67% | 57 | 34.58 / 189.80 s |

All remain partial, with incomplete contracts and unchanged code during runs.
Local acceptance fixes the demonstrated support defect, but adds more fragmented
segments and runtime without completing single/floor plans. Its risks remain
explicit; these results do not establish more correct semantic rooms.

The original and new ceiling fused clouds differ in only two float32 values
(maximum 1.49e-8 m), while their raw optimized poses differ by <=2.63e-13 in
matrix entries. Refitting/polygonization can nevertheless change room subdivision
and closure: the new saved-cloud replay splits the large left cell into two
cells with the same combined footprint; an older saved-cloud replay loses part
of that boundary and yields 24% rather than 36.67% coverage. This is a known
numerical/topology reliability concern, not independently demonstrated repeatability.
An explicit precision-grid comparison on the new frozen cloud (floating,
1 micrometre, 0.1 mm) produced identical 36.67% coverage/three cells/56 dangles.
It did not resolve the issue and was not adopted. Artifacts are under
`precision_after_local_support`. Do not attribute all differences solely to
serialization or claim numerical stability from this test.

Artifacts: `patch_trial`, `local_support_rank_trial`, and
`density_trial_shape_corrected` under `demo/phase3_sync_boundary`. The local
spatial trial retains comparable global-equivalent support for plane ranking.
An earlier local trial used raw support for ranking; it is retained separately,
and is not the fair-ranking comparison cited above. Baseline polygon counts
vary 21/22 for tiny numerical slivers; meaningful cell count, coverage and
dangles agree. No surveyed error improvement is inferred.

Reference A's `geometry/walls.py::density/wall_mask/dominant_orientations`
motivated the density proposal comparison. Our experiment uses local line seeds,
then validates finite raw 3D consensus, height/length span, spatial cells,
orientation and residual. Its 250 raw-point/40-cell limits are disclosed
development choices. It does not use A's flood-fill or morphology to claim room
dimensions. Reference B's unconditional rectangle and fixed-input substitutes
remain inappropriate. Open3D is an existing dependency; neither comparison
adds a runtime dependency to production.

An initial density experiment failed on the OpenCV returned-line shape; reshaping
to Nx4 corrected it and the rerun succeeded. The first video trial manifest used
the wrong nested source path and correctly failed intake; that path and a Windows
UTF-8 BOM were corrected before the actual RGB trial. These failed attempts are
retained and are not reported as successful validation.

## RGB-only sampling checkpoint

Both actual RGB-only sampling trials completed under
`demo/phase3_sync_boundary/video_sampling_verified_input` with six declared
execution checks passing and unchanged producer source during each run.

| Requested budget | Selected by sharpness/temporal budget | Registered views | Sparse points | Verified pairs | Reconstruction / command time |
|---|---:|---:|---:|---:|---:|
| 48 | 45 | 4 | 450 | 59 | 249.57 / 257.03 s |
| 72 | 68 | 10 | 153 | 139 | 351.85 / 358.81 s |

Both return partial/no plan, not accepted success. Selection may retain fewer
than its budget. Each selected video PNG currently receives a separate AUTO
camera (45/68 cameras). Verified pairs are predominantly UNCALIBRATED (55/134),
with 4/5 PLANAR_OR_PANORAMIC pairs and 6/8 images without any verified pair.
These facts motivate a bounded shared-camera 72-view trial; they do not prove
intrinsics grouping is the sole root cause. The earlier 24-view shared trial
registered 3/24 instead of 2/24 and was not promoted.

The shared-camera comparison holds the source, budget, matching guards and
pinned metric model constant. It assumes lens/intrinsic constancy; that remains
unverified for the supplied video and cannot silently become a default for
videos with zoom or lens switching. Its manifest contains no sensor sidecars.

## Pose-correction evidence correction

`ablation.compare_pose_correction` now counts accepted, numerically valid
geometric pose-graph constraints, including segmented sequential ICP graphs.
The assessment permits verified correction mechanisms other than loops. Raw
pose priors and unbacked loop counters are insufficient. The report still
requires actual trajectory change, enabled correction and identical inputs/code;
`accuracy_improvement` remains null without independent survey. This flag proves
an executed geometric correction mechanism, not reduced physical drift.
Targeted ablation/pose-boundary tests: **8 passed in 3.34 s**.

## RGB rectification correctness

`dense._undistort` supplied COLMAP source pixel-center coordinates directly to
OpenCV `remap`, causing a half-pixel shift and unnecessary dark-border mixing.
The identity and half-resolution pinhole controls both failed before correction
(2 failed in 1.03 s), then passed after converting source coordinates by -0.5.
The target OpenCV calibration matrix remains centered at (width-1)/2.
[COLMAP's official convention](https://colmap.github.io/faq.html#using-calibration-from-opencv-kalibr-or-other-tools)
distinguishes these origins. Related camera/registration/contract checks:
**29 passed in 5.28 s**. One initial targeted command named a nonexistent test
file and ran no tests; the corrected command uses the actual existing tests.

This changes RGB dense/metric sampling, so historical RGB runs retain their old
producer. The 72-view camera comparison reruns the current backend for AUTO using
a validated unchanged SfM cache, then runs shared-camera reconstruction fresh.
Only SfM registration changes can be attributed solely to camera grouping;
body geometry comparisons must use the same current backend. A physical accuracy
benefit is not asserted from the pinhole controls.

The current-backend camera comparison completed with **6/6 execution checks**:
AUTO (validated unchanged SfM cache) and fresh shared-camera both register 10/68
views, producing 153/147 sparse points respectively and no plan. Runtime is
97.68 s for cached AUTO downstream replay versus 408.41 s for fresh shared full
reconstruction; these are **not comparable full-runtime speed figures**.
Shared camera did not improve registration and is not adopted as a default.

## Further finite-wall correctness corrections

Two furnished-scene regression failures were reproduced before implementation:

- A 0.2 m-tall coplanar furniture fragment inherited the height support of a
  distant real wall, yielding two wall segments instead of one (1 failed in
  1.43 s). Each finite fragment now must pass the existing >=0.45 m height-span
  guard itself. The threshold is unchanged; its scope is corrected.
- Sixteen high-count, short furniture peaks exhausted the pre-validation
  twelve-bin proposal budget, omitting a genuinely observed wall (1 failed in
  1.52 s). The local policy now searches at most 48 bins per axis until twelve
  accepted proposals are found. The accepted-plane cap remains twelve per axis;
  the historical support policy retains its original search budget.

Targeted wall/furniture/opening checks: **17 passed in 24.50 s**. The current
complete regression suite passes **150 tests in 48.42 s**, including the timing,
pixel-coordinate, ablation and isolated semantic diagnostic checks. A six-case
current-source integration replay is underway. No production source is edited
during reconstruction.

## Semantic alternative evaluated

A pinned SegFormer-B0 ADE20K evaluation ran on 18 source sensor views with
visibility checked against corrected poses, camera intrinsics, depth and
confidence. It preserves unseen points and requires >=2 visible furniture votes
with >60% dominance and >=0.6 model score before rejection. Those are disclosed
development choices, not calibrated model confidence or accuracy guarantees.

Raw sensor images include quarter-turn camera roll. Model input was normalized
using the supplied gravity/poses, and label maps inverse-rotated back to the
original camera grid; sensor RGB, intrinsics, depth and poses were unchanged.
Both original and upright trials removed **zero** points: no useful geometric
filtering effect was established. Source input does not prove an annotated
furnished damage benchmark, and sparse 18-view visibility leaves many points
unseen. Do not lower the guard merely to obtain a numeric improvement.

The first semantic comparison also refitted planes on the saved float32 cloud;
coverage changed 36.67% to 22.33% despite zero removed points. That change is a
refit/numerical confound, **not** a semantic-model effect. The script now includes
an unfiltered refit control and shares its seeds with the candidate when no points
are removed. No semantic backend was added to production.

Artifacts: `semantic_ceiling_trial` and `semantic_upright_ceiling_trial`. Pinned
model `nvidia/segformer-b0-finetuned-ade-512-512`, revision
`489d5cd81a0b59fab9b7ea758d3548ebe99677da`, safetensors SHA-256
`6ae39addd01de6b1b8bde2cf677d43a5cd733424b8d186de3f95d1c51fee23f9`.
Its [model card](https://huggingface.co/nvidia/segformer-b0-finetuned-ade-512-512)
links [NVIDIA terms](https://github.com/NVlabs/SegFormer/blob/master/LICENSE),
which limit use to research/evaluation. This is an isolated take-home evaluation;
no commercial production rights or semantic ground truth are asserted. Only
existing Torch/Transformers dependencies are used; weights stay in ignored cache.

## Current-source six-case integration checkpoint

`geometry_correctness_final/reproduction.json` verifies **6/6 cases and 19/19
execution claims**. The generated geometry control retains two rooms, one
adjacency and a passing topology gate. Its assignment contract remains incomplete.
All supplied/derived cases intentionally retain assignment exit 1:

| Case | Tracked/input frames | Observed cells / fallback | Camera coverage | Reconstruction seconds |
|---|---:|---:|---:|---:|
| single | 115/115 | 0 / 1 | 34.78% | 19.19 |
| floor only | 176/176 | 0 / 1 | 9.09% | 35.09 |
| ceiling | 300/300 | 3 / 0 | 29.00% | 28.40 |
| denser single | 286/286 | 0 / 1 | 36.71% | 57.20 |
| extracted photos | depth fallback 1/4; SfM remains unregistered | 0 / 0 | 0% | 46.61 |

The denser single replay starts from raw scanner input and audits all 1,715
encoded RGB frames; the other sensor cases reuse the audited normalized intake.
Runtime above is reconstruction, not intake plus reconstruction. More tracked
frames do not establish complete walls or correct semantic room identities.
The broader suite at this checkpoint passed **150 tests in 48.42 s**, serially.

## Original finite-corner bound correction

Two additional regressions failed before the correction: sequential 15 cm joins
extended an actually observed endpoint by **42 cm**, and reversing segment visit
order changed the resulting geometry. The search now evaluates intersections
against immutable original finite lines in canonical order, then selects bounded
endpoint extrema simultaneously. It does not rotate the observed lines or relax
the existing 15 cm bound. The wall/opening suite passes **19 tests in 25.08 s**.
A fresh six-case replay (`original_bound_replay`) completed: **19/19 execution
checks**, generated two-room/one-adjacency topology retained, all contracts
incomplete. Single stays 34.78% coverage, denser single 36.71%, ceiling 29%; floor
now has one observed cell at 5.11%, replacing the earlier 9.09% inferred cell.
Coverage is not monotonic with correctness fixes and is not a measured score.
The corrected search reduces single/ceiling/floor dangles to 34/72/66.

## Exact geometry artifact replay

The same-code ceiling replay in `float32_replay_before_corrected_report` confirms
that saved float32 coordinates differ from the float64 fitting inputs: wall
segments and room corners differ, and raw polygons change **69 to 71**, even
though both camera coverage values remain 29%. The first verifier attempt failed
to serialize a NumPy boolean; that reporting error was corrected before recording
this baseline. Neither result is physical repeatability or surveyed accuracy.

`rgbd` now saves the actual float64 coordinates used for fitting, and `workflow`
records checksums for the cloud, trajectory, plane summary and layout evidence.
Shapely's version is included in measurement fingerprints. SfM cache identities
are unchanged. `scripts/verify_layout_artifact.py` checks original producer,
artifact hashes, exact corners, wall segments, coverage and boundary diagnostics.
Four verifier regressions pass, including changed-cloud, changed-dimension and
unversioned-producer failures. Targeted contract/provenance/wall tests pass
**28/28 in 5.36 s**. Fresh-source integrations and exact artifact replay follow.

The next broad run exposed one real regression: **155 passed / 1 failed in
47.05 s**. The existing traversed-door two-room test returned one room. A trace
located a **1.11e-16 m** difference between a partition endpoint and its adjoining
outer wall; bridge/fragments themselves had identical lateral locations. This
corrects the initial bridge-mismatch hypothesis. Shapely's documented
[precision-grid union](https://shapely.readthedocs.io/en/stable/reference/shapely.union_all.html)
now nodes the finite network at **1e-9 m**. Raw fitted wall segments remain unchanged;
this is numerical consistency, not a new gap allowance or accuracy assertion.
The corrected search plus precision noding passes **31 targeted regressions in
30.81 s**, including the previously failing two-room test and missing-wall/gap
guards. The older coarse coefficient-canonicalization experiments remain unadopted.

The full suite then passed **156 tests in 47.21 s**. The current-source combined
manifest (`exact_geometry_current`) completed **9/14 cases**: all eight native
reconstruction executions plus the identical-input drift comparison verified
their **28 execution claims**. Five artifact checks failed because the verifier
compared Shapely tuple coordinates against JSON list coordinates. Walls/corners
already matched exactly; the control differed only in connection representation,
and supplied cases differed only in diagnostic representation. A real diagnostic
tuple fixture reproduced the verifier failure (1 failed / 3 deselected).

The verifier now compares both sides in their published JSON representation,
retaining exact numeric equality, producer identity and artifact checksums.
**8 verifier/reproduction tests pass in 2.14 s**. The five unchanged artifacts
were reverified into `exact_artifact_reverified`: **5/5 cases and 15/15 claims
passed**, including exact corners, walls, connections, diagnostics and source
checksums. The failed combined run is retained.
It must not be retrospectively described as a 14/14 successful run.

Current identical-input on/off correction uses all 115 frames with unchanged code.
On has **4 verified sequential ICP constraints**, no verified loops, and maximum
pose changes **0.0732976 m / 0.586558 degrees**. Both plans remain partial with
zero adjacency. Footprint changes **6.99150 to 7.35540 m2** and camera coverage
**37.39% to 34.78%**. These are software-mechanism/shape-change observations, not
measured drift improvement; `accuracy_improvement` remains null. REQ-27 physical
accuracy acceptance stays open.

## Current evidence boundaries and remaining requirements

| Requirement group | Locally verified in this continuation | Remaining assessment acceptance |
|---|---|---|
| REQ-04,17,42 sensor capture | All encoded timelines paired/audited; initial frame restored; measured missing/tail accounting; three raw replays | Optical/depth registration, device/export-version validation, complete room/property reconstruction |
| REQ-07,10 walls/property | Spatial support invariant, local fragment height, accepted proposal budget, original gap bound, generated two-room adjacency | Supplied property boundaries still partial; semantic room identities and physical dimensions unknown |
| REQ-02,03,28,29 RGB | Strict input separation, corrected pixel origin; 0/4 photo and 10/68 video registration reported honestly | Native still/video reconstruction, complete property/graph, measured wall/footprint gates and calibration |
| REQ-27 drift | Identical source/code; verified geometric constraints and actual pose/footprint changes | No independent evidence that drift/accuracy improved; no verified loop on this supplied case |
| REQ-35,42 reproducibility | Exact saved geometry replay on four supplied configurations plus generated control; producer/source hashes | Full raw release volume, raw native-solver stability on supported environments, cold-machine timing |
| REQ-08,09,11,14,15 | Existing conservative per-room surfaces, through-ray opening guards, damage projection and grouped-calibration machinery retained | Measured ceilings/openings/damage; closed-door recognition; real calibration and independent audit |
| REQ-19-26,30,31,38,40,41 | Independent survey/import/evaluation paths already exist | Own >=3 rooms plus connector, all tiers, repeat, staged damage, measured truth, actual consumer export, prospective worst-gate Fix Loop, adverse/unseen rehearsal |
| REQ-16,36,37 | Internal contract and truthful development reporting | Published schema/Round 1 definitions and final <=6-page surveyed report |

Current-source supplied coverage after all corrections is **34.78% single,
5.11% floor, 29.00% ceiling**, with the denser single at **36.71%**. These are
camera-in-cell development proxies, not footprint or metric-error scores.
Photos remain **0/4 SfM registered**, depth fallback **1/4** and no plan. Video
remains **10/68** and no plan, taking **69.01 s downstream reconstruction** from
validated SfM cache; that is not full fresh video timing. Generated control retains
two rooms/one adjacency. Every assignment contract remains incomplete.

The final controlled semantic diagnostic completed in **47.87 s** under
`semantic_current_controlled`. Frozen planes, unfiltered refit and semantic
candidate all produce the same stage counts, three partial cells and 29% coverage.
Zero points are removed; 150,541/202,477 points have no selected-view visibility.
The corrected control therefore establishes **no benefit**, without attributing
plane-refit changes to the model. Keep semantic filtering out of production.

## Files affected by this continuation

Production: `floorplan/capture_sync.py`, `ingest.py`, `layout.py`, `dense.py`,
`ablation.py`, `provenance.py`, `rgbd.py`, `workflow.py`. Preserve the earlier
Phase 3 changes in other dirty files; this inventory does not attribute them to
the current continuation.

Regression additions/updates: `tests/test_capture_sync.py`, `test_ingest.py`,
`test_wall_completion.py`, `test_wall_planes.py`, `test_ablation.py`,
`test_rgb_camera_consistency.py`, `test_semantic_diagnostic.py`,
`test_layout_artifact.py`. Diagnostics/evaluation: capture timing, supplied geometry,
wall-policy comparison, isolated planar/density/precision/semantic alternatives and
`scripts/verify_layout_artifact.py`. Reproduction manifests are under
`docs/benchmark/`; code/model/input hashes and actual trial results stay in fresh
ignored `demo/phase3_sync_boundary` directories.

Documentation: this ledger, assessment execution roadmap, Phase 3 design/status/
operations, local-support correction record, open-source decisions and README.
No commit or push was made. No measured benchmark, future Fix Loop prediction or
physical acceptance result has been fabricated.

The final verifier also checks the complete measurement producer fingerprint,
including dependencies/configuration, rather than geometry-module hashes alone.
A changed-recipe regression rejects matching geometry from a different producer.
**26 verifier/contract/reproduction tests pass in 5.92 s**; all five unchanged
artifacts pass again with that full identity check, **15/15 claims**, under
`exact_artifact_producer_verified`. This adds no geometry
implementation change and does not alter supplied reconstruction outcomes.

Final serial regression after all continuation changes: **157 passed in
47.31 s**. The earlier 156-test runs (47.21 s and 50.69 s), reproduced geometry
failure and verifier failures remain historical evidence. No failed assertion
was removed or measurement tolerance relaxed. No native task remains running.

The next highest-value boundary validation is to establish independent room/wall
correspondence for a measured property, then score a frozen raw-input replay.
Continue geometry diagnosis on supplied inputs in parallel; do not select an
assessment-qualified Fix Loop from coverage alone. No external survey has been
invented, and no whole requirement is closed solely by component regressions.

Canonicalizing segment coefficients/extents before junction construction on the
older frozen cloud stabilized coverage at 36.67% for the tested three precision
settings, unlike union precision alone. This remains an experiment: current-source
paired-cloud/repeat validation and displacement-bound checks are needed before
adopting it. Finite coordinates must not be coarsened to manufacture room closure.
