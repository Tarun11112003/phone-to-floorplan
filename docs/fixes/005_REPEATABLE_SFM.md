# Prospective fix: seed all COLMAP SfM stages

## Observed failure

Three fresh stock-photo runs on identical ARKitScenes 8-image RGB input each
registered 4/8 views and verified the same 23 of 28 image pairs, but produced 12,
32 and 43 sparse points. Both correctly remained `scale_unresolved`; the quality
result was not repeatable even after seeding the exposed mapper stages. Database
inspection then found that run A inserted image names in a different order
(`00, 02, 01, 03...`) from runs B/C (`00, 01, 02, 03...`).
Passing a sorted image-name list did not resolve this: with multiple feature
workers, image IDs still reflected feature-completion order. Serialize feature
extraction so database IDs follow the explicit sorted list. This made the three
feature, descriptor, match and two-view-geometry tables identical, but sparse
point counts still varied (43, 12, 43). The remaining nondeterminism is in
incremental mapping/optimization, so also serialize its worker count.

PyCOLMAP exposes independent seeds in two-view RANSAC, the incremental mapper and
the triangulator. It also accepts an explicit ordered image-name list, but
parallel feature completion can reorder database IDs, and parallel mapping can
vary the final sparse model even with identical feature databases.

## Proposed change

Pass sorted selected-image names explicitly and set feature extraction and
incremental mapping to one worker. Set a fixed seed explicitly on two-view
geometric verification, the mapper and the triangulator, retaining the pipeline
seed. Preserve feature thresholds,
camera mode, matching method and all scale/status behavior. Report unchanged
registration, sparse point and verified-pair metrics on repeated identical
captures.

## Prediction and falsification

- Three fresh reconstructions of the same 8-image input produce identical
  registered-image count, sparse-point count and verified-pair diagnostics.
- The 2- and 4-image statuses remain unchanged and continue to expose diagnostics.
- Falsify if any repeated result differs or if a status/accuracy safeguard is
  relaxed to get stable output.

## Outcome

The original seed-only runs and the sorted-name/seed runs were not stable. After
serializing feature extraction and incremental mapping, three fresh stock-photo
runs produce the same status and counts: 4/8 registered, 12 sparse points, 23/28
verified pairs and 121 maximum inliers. Each remains `scale_unresolved`. The
explicit image order is identical in the feature database. Runtime for the fresh
8-image photo run is about 1.3 seconds on this workstation.

This evaluates software determinism only. It is not a physical repeat-capture or
measurement-accuracy test.
