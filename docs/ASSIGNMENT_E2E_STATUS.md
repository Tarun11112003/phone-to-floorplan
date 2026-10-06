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
| Regression suite | 28 tests | All pass in 15.39 s on this workstation. | Software invariants, not field acceptance. |

Commands for the scored frozen plans (run each tier in `photos video lidar`):

```powershell
& .\.venv\Scripts\python.exe -m floorplan.cli evaluate-assignment demo\v3_verified\photos\plan.json datasets\controlled_multimodal_v3\reference.json --tier photos --out demo\assignment_e2e0\photos_gates.json
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier video --source demo\assignment_e2e1\tum_room.mp4 --out demo\assignment_e2e1\tum_video_run
& .\.venv\Scripts\python.exe -m pytest -q
```

Current gate table and command paths are provisional until the actual schema and
Round 1 rubric arrive. The next indispensable evidence is a surveyed property
with 3+ rooms and a connector, all three raw capture tiers, independently repeated
room capture, damage regions, and a two-room consumer-app comparison. The code
still lacks sparse-photo metric reconstruction, separate-room property stitching,
ceiling estimates, complete openings, calibrated intervals and restoration scope.
No centimeter-level field result can yet be claimed.
