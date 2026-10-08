# Independent post-hoc odometry audit of the 29-view joint RGB model

This audits the saved candidate from
[batch 020](020_xfeat_lighterglue_context.md); matching and reconstruction are not
rerun. Read [the component research](../alternative_approaches.md) first.
The question is whether camera connectivity also represents sensor-consistent
geometry. Odometry is a withheld validation reference, not physical survey truth.

## Decision

**C: the across-transition geometry is contradicted by supplied odometry.**
The early portion is substantially more consistent than the later portion.
Retain the files as experimental evidence; reject this joint model for production
use and preserve production SIFT. Exact repeatability and low pixel residuals
do not make this result physically trustworthy. No production bug is established
by this audit; no reconstruction logic, thresholds, guard, or pose is changed.
No commit or push is appropriate for a rejected experimental result.

## Identity and coordinate convention

- Verify 383 unique retained file hashes from the batch 019/020 ledgers before
  and after the audit, including databases/WAL, models, images, source modules,
  experiment records and production. Mutable SQLite SHM is already excluded by
  the retained evidence methodology. Source MP4/odometry hashes also match the
  earlier synchronization audit.
- Reuse cached full-video integer-PTS timing, and recompute both index hypotheses
  through the existing `capture_sync.compare_sensor_timing` guards. Playback
  has 1,714 frames; encoded/scanner odometry has 1,715 frames. Only playback
  index **k -> sensor frame k+1** and encoded index **k -> sensor frame k** pass.
  Same-index playback fails; no nearest sensor timestamp is silently substituted.
- Playback clock rate is 0.999846666897, offset -0.016696436572 s, maximum residual
  29.742528 microseconds. The existing frame-identity limit is 4.167239 ms.
  Encoded shift zero also passes, with maximum residual 29.700671 microseconds.
- Resolve each retained image timestamp to one exact playback PTS. Maximum
  rounding difference is 0.333333 microseconds, within half the retained
  six-decimal digit (0.5 microseconds). This is a timestamp serialization check.
- Decode only those 32 selected indices afresh under both playback and encoded
  conventions. **All 64 witnesses are exactly equal in RGB pixel arrays** to
  their retained 1,920 x 1,440 images. PNG metadata/container bytes need not agree.
  Both conventions identify the same actual images, not merely nearby times.
- Read CSV with its comma-space formatting, require contiguous frame IDs,
  increasing timestamps, finite poses and the existing 0.01 quaternion-norm
  validity bound. Normalize `qx,qy,qz,qw` using the existing intake convention.
- The official scanner writer at revision
  `ec3e1dc9d33f8df2289ede6a5c59f7991d1a6bbb` composes its camera transform with an
  optical-axis conversion before exporting its quaternion. An additional ARKit
  axis flip is not justified. This supports the existing intake convention;
  this revision is a source witness, not proof of the supplied capture's app build.
  [Pinned writer](https://github.com/strayrobots/scanner/blob/ec3e1dc9d33f8df2289ede6a5c59f7991d1a6bbb/StrayScanner/Helpers/OdometryEncoder.swift),
  [scanner format](https://github.com/strayrobots/scanner/blob/ec3e1dc9d33f8df2289ede6a5c59f7991d1a6bbb/docs/format.md).
- COLMAP stores world-to-camera rotations; invert them to camera-to-world before
  comparing motion. Use its saved projection centers without modifying them.
  [COLMAP model conventions](https://colmap.github.io/format.html).

The source writer is retained only as a read-only witness in ignored `demo`,
SHA256 `3613d3521833b5137763578cc64f8604b8b4a73aceff3b02e7a980d5d1740bd3`.
No upstream code is incorporated into the implementation.

## Audited views and metrics

All **29 registered views**, all **28 consecutive registered-view motions**, and
all **23 consecutive motions inside the 24->27 transition** are audited. The
sequence includes frame 16/19/22/23/24, all 20 retained bridge views, frame 25/26/27
and frame 28. Context 31/34/37 remains unregistered; it is not extrapolated.
Exact image/PTS/sensor-frame mappings and every measured relative motion are
retained in `audit.json`.

| Anchor | Playback time, s | Sensor frame |
|---|---:|---:|
| frame 16 | 7.516666667 | 346 |
| frame 19 | 9.033333333 | 420 |
| frame 22 | 10.550000000 | 494 |
| frame 23 | 11.050000000 | 517 |
| frame 24 | 11.550000000 | 539 |
| frame 25 | 12.066666667 | 562 |
| frame 26 | 12.566666667 | 587 |
| frame 27 | 13.066666667 | 610 |
| frame 28 | 13.583333333 | 634 |

For camera-to-world rotation R and center C, compare relative orientation
R_i^T R_j and local translation R_i^T(C_j-C_i). These cancel each reconstruction's
independent world origin and rotation. Report rotation geodesic error and local
translation direction angle. Sensor distances are metres; monocular model
distances remain explicitly **model units**.

Compare dimensionless lengths after dividing each system's displacement by its
own common pre-transition **19->24** displacement. The reported relative length
ratio is candidate-normalized length / sensor-normalized length; one means equal
relative magnitude. The reference is 8.293933 model units and 1.036796 sensor
metres. This does not rescale, align, optimize, or output a corrected model and
does not establish metric reconstruction scale. No absolute trajectory-error
metric is calculated by comparing unrelated world-coordinate origins.

| Span | Relative rotation error | Translation direction error | Relative length ratio |
|---|---:|---:|---:|
| 19->24, pre-transition reference | 0.969732 deg | 4.329983 deg | 1.000000, by definition |
| 22->27, direct group connection | 25.129064 deg | 49.341816 deg | 1.190763 |
| 23->27, direct group connection | 24.931597 deg | 40.280853 deg | 1.459716 |
| 24->27, target endpoints | **24.771982 deg** | **34.595082 deg** | **1.496456** |
| 24->28, cumulative late endpoint | **34.735237 deg** | **66.479466 deg** | **3.721359** |
| 27->28, final consecutive step | 11.639250 deg | 47.762522 deg | 10.872672 |

On 24->27 the model rotates 119.686090 deg while odometry rotates 98.466582 deg.
Even these relative rotation magnitudes disagree by 21.219508 deg; that mismatch
does not depend on a constant optical-axis convention. Endpoint sensor distance
is 0.566490 m; candidate distance is 6.781461 model units. Do not compare those
raw numbers as a metric error.

Within the transition, consecutive orientation error is median 0.418971 deg,
p95 3.578859 deg, maximum 3.960849 deg. The small local errors accumulate into
the much larger endpoint disagreement. Local translation direction errors are
median 26.888019 deg, p95 57.764145 deg, maximum 59.992279 deg; several sensor steps
are only millimetres, making their direction particularly sensitive to unknown
sensor/reconstruction noise. Do not apply that caveat to the 0.566 m endpoint as
though its large disagreement were a proven rounding effect.

Varying both 24/27 sensor associations independently by +/- one frame leaves
orientation disagreement **23.896325..26.351143 deg** and direction disagreement
**34.038207..35.805007 deg**. Exact pixel identity already establishes the primary
pairing; this wider sensitivity probe is not an acceptance tolerance.

A dense CSV check through frames 539..610 covers all 71 sensor steps. Timestamp
spacing is 16.669083..33.338625 ms; maximum position step is 0.021072 m and maximum
rotation step 3.112453 deg, with maximum speed 0.660414 m/s and angular rate
94.361004 deg/s. All quaternion norms lie in 0.999999912..1.000000081. This does
not reveal a CSV discontinuity accounting for the observed joint-model error;
it does not certify sensor tracking accuracy. The sampled sensor path length is
0.655081 m, distinct from endpoint displacement. The extended 539..634 path is
0.862084 m over 95 sensor steps.

## Calibration observation and limits

The saved candidate's focal values fall progressively after 12.3 s:
1,507.728 px at bridge 12, 1,268.369 at frame 26, 978.288 at frame 27 and 884.083
at frame 28. The full model range is 884.083..1,545.651 px. Corresponding sensor
focal values over registered views stay in **1,587.494..1,608.282 px**. Images are
pixel-identical at the same resolution, so a resize does not explain that gap.

The larger orientation and translation disagreements grow in this same later
segment. This is evidence of a plausible **intrinsic/pose ambiguity**, alongside
the already recorded weak/conflicting correspondence support and solver warnings.
Correlation does not prove that focal freedom caused the wrong geometry. A
controlled reconstruction experiment is required before fixing or adopting a
camera policy. No software arithmetic/convention bug is found here.

There is no supplied pose covariance or independently surveyed pose trajectory.
The assessment's opening, ceiling and wall tolerances are not camera-pose
tolerances. Do not invent a rotation/translation acceptance band or convert this
audit into a centimetre-level claim. The C classification is an evidence-based
sensor contradiction, rather than a formal physical gate failure.

## SIFT comparison and reproducibility

Retained SIFT registers 11 earlier views and has no joint target-group model.
On the ten identical consecutive common-view spans, median rotation disagreement
is **0.132797 deg SIFT / 0.150657 deg XFeat**, and median translation-direction
disagreement **19.981035 / 11.664636 deg**. Relative length ratios span
**0.970840..2.657618 / 0.980623..1.466143**. XFeat improves some early local motion
estimates, especially directions at tiny steps, but that does not validate its
later bridge. SIFT is not claimed to solve the transition that it never registers.

Two fresh audit directories independently reproduce RGB witnesses, alignment,
all pose metrics and control comparisons exactly, excluding measured runtime:
**27.064 / 20.786 s**. Within each audit the two saved independently reconstructed
XFeat trials also produce exactly equal results. No inference is repeated. The
candidate still has **29 views, 5,455 points, 1.486099 px mean reprojection error**;
connectivity and geometry are not altered. No before/after reconstruction gain
is claimed: this batch changes the evidence and adoption decision only.

## Validation and reproduction

```powershell
.\.venv\Scripts\python.exe scripts/diagnostics/audit_transition_odometry.py --out demo/phase3_transition_odometry/audit1
.\.venv\Scripts\python.exe scripts/diagnostics/audit_transition_odometry.py --out demo/phase3_transition_odometry/audit2
.\.venv\Scripts\python.exe -m pytest -q tests/test_transition_odometry.py tests/test_xfeat_context.py tests/test_transition_context.py tests/test_transition_tracks.py tests/test_transition_matchers.py
.\.venv\Scripts\python.exe -m pytest -q
```

Use new output directories when reproducing; existing outputs cannot be replaced
and output cannot overlap models, timing or source data. Tests cover optical
relative-pose calculations under independent world gauges/scale, nonzero motion
errors, exact RGB witnesses and wrong-pixel rejection, playback off-by-one
identity, bad PTS/order/duplicates, invalid quaternions/frame IDs, changed hashes,
and safe output paths.

- Targeted: **50 passed in 4.05 s**, including **16 new audit cases**.
- Full regression: **232 passed in 64.60 s**; zero failing tests.
- The first targeted command referenced nonexistent `test_video_bridge.py` and
  failed collection without running tests. The corrected command above passes;
  the full suite includes the actual `test_video_bridge_trial.py` and sync tests.
- An initial disposable read-only numerical probe omitted CSV whitespace handling
  and stopped with a missing-key error. The retained auditor/tests handle it;
  this was diagnostic setup, not a production ingestion bug.

Files: `scripts/diagnostics/audit_transition_odometry.py`, `tests/test_transition_odometry.py`,
this record, [compact hashed evidence](../../../benchmarks/results/transition_odometry_summary.json),
and current research/status/operations/roadmap/decision/design notices. Raw audit
JSON, fresh RGB witnesses and source-convention witness stay in ignored `demo`.
Existing batch 019/020 files and all unrelated uncommitted work are preserved.

## Requirements and next step

REQ-03/05/10/27/29 remain **PARTIALLY IMPLEMENTED**: video reconstruction,
common complete output, property adjacency, drift/ablation and measured wall
accuracy are not closed by this audit. The locally addressable validation
question is closed: joint connectivity is not sufficient to justify adoption.
No geometry, drift correction, benchmark Fix Loop or physical gate is shipped.

Floor coverage remains **25/176**, with 151 uncovered samples. The previous
**0.702677 m ceiling boundary displacement remains unvalidated**. Independent
survey, same-property three-tier/repeat/damage evidence, interval calibration,
consumer comparison, cold rehearsal and missing official specifications remain
outstanding. Sensor agreement would not replace them even if this audit passed.

The consolidated research does not justify adopting A/B architecture changes.
Their posed-video/calibration ideas concern genuinely available capture metadata;
they do not make this RGB-only model correct. No new matcher, structural backend,
restricted code/assets or production dependency is introduced. Existing pixel,
timing, registration and acceptance safeguards are retained.

**Single next technical step:** run an isolated **intrinsics-only remapping
control** on the retained 32-view XFeat feature/match database, holding the
supplied per-frame optical calibration fixed while withholding all sensor poses
and preserving verification/mapping thresholds. Compare its saved relative poses
through this same auditor. This tests the observed focal-degeneracy hypothesis;
it is not yet implemented or validated, and sensor-calibrated success would not
establish readiness for stock videos lacking that calibration.
