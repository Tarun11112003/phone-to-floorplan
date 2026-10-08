# Prospective fix: report verified photo overlap and SfM initialization failures

## Observed gap

Sparse trials currently report only `no_model`. Read-only inspection of the
existing COLMAP databases shows that this hides two different cases: the public
low-resolution iPhone two-view pair has zero geometrically verified pairs, while
some supplied high-resolution RGB two- and four-view failures have geometrically
verified pairs with over 200 inliers. A match count does not establish usable
parallax or a stable 3D seed, so these cases must remain distinct.

COLMAP's official incremental-mapper defaults require 100 initial-pair inliers
and a 16-degree triangulation angle, then its pipeline relaxes initialization
constraints over retries. Changing those safeguards without metric truth could
make attractive but unstable geometry. The observed gap is missing diagnostics,
not permission to weaken acceptance.

## Proposed change

After feature matching, read the existing COLMAP database and add auditable
counts to `sfm_summary.json` and `run.json`: possible image pairs, pairs with
verified two-view geometry, verified inlier maximum/median, images with no
verified pair, and the strongest verified pairs. If no model forms, distinguish
no verified overlap from verified pairs that still failed model initialization.
Show the guidance and compact counts in the offline HTML capture review as well.
Keep reconstruction, registration status, thresholds and metric-scale behavior
unchanged. Do not read or expose sensor streams or ground truth.

## Prediction and falsification

- The 2-view ARKitScenes trial will report zero verified pairs and an overlap/
  texture diagnostic.
- At least one failed supplied high-resolution trial will report verified pairs
  yet an initialization failure diagnostic.
- The successful calibrated ICL 2/4/8 trials will report pair support and retain
  exactly the same registered-image and sparse-point counts.
- Blank/featureless images will still fail honestly with zero verified pairs.

Falsify this change if output counts disagree with direct read-only database
queries, if any geometry/status/scale changes, or if diagnostic code consumes
anything beyond the image-matching database. Add unit tests for empty, partially
connected and fully connected pair graphs; run the RGB suite and fresh 2/4/8
end-to-end trials on the same held-out subsets.

## Outcome

Implemented pair counts, inlier summaries, unpaired-image names and stage-specific
guidance in the SfM summary, capture ledger and HTML review. The fresh public
iPhone 2/4/8 intake runs agree with their databases: 0/1 verified pairs at 2
views; 4/6 at 4 views with no model; 23/28 at 8 views with 4/8 registered.
The 8-view run remains `scale_unresolved` and produces no floor plan. Blank images
retain their safe failure. Four diagnostics tests pass; the full suite result is
recorded in `ASSIGNMENT_E2E_STATUS.md`.

The original-pair diagnosis holds: verified inlier counts alone do not guarantee
stable pose initialization. COLMAP's geometry decisions remain unchanged.

## Open-source decision

Keep COLMAP/SIFT as the CPU baseline for this code increment. The official COLMAP
mapper exposes inlier/parallax guards, so first measure which guard the evidence
fails before changing it. LightGlue is an Apache-2.0 matcher with Apache-2.0 DISK
weights or BSD-3-Clause ALIKED; SuperPoint has a separate restrictive license.
It is a reasonable optional matching experiment if pair diagnostics show missing
correspondences, but it cannot supply metric scale and adds a learned-model/runtime
dependency. VGGT's commercial checkpoint requires gated access and a GPU-oriented
large model; it is a later backend candidate, not a practical default for this
Windows CPU demo. Do not bring noncommercial DUSt3R/MASt3R checkpoints into the
commercial-facing take-home path.
