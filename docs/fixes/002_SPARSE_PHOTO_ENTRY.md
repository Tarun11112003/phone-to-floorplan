# Prospective fix: permit the stated 2–8-photo input count

Declared 2026-10-06 before changing `sfm.py`.

The importer accepts two photos, but SfM currently rejects fewer than five before
attempting image matching. COLMAP's default minimum model size is also ten and
two-view-only tracks are ignored. This guarantees an input-policy failure even
when a calibrated two-view pair has sufficient parallax and correspondence.

Change the minimum accepted frame count to two; cap minimum model size at available
image count; enable two-view tracks for a two-image experiment. Keep the existing
geometric inlier and triangulation checks. Do not relax them to manufacture a model.
Preserve unresolved metric scale as an explicit failure to produce dimensions.

Prediction: 2/4/8 photo attempts reach correspondence and pose estimation instead
of the five-image policy error. This does not predict a complete or cm-accurate
floor plan, because overlap, parallax, observed walls and scale remain necessary.
Test blank pairs for safe failure and supplied RGB subsets for actual registration.
Reference depth/poses must not enter the photo reconstruction.

## Observed outcome

The 2/4/8 uniformly sampled RGB subsets all reached feature extraction/matching
and returned `no_model` due to lack of verified matches. The original-resolution
8-image subset also returned `no_model` in 18.97 s. No sensor poses, intrinsics or
depth entered these photo trials. Blank-input regression retains an auditable
failure after quality filtering and generates a failure HTML/JSON report.
The software input restriction is fixed; successful sparse-photo geometry is not.
