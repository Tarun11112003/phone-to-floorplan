# Device and capture matrix

Route2 candidate: Native Camera for photos/video; Stray Scanner raw export
for LiDAR. This is a software/hardware-availability matrix, **not measured accuracy**.

| Tier | Hardware assumption | Delivered input path | Independently demonstrated accuracy | Status |
|---|---|---|---|---|
| Photos | iPhone15 or newer, including base models | Original HEIC/JPEG;2–8 stills per room, no depth/poses | None on a qualifying phone/property benchmark | PARTIAL: intake and SfM; strict metric property result incomplete |
| Video | iPhone15 or newer, including base models | Original MOV/MP4 walkthrough | None against required±3% wall gate | PARTIAL: decoding/timing/SfM; difficult transitions unresolved |
| LiDAR | iPhone15 or newer with LiDAR (Pro-class) | Stray Scanner RGB/depth/confidence/odometry/per-frame intrinsics | None against independent physical ceiling/opening/wall/repeat gates | PARTIAL: supplied raw sensor export exercised, device/cold capture unverified |

LiDAR availability is not assumed for a base iPhone16. Current app version,
availability, export behavior and installation time must be recorded in a
physical rehearsal; none has been fabricated. Follow the [protocol](CAPTURE_PROTOCOL.md).
The [upstream export format](https://github.com/strayrobots/scanner/blob/main/docs/format.md)
is the recorded adapter reference. Learned RGB and research-scale outputs do
not create a per-device centimetre-accuracy guarantee.
