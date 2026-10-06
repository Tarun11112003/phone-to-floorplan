# Phase 0: benchmark inventory and collection status

Authority: [Cozmo Applied AI brief](../Applied%20AI.html). Updated 2026-10-06.
This inventory separates the supplied integration data from the benchmark that
the brief requires the candidate to create.

## Current data inventory

`datasets/Given_dataset/` contains three Stray Scanner exports. The app/device
version and physical capture setup have not been independently verified. The
existing intake manifests hash the odometry and video source files; prepared
bundles are ignored by Git under `demo/`. Aggregate counts below come from the raw
folders and frozen intake ledgers; use full per-file manifests on newly collected
benchmark data.

| Supplied scan | Raw asset inventory | Latest observed reconstruction | Truth status |
| --- | --- | --- | --- |
| `single_room/c00a170fe1` | 1,715 odometry rows, 1,715 depth and confidence frames, `rgb.mp4`; intake sampled 172 frames. | One partial room about 2.54 x 3.00 m; 36.6% camera coverage; no ceiling. | No tape/laser survey or room-corner reference supplied. |
| `single_scan_floor_only/1a8384c3f6` | 5,251 odometry rows, depth and confidence frames; decoded video ends one frame early; intake sampled 175. | No room plan; inadequate observed vertical-wall support. | No dimensional truth supplied. |
| `single_scan_with_ceiling/c7d28f72c6` | 9,745 odometry rows, 6,899 depth/confidence pairs, 2,846 unpaired odometry rows; intake sampled 300. | Corrected-pose run tracks 300 frames but has four parallel wall segments and no closed plan. | No dimensional truth supplied. |

These are useful raw-format, sensor-registration and failure-mode tests. They do
not meet the required benchmark because they are not a surveyed 3+ room property
captured in all tiers; they have no independent geometry/damage truth, independent
repeat or incumbent-app export.

Other data already in the repository include controlled synthetic two-room
photo/video/LiDAR fixtures, ICL-NUIM synthetic RGB-D, and a TUM RGB-D video.
Their roles and limitations are in [DATASETS.md](../DATASETS.md). They do not
replace the physical benchmark described by the brief.

## Required collection matrix

Use one stable `property_id` and stable room/wall/opening/surface IDs across the
following evidence. Preserve original exports and hash them at intake. Record
device model, OS, capture app/version, timestamps, tier, and any conversion. The
evaluation pipeline receives raw capture; survey measurements remain evaluator-only.

| Capture ID | Required evidence | Current state |
| --- | --- | --- |
| `property_a_photos` | 3+ rooms plus connector; one folder per room; 2–8 stills per room; no depth or poses. | Missing physical capture. |
| `property_a_video` | Handheld iPhone 15+ walkthrough covering the same rooms and connector. | Native-device video missing. |
| `property_a_lidar` | Pro-class iPhone RGB, depth, poses and intrinsics covering the same rooms. | Only unrelated single-room supplied scans exist. |
| `damage_room_*` | Furnished room, same room in each tier, with two staged damage classes and undamaged controls. | Missing capture and annotations. |
| `repeat_room_*` | At least one room captured twice at the same tier, restarting capture independently. | Missing independent repeat. |
| `consumer_room_*` | Two benchmark rooms scanned by one named consumer app; version and actual export retained. | App choice/export missing. |
| `challenge_*` | Mirrors, glass, wet-look surfaces and low light; label each condition. | Missing labeled challenge captures. |

Follow and update [CAPTURE_PROTOCOL.md](../CAPTURE_PROTOCOL.md) and
[DEVICE_MATRIX.md](../DEVICE_MATRIX.md) using the actual device/app versions.
Protocol instructions require room coverage and readings, but have not been tested
with the actual iPhone, stock apps or a novice operator.

## Truth collection rules

- Assign IDs before inference. Give each physical wall one `wall_id` shared across
  captures; give each physical opening its own `opening_id` even when doors connect
  the same pair of rooms.
- Use a documented local coordinate convention for room corners and damage polygons.
  Record tape/laser raw readings, tool/model, stated resolution, operator, date and
  a photo showing the measurement. Keep raw endpoints/readings; do not store only
  rounded dimensions.
- Measure every room's floor footprint, ceiling height, every wall, every door/window
  width and height, and annotated damage-region class/extent. Mark non-measurable or
  obscured items explicitly with a reason.
- Capture repeat data in a new independently started session. Reusing the same files
  tests deterministic replay, not physical repeatability.
- Keep model development, calibration and final evaluation properties disjoint.
  Do not feed test tape values, consumer exports or survey alignments to inference.
- For the incumbent comparison, measure the same physical dimensions in both outputs;
  retain unshared/missing dimensions and failures in the denominator as required by
  the official scoring definition.

## External definitions still absent

The supplied HTML states the new gates for opening width/detection, ceiling height,
repeatability, drift ablation, photo whole-property stitch and photo/video wall
lengths. It also refers to the “Round 1” gates without reproducing the complete
definitions, and mentions a “published schema” without including it. No schema file
or full earlier gate definition is present in this workspace at this checkpoint.
Keep current evaluator labels provisional for any unspecified LiDAR wall, area,
damage, interval-coverage or denominator rule. Do not silently fill those gaps with
an internal choice and claim exact compliance.

## Phase 0 close checklist

- [ ] Obtain and version the published JSON schema.
- [ ] Obtain/version all earlier Round 1 gates and resolve any ambiguity in opening
  scoring, LiDAR wall accuracy, area and interval coverage.
- [ ] Fill [benchmark manifest](benchmark_manifest.template.json) for one physical
  property shared across three tiers.
- [ ] Enter independent raw survey values in the CSV templates in this directory.
- [ ] Add the staged damage room, repeat capture, two consumer exports and challenge
  conditions to the same manifest.
- [ ] Verify all inputs by hash and physically check one sample row/ID from every table.
- [ ] Freeze development/held-out property membership before tuning.

Phase 0 is now prepared in the repository, but remains open until the boxes above
that require external captures and definitions are completed. The next code focus
stays Phase 1 after the benchmark definitions and photo-tier data are usable.
