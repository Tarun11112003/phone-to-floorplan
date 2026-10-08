# Stock-phone capture protocol ? Route 2 candidate

**Status: unverified capture route.** This is a one-page handoff protocol, not a
passed novice/cold-device trial. Use the same property across all three tiers.
Keep raw originals; do not input a consumer app's processed floor plan.

1. **Prepare.** List unique room IDs, including a connector/hall. Keep one room
   furnished and record two staged damage classes safely. Keep laser/tape
   measurements and survey photographs in a separate folder outside inference.
   Measure walls, openings, ceiling heights and damage extents; repeat at least
   one room at the same tier. Record device/app version and transfer method.
2. **Photos ? any iPhone 15+.** Use the stock Camera app. Take 2 to 8 original stills
   per room from different corners. Include floor/wall/ceiling junctions,
   openings and shared doorways from both adjoining rooms. Avoid digital zoom,
   panoramas, blur and compressed chat copies. Transfer original HEIC/JPEG files
   into `captures/property_photos/<room_id>/`. No depth, poses or scale annotations
   belong in the strict photo input. Photo folders must ultimately form one
   whole-property plan; isolated room drawings are insufficient.
3. **Video ? any iPhone 15+.** Use Camera to record one slow continuous walkthrough.
   Show each floor, ceiling, wall, opening and staged damage; traverse connecting
   doorways while showing both sides. Avoid fast turns. Transfer the original
   MOV/MP4 to `captures/walkthrough.mov`, preserving metadata.
4. **LiDAR ? iPhone 15+ Pro device.** Use Stray Scanner if available in the
   device's region. Follow the same slow route. Export raw `rgb.mp4`, `depth/`,
   `confidence/`, `camera_matrix.csv`, `odometry.csv` and `imu.csv` together into
   `captures/stray_export/`. Keep names/frame numbers unchanged. Current app
   availability/export behavior must be checked on the actual phone.
5. **Transfer and execute.** Open PowerShell at the repository root. Install
   once with `scripts/bootstrap_windows.ps1`; choose the exact tier command in
   the README, using a fresh output directory. Run one command per capture.
   Inspect `result/report.html`, `run.json`, `assessment.json` and `plan.svg`
   when available. Retain raw data and logs even if the command exits nonzero.

**Current limitations:** strict RGB scale/stitching is incomplete; supplied LiDAR
produces partial plans. A nonzero exit/absent measurement is not success.
No tier is certified to centimetre accuracy. Consumer exports are comparison
references only, never inference inputs. The device matrix and evaluator
commands are linked from the README.

[README](../README.md) ? [device matrix](device_matrix.md) ?
[Stray export reference](https://github.com/strayrobots/scanner/blob/main/docs/format.md)

[Printable one-page protocol](capture_protocol.pdf).
