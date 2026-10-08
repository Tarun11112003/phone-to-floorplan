# Stock-phone capture protocol

**Status: unverified capture route.** These steps have not been validated by a
first-time user on a freshly set up phone. Use the same property across all
three tiers and keep the original capture files.

1. **Prepare the property.** Choose at least three rooms and a connecting hall;
   give each a unique ID. Keep one room furnished and safely stage two damage
   classes. Record device/app versions and the transfer method. Separately
   measure walls, openings, ceiling heights and damage extents with laser/tape.
   Keep those measurements and survey photographs outside reconstruction inputs.
   Capture at least one room twice independently at the same tier.
2. **Capture each tier.** Include floors, walls, ceilings, openings and staged
   damage. Show shared doorways from both adjoining rooms.

   | Tier and device | Capture steps | Save originals to |
   |---|---|---|
   | Photos: any iPhone 15 or newer | Use Camera. Take **2-8 stills per room** from different corners, including floor/wall/ceiling junctions. Avoid digital zoom, panoramas, blur and compressed chat copies. | `captures/property_photos/<room_id>/` as HEIC/JPEG |
   | Video: any iPhone 15 or newer | Use Camera for one slow continuous walkthrough through **every room and the connector**. Traverse doorways and show both sides; avoid fast turns. Preserve original MOV/MP4 metadata. | `captures/walkthrough.mov` |
   | LiDAR: iPhone 15 or newer with LiDAR, Pro-class | Use Stray Scanner if available in the phone's region. Follow the same slow route and export raw sensor data. Check app availability and export behavior on the actual phone. | `captures/stray_export/` |

   Strict photo inputs must contain no depth, poses or scale annotations. The
   required photo result is one whole-property plan; isolated room drawings are
   insufficient. For LiDAR, keep `rgb.mp4`, `depth/`, `confidence/`,
   `camera_matrix.csv`, `odometry.csv` and `imu.csv` together with their original
   names and frame numbers.
3. **Transfer and run.** Open PowerShell at the repository root. Follow the
   [README](../README.md) setup (`scripts/bootstrap_windows.ps1`) and exact tier
   command. Use a fresh output directory and run once per capture. Keep raw data
   and logs even if the command exits nonzero.
4. **Review the result.** Inspect `result/report.html`, `run.json`,
   `assessment.json` and `plan.svg` when available. Keep consumer-app exports
   separate for comparison; never supply a processed consumer floor plan or
   survey measurements to reconstruction.

**Current limits:** strict RGB scale/stitching is incomplete and supplied LiDAR
plans are partial. A nonzero exit or missing measurement does not demonstrate
success. No tier has demonstrated independent centimetre accuracy or full
assessment acceptance.

See the [device matrix](device_matrix.md) and
[Stray export reference](https://github.com/strayrobots/scanner/blob/main/docs/format.md).
