# Prospective fix declaration: supported room cells

Declared before implementation, 2026-10-06. Baseline: `40d7b81`.

**Observed failure:** the supplied `single_room/c00a170fe1` capture produces zero
closed rooms from 172 selected RGB-D frames. Six supported wall segments exist.
Two fragments of one boundary differ by about 15 cm and have a roughly 0.96 m gap.
The current exact polygonization cannot close that boundary. Source evidence is
`demo/given_single_room_run_v2/result/artifacts/layout_evidence.json` and its cloud.

**Hypothesis:** a bounded arrangement of observed parallel wall fragments can
recover a reviewable room cell while exposing unsupported portions. Require
support on all four sides, a maximum missing span, a minimum supported fraction,
and camera occupancy. Record wall-location dispersion and each missing span.
Reject a three-wall room. Do not classify a gap as a door without separate evidence.

**Prediction:** at least one partial room proposal on the unchanged `single_room`
frames; no whole-property pass and no accuracy claim. Frozen V3 polygon results
should remain unchanged because the fallback only runs when no exact polygon closes.

**Test:** paired baseline/new outputs on the same prepared input; generated room
with an occlusion, missing entire wall, and no camera occupancy; V3 geometry regression.
Keep the old outputs and publish observed support, inferred gaps and camera coverage.

This is an integration fix declaration. The official worst accuracy gate cannot
be selected until surveyed truth is supplied; it is not the brief's final measured
accuracy fix experiment.

## Observed result

`demo/given_supported_cells` recovered one partial room on the same 172 selected
frames: 2.53677 by 2.99922 m, area 7.60833 m2, camera coverage 0.366279. Height remains
unavailable. The proposal-count prediction was met; property completeness and
centimetre accuracy remain unverified. Unit checks reject a missing whole boundary
and an unvisited candidate. Later pose-refinement experiments are separate runs.
