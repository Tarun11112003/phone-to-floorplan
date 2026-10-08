# One-page stock-phone capture protocol (Route 2 candidate)

**Final handoff:** [operations](PHASE3_OPERATIONS.md) describes strict
assignment flags and the unpromoted RGB experiment. Transfer photos as per-room folders; record one
consistent physical property ID outside inference media. Calibration/truth/consumer
exports remain separate assets. Current replay outcomes are in
[validation ledger](BENCHMARK_RESULTS.md).

**Status:** operational draft. A nonengineer has not yet completed an unseen-room
rehearsal, so this is not a validated assignment capture route. Use an iPhone 15 or
newer for photos/video; use a Pro-class model with LiDAR for depth. Capture the same
rooms in every tier. Keep original files, filenames and metadata. Do not use a
floor-plan app's processed model as input.

1. **Choose the space.** Give each room a short distinct ID, including a connector
   such as `hall`. Open the doors. Make a quick list of room IDs and the doorway
   pairs between them. Photograph the laser/tape reading for each wall, door/window
   width, ceiling height and staged damage region separately; keep these survey
   images outside the capture folders so they cannot leak into inference.
2. **Photos:** make a folder for each room. With the ordinary Camera app, take **2–8
   original stills per room**. Stand in different corners, include floor-wall and
   wall-ceiling junctions, every doorway/window, and the same shared doorway from
   both adjoining rooms. Avoid digital zoom and panorama. Keep some furniture in
   view, but move enough to show boundaries safely. Transfer originals by cable or
   an option that preserves original HEIC/JPEG files. Do not send compressed chat
   copies. Use unique room folder names; duplicate camera filenames are fine.
3. **Video:** with the ordinary Camera app, record a slow continuous walkthrough
   of the property. Start by showing the floor, ceiling and each wall of the first
   room; pass through each connecting door while filming both sides. Pause briefly
   on windows and staged damage. Walk steadily, avoid fast turns and blur, and keep
   normal lighting. Transfer the original MOV/MP4 file.
4. **LiDAR:** on a LiDAR iPhone, install [Stray Scanner](https://github.com/strayrobots/scanner)
   if available in your region. Record the same slow walkthrough; export the **raw**
   `odometry.csv`, `camera_matrix.csv`, `imu.csv`, `rgb.mp4`, `depth/`, and `confidence/` files together. Preserve
   their names and frame numbers. The importer resizes RGB to depth resolution and
   scales per-frame intrinsics when their aspect ratios match; it rejects unsupported
   distortion tables or aspect-ratio mismatches. Inspect the diagnostic if an app
   version exports a different format.
5. **Transfer and run:** copy the folder or original clip to the Windows computer.
   Install once using the README instructions. Open PowerShell at the repository
   root. Choose the matching command, using a new output directory each time:

   ```powershell
   & .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier photos --source captures\property_photos --out runs\photos_01 --profile assignment --property-id property_01
   & .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier video --source captures\walkthrough.mov --out runs\video_01 --profile assignment --property-id property_01
   & .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier lidar --source captures\stray_export --out runs\lidar_01 --profile assignment --property-id property_01
   ```

Check `runs/<name>/result/run.json` for status and `plan.svg`/`plan.json` if
produced. A nonzero exit or absent plan is a **failed/incomplete capture**; retain
the raw data and error log. The code accepts 2–8 photos and attempts matching.
Sparse registration is overlap-sensitive: some contiguous supplied RGB subsets
register, while widely spaced subsets fail; the tested public low-resolution
iPhone RGB segment registers only 2/8 views. RGB scale and
separate-room placement remain unresolved for arbitrary unposed media. No result
from this draft workflow is certified to centimeter accuracy.
