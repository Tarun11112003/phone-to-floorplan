# Assignment device and tier matrix

| Tier | Eligible phone | Source and retained evidence | Current route | Metric accuracy evidence |
|---|---|---|---|---|
| 2–8 stills per room | iPhone 15+ including non-Pro | Original HEIC/JPEG, room folders, EXIF; no depth or poses | Camera → importer → SfM. Under five total views fails; arbitrary-scale SfM cannot yield dimensions without independent scale. Separate-room stitching absent. | No assignment-compliant physical test; 8% wall and footprint gates unproven. |
| Walkthrough video | iPhone 15+ including non-Pro | Original MOV/MP4/HEVC, duration and source hash | Camera → importer → frame selection/SfM. Requires scale evidence for metric plan. | Synthetic dense-video result only; 3% wall gate unproven on native phone clip. |
| RGB-D / LiDAR | Pro-class iPhone with LiDAR | Stray Scanner RGB, depth (mm), odometry, intrinsics, confidence if exported | Raw export → strict synchronisation and coordinate conversion → RGB-D reconstruction. Registration and coordinate conventions need device verification. | ARKitScenes public-data provisional single-room result; no on-device Stray Scanner test or required multiroom survey. |

The [Stray Scanner export format](https://github.com/strayrobots/scanner/blob/main/docs/format.md)
defines odometry, depth, confidence and RGB files. The
[app listing](https://apps.apple.com/ca/app/stray-scanner/id1557051662) lists
LiDAR availability and exports. App availability, exact frame registration and
operator steps are pending a physical trial. No phone variant can be marked as
meeting the brief's centimeter-level gates on the current evidence.
