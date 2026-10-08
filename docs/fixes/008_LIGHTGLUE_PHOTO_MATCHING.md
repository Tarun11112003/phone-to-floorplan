# Prospective experiment: LightGlue + DISK for sparse photo matching

This is an isolated matcher trial; production matching and
acceptance thresholds remain unchanged unless evidence supports adoption.

## Failing metric and baseline

The supplied RGB-only high-resolution sequences have view-dependent SfM results.
With the current seeded COLMAP/SIFT pipeline on four adjacent frames, the group at
start 0 registered 0/4 and produced no model; the group at start 80 registered
4/4 with 62 sparse points. Both are from the RGB export of the supplied LiDAR
recording, so they test view/matcher behavior, not independent still-photo accuracy.
Baseline code `floorplan/sfm.py` SHA-256:
`e409307351ccd0318f3721c4cf673f7442b751e7d833e7c08e0be642eba1ff4a`.

The eight source RGB image SHA-256 values are recorded by frame ID in the trial
input manifest. Inference may read those RGB images only; it must not access depth,
poses, intrinsics, trajectories, reference scans, scale controls or the mapper's
previous sparse model.

## Root-cause hypothesis and open-source option

Hypothesis: some failed 2–8-view groups fail because SIFT descriptors do not retain
enough correspondences under viewpoint/appearance changes. LightGlue is an
adaptive sparse-feature matcher designed for local feature correspondence and its
official implementation supports DISK features. Test the Apache-2.0 LightGlue and
DISK code/weights; avoid SuperPoint because the official repository identifies its
separate restrictive license. Pin the repository commit, checkpoint revision and
SHA-256 before running.

Pinned before inference: LightGlue code commit
`eb42fee2d71449efb0aa5c10549752b5d75384d8`; matcher release `v0.1_arxiv`, file
`disk_lightglue_v0-1_arxiv.pth`, SHA-256
`b5b21d47ea24f2c5e501aec9c91b9716e4c8c3429a4dc1e615c133c4c9378335`;
DISK extractor checkpoint `depth-save.pth`, SHA-256
`9c2ee4ded238892dfa51569941372601e35e4a74aa6f84ea80053d2ab1c07abe`.

Source references: [LightGlue](https://github.com/cvg/LightGlue),
[HLoc's COLMAP/SfM pipeline](https://github.com/cvg/Hierarchical-Localization).

## Predicted result and falsification

Prediction: on identical RGB, LightGlue+DISK will create geometrically verified
matches for the start-0 4-view group and register at least 3/4 images, while the
start-80 group remains at least 4/4. Use identical camera model, mapper settings,
RANSAC/geometric checks, and seeded single-thread reconstruction. Keep every input
view; do not choose only a successful subset.

Falsify if the failed group's verified-pair graph/model does not improve, the known
successful group loses registration, geometric verification is weaker despite more
raw matches, inference exceeds the documented demo time budget, or any withheld
reference stream enters the matcher. Additional matches alone do not establish
room geometry, metric scale, or centimetre accuracy.

## Measurement

Record per pair raw matches, verified inliers, graph connectivity, registration
fraction, sparse points, runtime and peak memory. Run the current SIFT baseline and
the candidate on fresh databases from the exact same eight RGB inputs. If results
justify integration, add an opt-in matcher and regression tests in a separate code
change. Regardless of result, leave photo scale, plan extraction, room stitching,
survey accuracy, and the final assignment gate open.

## Outcome

Fresh seeded SIFT baseline and isolated CPU LightGlue runs used the same two four-view
RGB groups. On `start0`, SIFT produced 6/6 verified pairs, max 581 inliers, 0/4
registered, and no points. LightGlue produced 6/6, max 1,224 inliers, but still 0/4
and no points. The SIFT pairs classify as `PLANAR_OR_PANORAMIC`; LightGlue's classify
as `UNCALIBRATED`. On `start80`, SIFT registered 4/4 with 60 points; LightGlue
registered 4/4 with 305 points and increased max inliers from 71 to 361.

LightGlue took 29.04 seconds / ~2.19 GB peak RSS for `start0` and 27.35 seconds /
~2.19 GB for `start80`, compared with the faster SIFT baseline. It did not satisfy
the predicted recovery of the failing sequence, and more matches did not create a
stable initial model. **Decision: do not integrate** into the default CPU pipeline.
Keep the script and its pinned dependencies isolated for future GPU or broader
photo-set evaluation. Neither matcher result establishes scale, a floor plan, or
centimetre accuracy. The source database classifications are independently
summarized by the new diagnostics in fix 009.
