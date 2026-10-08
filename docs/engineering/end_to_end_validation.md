# Incremental end-to-end status — **Latest evidence:** [batch 017](investigations/017_disk_lightglue_transition.md)

**Historical engineering record. Development is closed. Current requirements/status and evaluator commands are in [compliance](../compliance_matrix.md) and [README](../../README.md).
connects the bounded RGB match graph using pinned DISK + LightGlue, but does not
produce a joint endpoint sparse model. No production backend or acceptance rule
is changed; 192 regressions pass. This is a validated matcher experiment, not
a successful end-to-end property reconstruction or a physical accuracy result.

**Update:** [Phase 3 implementation/test status](implementation_history.md#consolidated-implementation-and-acceptance-ledger)
records the current frozen replays and provisional-v2 evaluator. The entries below
retain earlier results and limitations; they are not the latest acceptance state.
The latest [supplied-data continuation](implementation_history.md#supplied-capture-reconstruction-integration) records
133 passing serial tests, three partial supplied sensor results and the actual
RGB-only supplied-video failure to close a room.

The [assignment brief](../specification/applied_ai.html) is the target. The evaluator is
`assignment-aug2026-provisional-v1`; the published schema and earlier Round 1
gate definitions are absent from the supplied HTML. The raw predictions and full
machine-readable gate results are in ignored `demo/assignment_e2e0/` and
`demo/assignment_e2e1/` on this workstation. They can be regenerated from the
commands below and the documented V3 fixture.

## Latest restoration and open-source increment

Earlier rows below are historical checkpoints. The current suite passes **52 tests**.
The supplied single-room scan now produces a partial room, while sparse
RGB inference is attempted for 2–8 photos instead of being rejected by a five-image rule.

| Increment | Actual result | Acceptance limit |
| --- | --- | --- |
| Supported-cell geometry, unchanged 172-frame supplied capture | One 2.54 x 3.00 m partial room, 7.608 m2, 36.6% camera coverage | Unknown ceiling and missing boundaries; no survey truth |
| Surface assessment and offline report | `demo/given_restoration_on/report.html`, validated internal `assessment.json`, evidence overlays and inspection scope | Heuristic candidate masks; published schema and statistical calibration pending |
| Pose correction off/on | One partial room in both; 7.535/7.608 m2; 12.80/16.46 s; zero verified loops | Identical hashed inputs/code; change is not measured accuracy improvement |
| Fresh V3 LiDAR regression | Two room polygons with exactly unchanged corner coordinates | Ceiling evidence remains insufficient; synthetic fixture with supplied poses |
| Fresh V3 photo/video dense reconstruction and assessment | Two rooms each, exactly unchanged corner coordinates; 247.43/246.10 s | Reused hashed SfM caches and measured scale controls; not a fresh sparse-photo or clean-machine test |
| Depth Anything V2 Small, actual pinned CPU model | Eight images; per-frame mean absolute depth disagreement with LiDAR 0.128–0.774 m | Experimental adapter retained; rejected as cm-scale measurement source |
| Supplied RGB-only 2/4/8 subsets at 256x192 | All reach feature matching; all return `no_model`, no fabricated plan | Widely spaced frames do not provide verified matches |
| Supplied RGB-only 8-image subset at original 1920x1440 | Still `no_model`, 18.97 s | More resolution alone did not establish sufficient correspondences |
| Contiguous RGB-only subsets, original 1920x1440, starts 0 and 80 | Across two groups each at 2/4/8 views: 2-view groups both fail; 4-view groups yield 0/4 and 4/4; 8-view groups yield 8/8 and 7/8, with 62–223 sparse points on successful models | Confirms overlap/view selection changes registration. Extracted from the LiDAR recording but only RGB entered inference; no scale, no plan, and no independent-photo/accuracy validation |
| ARKitScenes held-out iPhone RGB segment 41418140, 256x192, four seconds | 2-image and 4-image runs: 0 registered; 8-image run: 2/8 registered and 56 sparse points | RGB only entered inference; mobile depth, poses, calibration and FARO scan withheld. Low-resolution failure case, no metric plan or accuracy score |
| ICL-NUIM RGB-only subsets, 640x480, known PINHOLE intrinsics | 2/2, 4/4 and 8/8 registered; final seeded rerun: 126, 220 and 491 sparse points | Synthetic calibrated-camera feasibility check only; depth, trajectory and mesh withheld, arbitrary scale and no floor plan |
| Fresh stock-photo intake E2E on held-out ARKitScenes low-res RGB, 2/4/8 images | 2: `no_model`, 0/1 pairs verified; 4: `no_model`, 4/6 pairs verified; 8: `scale_unresolved`, 4/8 registered, 12 sparse points, 23/28 pairs verified; reports written for all. Runtime 0.84/0.96/1.34 s. | The CLI returns nonzero because no metric floor plan is ready; this is the expected honest failure for missing geometry/scale, not a crash |
| Identical 8-photo software repeat, three fresh one-command runs | Each `scale_unresolved`, 4/8 registered, 12 sparse points and 23/28 pairs verified; same input ordering | Software determinism only; no physical rescan or accuracy claim |
| MoGe-2 ViT-S RGB-only metric-depth probe on ARKitScenes 41418140 | 8 synchronized RGB frames; 10.35 s/frame CPU, raw depth MAE 0.554 m, median absolute error 0.456 m, signed bias -0.364 m | No reference scale fitting; substantial frame variation; fails as a cm-scale source. Depth agreement only, not plan accuracy or surveyed truth. |
| Walk-in report coverage before/after on the same two ARKitScenes RGB photos | Both runs: `no_model`, 0/2 registered, no plan. After run: 0.81 s and 12 explicit output-coverage rows in JSON/HTML; baseline: 1.28 s and no coverage artifact. | Auditability changed as predicted; timing variation is noise. Photo geometry, metric scale and walk-in readiness remain failed. |
| Isolated LightGlue + DISK comparison, two four-view RGB groups | On failing `start0`, max verified inliers rose 581→1,224 but registration stayed 0/4; on control `start80`, registration stayed 4/4 and sparse points rose 60→305. Geometry classes and measured runtime/RSS are recorded in fixes 008–009. | Matcher not integrated: it did not recover the failed group and cost ~27–29 s / ~2.2 GB for four images. No scale or plan resulted. |
| Two-view geometry classification diagnostics | Fresh unit tests cover COLMAP config labels and unknown values; direct summaries match all four saved SIFT/LightGlue databases. Full suite: 50 passed. | Read-only diagnostics only; mapper decisions and acceptance thresholds are unchanged. |
| Fresh four-view SIFT diagnostic replay | Same `start0` RGB frames, fresh database: `no_model`, 0/4 registered, 0 points, 6/6 verified pairs, all `PLANAR_OR_PANORAMIC`, max 581 inliers. | Confirms the new configuration labels match the baseline; it does not resolve sparse-photo initialization. |
| Three-room software stitch chain | Deterministic A→B→C synthetic manifest, independent room captures, two connector alignments; exports one SVG/DXF plan with max corner error <1e-9 m and p95 dimension error <1e-9 m. | Closes the synthetic manifest-chain smoke test only. It does not test visual connector matching, physical room scans, or the assignment's 3+ room accuracy gate. |
| Stitch failure guard | Synthetic doorway anchors with a 0.4 m mismatch are rejected with a doorway-anchor disagreement error. | Prevents a deliberately inconsistent connector declaration from silently producing a combined plan. |

## Fresh public candidate benchmark — Command: `python -m floorplan.cli benchmark examples/public_benchmark.json --out demo/public_candidates_e2e_20261006`.
The run completed all five cases; **1/5 met the complete configured target**.

| Candidate | Result | Interpretation |
| --- | --- | --- |
| ICL-NUIM development | Maximum error 0.96 cm across the scored room dimensions; target <=3 cm met. | Synthetic RGB-D sequence; dimension-only scoring, proposal still requires review. |
| ICL-NUIM held-out trajectory | Dimension errors 0.52 cm and 2.01 cm; target <=3 cm met, but reconstruction is partial. | Synthetic feasibility evidence, not a complete floor-plan pass. |
| ARKitScenes development `41418135` | FARO-derived reference: P95 dimension error 1.96 cm, P95 corner error 1.73 cm, 100% sampled boundary coverage at 5 cm, IoU 0.993. | Best real-room candidate result. Provisional manually selected polygon from one scanner venue, four correlated edges, assumed 1 cm annotation floor; no independent review, openings, or field certification. Keep as a promising single-room result, not proof of general cm accuracy. |
| ARKitScenes held-out `41418140`, `41418155` | Both produce reviewable proposals, but have no vetted reference polygons. | Reconstruction output exists; accuracy is unscored. FARO PLYs are local, but annotation must be blind to predictions and independently reviewed. |

The FARO-only review found that the sampled wall-height projections do not
support defensible closed room annotations for either held-out venue: one has
interrupted/ambiguous perimeter runs, and the other appears to span multiple
spaces. We deliberately left both unscored instead of inventing polygons. See
[held-out reference review](reference_depth_review.md). Full-cloud,
multi-height room/topology annotation and a second reviewer remain the gate.

Raw machine-readable metrics and the rendered report are in ignored
`demo/public_candidates_e2e_20261006/benchmark.json` and `REPORT.md` on this
workstation. FARO scans were used only for reference scoring, not inference.
This candidate suite does not exercise restoration damage truth, a multiroom
physical stitch, or a property captured across all input tiers.

Sparse trials live under `demo/given_sparse_photo_trials/run_*` and
`demo/sparse_overlap_trials/`; they use RGB only. The public ARKitScenes low-res
trial likewise withheld its sensor streams and FARO scan from inference. These
are useful feasibility diagnostics, not the brief's independent still-photo
accuracy benchmark. The full-resolution supplied RGB trial is also recorded and
failed, while some contiguous subsets register. See
[overlap diagnosis](investigations/003_sparse_overlap_trial.md),
[research decisions](../third_party.md), [restoration architecture](../pipeline.md),
and prospective [geometry](investigations/001_supported_cells.md) / [sparse-entry](investigations/002_sparse_photo_entry.md) fixes.

[Archived regression summary](../../benchmarks/results/restoration_regression.json) records all
three tiers. Photo/video walls, openings, property footprint and topology pass the
provisional synthetic gates. All three still fail ceiling and interval requirements;
LiDAR wall tolerance remains pending the missing earlier definition. The assessment
contains uncalibrated envelopes, but the legacy plan evaluator does not consume
that separate contract and height intervals are unavailable regardless. Do not
interpret the new assessment file as a passed interval gate.

| Checkpoint | Data | Outcome | Meaning |
|---|---|---|---|
| E2E 0: frozen plan scoring | V3 controlled two-room photo, video and simulated LiDAR plans | Photo/video walls, openings, footprint and topology pass the newly stated provisional gates. All three fail ceiling and interval presence. LiDAR wall gate remains pending the missing Round 1 definition. | Old geometry success is not assignment completion. |
| E2E 1a: sparse intake → reconstruction (historical baseline) | Two synthetic photos in one room, same 2–8 input count as allowed | At the earlier code revision, one command stopped at a five-image software guard. That restriction has since been removed; current 2/4/8 trials proceed through feature matching but return `no_model`. | Intake works; this row documents a fixed software restriction. Sparse photo geometry remains unsupported, as confirmed by the current trials above. |
| E2E 1b: public real video → reconstruction | Six seconds of [TUM RGB-D `freiburg1_room`](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/download), transcoded from public AVI to MP4 for the importer | Import succeeds; 3/12 selected frames register; run finishes `scale_unresolved` in 7.6 s with no plan. | Video decoding works, but this clip gives neither full geometry nor absolute metric scale. It is not native iPhone footage. |
| E2E 1c: Stray Scanner format | Two-frame generated fixture with odometry, RGB, 16-bit mm depth and confidence | Import tests pass, including high-resolution RGB resampling, per-frame intrinsics, missing depth and orientation conversion. | Format parsing only; no physical device or accuracy validation. |
| E2E 4 preparatory repeatability check | Same frozen V3 photo plan supplied twice, plus synthetic paired regression cases | Same-file wall spread passes trivially; ceiling spread/accuracy fail due missing heights. A consistent 4 cm height bias passes spread but fails accuracy in regression. | Scorer works; same files are not independent physical captures. |
| E2E 3 preparatory ceiling check | Controlled V3 simulated LiDAR sequence, 97 frames | New geometric ceiling detector leaves both heights null because no sufficiently supported ceiling surface is observed. Tracking and two-room reconstruction remain intact; runtime 4.16 s. | Correct missing-evidence behavior, not a passing height gate. Synthetic broad-ceiling and cabinet-top tests pass. |
| Provided `single_room` LiDAR export | 1,715-frame raw Stray Scanner capture | 172 frames imported; direct-quaternion ablation tracks all frames and finds six supported wall segments, but no closed room because of a roughly 0.96 m wall gap and unverified boundary. | Real raw-media path works; no final plan or accuracy claim. |
| Provided `single_scan_floor_only` LiDAR export | 5,251 odometry/depth frames; video ends one frame earlier | 175 aligned frames processed through `run-capture`; one missing video-tail frame is logged. No closed plan: insufficient vertical wall support. | This challenge capture lacks needed wall coverage. |
| Provided `single_scan_with_ceiling` LiDAR export | 9,745 odometry frames, 6,899 paired depth/confidence frames | Import logs 2,846 unpaired frames and samples 300. Direct-quaternion reconstruction tracks all 300 but has only four parallel wall segments; no closed plan. | Ceiling coverage alone does not establish a floor-plan boundary. |
| Regression suite | 36 tests | All pass in 25.69 s on this workstation. | Software invariants, not field acceptance. |

Commands for the scored frozen plans (run each tier in `photos video lidar`):

```powershell
& .\.venv\Scripts\python.exe -m floorplan.cli evaluate-assignment demo\v3_verified\photos\plan.json datasets\controlled_multimodal_v3\reference.json --tier photos --out demo\assignment_e2e0\photos_gates.json
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier video --source demo\assignment_e2e1\tum_room.mp4 --out demo\assignment_e2e1\tum_video_run
& .\.venv\Scripts\python.exe -m floorplan.cli evaluate-repeatability demo\v3_verified\photos\plan.json demo\v3_verified\photos\plan.json datasets\controlled_multimodal_v3\reference.json --out demo\assignment_e2e0\same_file_repeatability.json
& .\.venv\Scripts\python.exe -m floorplan.cli reconstruct datasets\controlled_multimodal_v3\lidar.json --out demo\assignment_e2e3_lidar_ceiling
& .\.venv\Scripts\python.exe -m pytest -q
```

Current gate table and command paths are provisional until the actual schema and
Round 1 rubric arrive. The next indispensable evidence is a surveyed property
with 3+ rooms and a connector, all three raw capture tiers, independently repeated
room capture, damage regions, and a two-room consumer-app comparison. The code
still lacks sparse-photo metric reconstruction, separate-room property stitching,
ceiling estimates, complete openings, calibrated intervals and restoration scope.
No centimeter-level field result can yet be claimed.

## User-provided raw dataset checkpoint

`datasets/Given_dataset/` was supplied after the first audit. It is intentionally
ignored by Git because the raw captures are large. The three directories are
Stray Scanner exports with original RGB/depth/confidence/odometry and IMU. There
are **no tape/laser dimensions, opening labels, or certified room polygons** in
those folders, so they are integration and structural-coverage tests, not an
accuracy benchmark. The first adapter assumption flipped camera axes incorrectly;
the frozen same-frame direct-quaternion ablation restored vertical planes, and
the importer now uses that interpretation. The source format is documented in
[Stray Scanner's data specification](https://github.com/strayrobots/scanner/blob/main/docs/format.md).

```powershell
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier lidar --source datasets\Given_dataset\single_scan_floor_only\1a8384c3f6 --out demo\given_floor_only_replay --max-frames 180
```

The other two raw exports can be passed to the same command. The initial
`single_room` and `single_scan_with_ceiling` runs used an explicit same-input pose
ablation while correcting the adapter; `single_room` was then replayed with the
current one-command importer, 172/172 tracked frames and six wall segments. All
three runs presently fail to produce a
closed, dimensioned plan. The next geometry experiment should compare the
wall-gap candidate against independently measured room dimensions before closing
it automatically; treating an occlusion gap as a door without evidence risks a
phantom opening under the assignment gate.

When wall segments exist but cannot form a room, the pipeline now writes
`layout_diagnostic.svg` alongside the failure ledger. The current
`single_room` diagnostic (separate handoff: `demo/given_single_room_run_v2/result/layout_diagnostic.svg`)
shows the six supported segments and camera path; it is a diagnostic rendering,
not a dimensioned plan.
