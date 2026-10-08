# Prospective fix: expose two-view geometry classifications

## Observed gap

The isolated RGB-only LightGlue + DISK trial increased matching support on the
failed four-view sequence but still produced no model. Direct inspection of the
same COLMAP databases shows that inlier counts alone omit useful context:
LightGlue's six pairs are classified `UNCALIBRATED` (COLMAP config 3), while
SIFT's six pairs are `PLANAR_OR_PANORAMIC` (config 6). The successful LightGlue
control registered 4/4 images and produced 305 points. These labels can help
separate pose-estimable geometry from planar/panoramic degeneracy, but do not
prove good parallax, metric scale, or a valid plan.

## Proposed change

Extend the existing read-only COLMAP matching diagnostics with a count by
two-view geometry configuration and a configuration label on each strongest
pair. Keep all mapper options, acceptance thresholds, and status decisions
unchanged. Do not make configuration labels a metric-quality claim.

## Falsification and validation

Unit tests must cover known configuration values and unknown future values.
Fresh RGB reconstruction outputs must agree with direct database counts, while
registered-image counts, sparse-point counts, geometry, and scale status remain
unchanged. The matcher experiment remains isolated and optional.

## Outcome

Implemented labels and counts in the existing read-only pair diagnostics. Direct
queries on the four saved trial databases agree with the emitted classifier:

| Run | Verified pairs | Geometry configurations | Registered | Sparse points |
| --- | ---: | --- | ---: | ---: |
| SIFT `start0` | 6/6 | 6 planar-or-panoramic | 0/4 | 0 |
| LightGlue `start0` | 6/6 | 6 uncalibrated | 0/4 | 0 |
| SIFT `start80` | 6/6 | 4 uncalibrated, 2 planar-or-panoramic | 4/4 | 60 |
| LightGlue `start80` | 6/6 | 6 uncalibrated | 4/4 | 305 |

Five targeted diagnostics tests and the full suite pass (50 tests). No mapping,
registration, or acceptance threshold changed. These classifications improve
failure triage but do not identify the exact initialization rejection or prove
parallax, metric scale, or room-plan correctness. Next photo-tier work should use
the assignment's actual 2–8 stills and surveyed dimensions when available; on the
provided RGB frames, test capture/viewpoint coverage and camera metadata before
considering weaker mapper guards.

A fresh end-to-end SIFT replay of the four `start0` RGB frames remained `no_model`,
0/4 registered, 0 points, and 6/6 verified pairs; all six were again labeled
`PLANAR_OR_PANORAMIC` with maximum 581 inliers. The classifier matches the saved
baseline and the failure remains honest.
