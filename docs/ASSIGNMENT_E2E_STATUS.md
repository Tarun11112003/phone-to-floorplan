# Incremental end-to-end status — 2026-10-06

The [assignment brief](<Applied AI.html>) is the target. The evaluator is
`assignment-aug2026-provisional-v1`; the published schema and earlier Round 1
gate definitions are absent from the supplied HTML. The raw predictions and full
machine-readable gate results are in ignored `demo/assignment_e2e0/` and
`demo/assignment_e2e1/` on this workstation. They can be regenerated from the
commands below and the documented V3 fixture.

| Checkpoint | Data | Outcome | Meaning |
|---|---|---|---|
| E2E 0: frozen plan scoring | V3 controlled two-room photo, video and simulated LiDAR plans | Photo/video walls, openings, footprint and topology pass the newly stated provisional gates. All three fail ceiling and interval presence. LiDAR wall gate remains pending the missing Round 1 definition. | Old geometry success is not assignment completion. |
| E2E 1a: sparse intake → reconstruction | Two synthetic photos in one room, same 2–8 input count as allowed | Import succeeds with room ID and hashes. One command exits 1 and saves `result/run.json`: SfM requires at least five overlapping images. | The 2-photo route is currently unsupported. |
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
[`single_room` diagnostic](../demo/given_single_room_run_v2/result/layout_diagnostic.svg)
shows the six supported segments and camera path; it is a diagnostic rendering,
not a dimensioned plan.
