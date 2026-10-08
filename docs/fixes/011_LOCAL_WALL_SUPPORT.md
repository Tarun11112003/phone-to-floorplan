# Local wall support correctness correction

This is a development correction, not the assessment's qualified physical Fix Loop.
No independent survey or failing measured accuracy gate is available here.

## Failure reproduced before implementation

The existing wall proposal criterion required 250 points in a hypothetical global
sample of at most 18,000 points. Adding 250,000 distant floor points to the same
observed 4 x 3 m software-control room reduced its wall proposals from >=3 to 0.
The new invariance regression failed before the change (1 failed in 3.44 s).
Those distant surfaces add no evidence about the unchanged local walls.

## Alternatives evaluated

Pinned Reference A's height-band density proposal idea and Reference B's
projection-mode idea were evaluated using our frozen supplied ceiling cloud.
Open3D planar patches did not improve completeness. Local density/Hough
proposals found two cells at 14.33% camera coverage; a more permissive, narrower
height-band/48-seed projection experiment found six cells at 64% coverage but
104 dangles. More cells do not prove correct rooms. These larger experimental
changes were not adopted.

## Selected minimal correction

`layout._supported_wall_proposals` now accepts locally supported candidates with
>=250 raw consensus points, >=40 occupied 10 cm cells, >=0.9 m observed height
span, >=0.6 m observed length span, <=2.5 cm fit residual and the existing
vertical/orientation guards. Global-equivalent support remains the ranking
weight so added proposals do not change ranking units. The old global policy is
retained for identical-cloud comparisons.

The original height band, bounded seed budget, plane refitting, observed finite
intervals, small corner-gap limit, traversed-door rule, room filters and
incomplete-status guards remain. No new runtime dependency, fixed sensor bias,
survey scale, unobserved rectangle or raster fill is introduced.

The local support thresholds are disclosed development choices, not centimetre
accuracy guarantees. A tall cabinet can still supply a plane: independent room
semantics, held-out physical dimensions and false-boundary validation remain
required. Existing measurement/cache producer hashes invalidate old calibration.

## Executed validation

- Missing boundaries, furniture/columns, inclination, ceilings and openings:
  **21 passed in 27.41 s** after the first logical change.
- Added cluster-spatial-support and legacy-policy guards; full suite:
  **143 passed in 57.34 s**.
- Identical frozen ceiling cloud, retained old policy versus new policy:
  one cell/8% coverage versus two cells/24% coverage; both incomplete and zero
  adjacency. Dangles increased 45 to 64. Geometry-only evidence is under
  `demo/phase3_sync_boundary/local_support_core_ceiling`.
- Fresh raw all-case replay completed: 3/3 cases and 15/15 checks. Ceiling
  coverage is 36.67%; single/floor remain 34.78%/9.09%, all incomplete.
  Fragmentation/runtime increase and numerical subdivision sensitivity remain
  risks, recorded in `PHASE3_SYNC_BOUNDARY_PASS.md`. Saved float32 cloud replay is
  not a replacement for the complete pipeline replay.

## Next acceptance evidence

Identify missing/extra boundaries against independently annotated geometry and
laser/tape dimensions. Do not call internal coverage a surveyed accuracy delta
or a 25% qualifying Fix Loop improvement.
