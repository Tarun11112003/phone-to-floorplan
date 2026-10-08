# Prospective fix: prove a three-room stitch chain in the offline contract

Phase 4 currently has only a two-room controlled scene; no
available capture set has three measured rooms with shared connector truth. This
is a software-readiness check only, not a replacement for that field benchmark.

## Frozen baseline and hypothesis

The existing `run_project` manifest stitch path aligns a source room to an
already placed target from two anchor points. Baseline SHA-256:

- `floorplan/pipeline.py`: `920FA9FA0DD6B04D5789CC4EC598A6CBDB876452D679E7F44D5A30AD97BCE5B7`
- `floorplan/demo.py`: `DEF8FE532951DB043C1683D212266EDF889989D6B9C79EDF1C7611EDC1122113`
- `tests/test_floorplan.py`: `FC3B74B87101CBD0AF7E085B7AD3F0B197F052DF262D87DABCEFBF79C7D5382B`

Hypothesis: a declared chain A→B→C places all rooms consistently and emits the
same globally registered plan and quantities as its analytic reference. Input is
the deterministic generated demo image/video with synthetic room corner data;
it contains no phone scan, LiDAR scan, or independent truth.

## Prediction and falsification

Prediction: the 3-room smoke benchmark exports all three rooms, correct doorway
adjacency, a single global plan, and zero corner/dimension error against the
analytic reference. Falsify if any room remains independent, any transformation
or adjacency is wrong, or the property plan is not exported. Preserve negative
checks for disconnected rooms, unscaled rooms, and inconsistent anchors. Passing
this test means the stitching contract is ready for field inputs; it does not
close Phase 4's surveyed accuracy gate.

## Outcome

The new end-to-end test passed. Its third room is independently input and linked
to the second room, producing placements `origin`, `stitched`, `stitched`; the
evaluator measured maximum corner error and p95 dimension error below 1e-9 m.
SVG and DXF property exports were created. The fixture supplies exact room corners
and anchor coordinates, so it validates chained manifest alignment and output
consistency, not visual matching or a real capture. The physical Phase 4 gate
remains open. A companion regression now rejects a deliberately inconsistent
doorway anchor pair. Both targeted stitch tests and the full suite pass (52 tests).
