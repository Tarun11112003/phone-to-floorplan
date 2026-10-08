# Frame34 registration support: ambiguity versus inherited geometry

Continue [batch026](026_native_registration_stage.md), using
[component research](../alternative_approaches.md) as the primary record.
Do not repeat SIFT/DISK/XFeat matching experiments, calibration ablations, or
reference-repository research.

**The evidence favors inherited local geometry bias, reinforced by concentrated
support, over feature-identity ambiguity as the main explanation for31->34
disagreement.** This is a supported diagnosis against withheld sensor evidence,
not proof of a particular solver defect or independently measured accuracy.
No registration/filtering intervention or production adoption is justified.

## Scope and invariance

Audit the saved30-view snapshot27, the frame34 accepted-registration snapshot,
and the same retained XFeat database with fixed supplied intrinsics. No solver,
matching, verification, BA, pose correction, or new reconstruction is run.

Before reading odometry, require batch026's exact model-state reproduction,
all captured/source hashes, unchanged source-camera poses and landmark XYZ,
identical feature coordinates, and pose-free database rows. Build the native
correspondence cache from a fresh ignored database copy using the same settings.
Native registration previously changed only frame34's pose/associations; the
preceding cameras and inherited point coordinates remain exact. All1301 prior
pinned entries are unchanged. No production files or earlier experiments change.

The only new source inspection establishes exact candidate enumeration, using
the official [COLMAP4.2.1 registration implementation](https://github.com/colmap/colmap/blob/4.2.1/src/colmap/sfm/incremental_mapper.cc).
It gathers direct associations from registered views with valid camera parameters
and triangulated landmarks, deduplicating a landmark within one target feature.
Competing landmarks for the same feature remain separate candidate rows.
Saved observations are added from the accepted mask without overwriting an
already-associated feature. The internal RANSAC mask is not exposed by these
saved models. Retain the unmodified source/URL/hash under ignored diagnostics;
SHA-256 `ed54fd69e838bd189926110607bcb4ac5dc302b9840612447cc76612118f6969`.
No third-party implementation code is incorporated; prior alternatives are reused
as research, not adopted merely because their architecture differs.

## Candidate and identity accounting

| Quantity | Result |
|---|---:|
| Native visible target features |83|
| Distinct feature-to-landmark candidate rows |87|
| Unique inherited landmark IDs |86|
| Features with competing landmark IDs |4|
| Accepted feature observations / unique landmarks |37 /37|
| Features with no accepted association |46|
| Candidate rows not accepted |50|
| Accepted features with competing IDs |1|
| Source landmarks with repeated same-image feature identities |1, rejected|
| Accepted source-track identity collisions / duplicated landmarks |0 /0|

Do not conflate83 features,87 candidate rows and86 landmarks. The50 nonaccepted
rows touch47 feature IDs because the unselected alternative of an accepted
feature is included. The46 completely unaccepted features are the feature-level
comparison. Native cache filtering skips192 edges to unregistered views and316
edges to observations without landmarks; no origin camera is excluded as bogus.

Competing-ID features are19,79,773,923. Only79 is accepted: landmark9146;
alternative9215 is not accepted. Landmark9144 is proposed by two different
target features, but neither is accepted. Native association semantics preserve
these conflicts without incorrectly collapsing candidate identities.

Source landmark5577 includes frame25 features23 and5,5.625px apart; it is a
candidate for target feature88 and is rejected. Its inverse point associations
are consistent, but its multiple feature identities are a quality flag. This
does not prove which feature is wrong, a native software defect, or a cause of
the accepted pose. Only one accepted candidate also has a local verified triangle
conflict. Excluding flagged rows in descriptive summaries does not remove the
systematic geometry discrepancy; **no rows are removed from reconstruction**.

## Accepted versus nonaccepted support

| Diagnostic |37 accepted rows|50 nonaccepted candidate rows|
|---|---:|---:|
| Two prior views |28|16|
| More than two prior views |9|34|
| Positive depth under accepted native pose |37|39|
| Median native target projection residual |6.319157px|12706.343849px over39 positive-depth rows|
| Maximum source-track projection residual |3.270945px|3.267649px|
| Median of per-candidate sensor epipolar medians |2.688945px|268.186123px|
| Median sensor prior-only held-out prediction residual |9.420436px|5233.148588px|
| Hull fraction of target image |3.403854%|33.033562% over47 touched features|
| Occupied8x8 image cells |5|15|

All accepted observations have positive depth and residual at most11.840311px,
within the unchanged12px absolute-pose gate. Nonaccepted positive-depth rows
have residual at least13.337288px; eleven other rows are behind the camera.
The very large nonaccepted residuals reflect grossly inconsistent/off-image
projections; they are not a precision estimate. Sensor-epipolar distributions
also separate the accepted and most nonaccepted associations.

All37 accepted landmarks are seen in frame31;33 also in frame27.28 have only
those two prior views. Their maximum prior triangulation angles range
10.232793–13.127068deg, above the existing1.5deg filtering minimum. There is no
zero-parallax explanation. The fixed-landmark pose Jacobian has finite condition
number74.187255; this is not a joint geometry uncertainty estimate or a prescribed
acceptance threshold. The saved points are elongated, with smallest/largest SVD
ratio0.080481; they are not exactly planar or arithmetically singular.

The support plot (separate handoff: `demo/phase3_registration_support/registration_support.png`)
shows the accepted cluster around the cabinet handle/shadow and lower trim.
Cyan labels mark two sensor-plausible rejected wall observations. This display
helps assess concentration; it does not create correspondence ground truth.

## Withheld sensor checks and inherited-bias evidence

Reuse batch021's exact RGB witnesses and playback-index+1 sensor alignment.
Frame31 maps to sensor705;34 to773. Sensor poses enter only the post-hoc audit.
The auditor never fits or updates any reconstruction camera pose or point.

Intersect rays algebraically using only each inherited landmark's prior RGB
observations and corresponding withheld sensor poses/calibration. Frame34 and
all future observations are excluded from this diagnostic point calculation;
project the result into frame34 afterward. Keep singular/nonpositive geometry
explicit. These points are noisy sensor-based validation estimates, not corrected
reconstruction, physical measurements, or adopted output geometry.

Normalize sensor/model scale using the same19->24 displacement reference,
14.195672908 model units per sensor meter. No similarity transform or target
residual minimization is fitted. Compare each prior point's frame31 optical
depth between the saved model and sensor ray estimate:

| Accepted support subgroup |Count|Median native/sensor-reference depth ratio|Median held-out sensor prediction residual|
|---|---:|---:|---:|
| All accepted |37|**1.194292**|9.420436px|
| No competing landmark identity |36|**1.194102**|9.894539px|
| No local triangle conflict |36|**1.194102**|8.993692px|
| More than two prior views |9|**1.174279**|13.989066px|

All37 depth ratios lie between1.163624 and1.211253. This systematic discrepancy
persists outside the flagged identities and is already present in the input
landmarks. It is not an independently demonstrated19.4% physical depth error.
The corresponding source motion is already sensor-inconsistent before frame34:

| Relative span in saved input geometry |Rotation disagreement|Direction disagreement|Normalized length ratio|
|---|---:|---:|---:|
| Earlier control22->23 |0.038625deg|0.081491deg|0.991706|
|27->31 |**4.206027deg**|12.260180deg|**1.318052**|
|28->31 |4.291577deg|9.267045deg|1.293224|
|24->31 |6.286828deg|12.805577deg|1.061213|
| Accepted31->34, unchanged |7.842073deg|10.039021deg|0.938172|

Hold the inherited points fixed and project them under sensor-relative31->34
motion, anchored in frame31 with the declared19->24 scale. Their median target
residual becomes83.630263px. This shows incompatibility between the saved local
geometry and sensor reference under that scale; it is not a proposed sensor
correction. Native reprojection can be small while this consistency check fails.

Not every rejected candidate is bad. Target feature386/landmark8867 has81.736537px
native residual but3.149744px prior-only sensor prediction residual; feature1765/
landmark9062 has64.738095px native versus9.807629px sensor prediction residual.
Both have unambiguous IDs and prior frame31 support. Their sensor epipolar medians
are0.988515/1.727403px. These examples strengthen the geometry-bias explanation
and caution against treating the native inlier set as correspondence truth.
They still do not establish independent correct labels or a faulty RANSAC routine.

Reading the already-retained native history shows **34 of37 accepted landmarks
first appear in snapshot27**, the frame31 registration/refinement interval.
Two first appear in snapshot25 and one in24. This identifies the next missing
stage evidence; the saved snapshots cannot separate point creation from local
and global refinement within frame31's interval.

## Root-cause classification and decision

Correspondence ambiguity exists, especially in the nonaccepted input. The native
guards reject the repeated source identities and most sensor-inconsistent rows.
36 accepted features have a single inherited landmark, no accepted source track
contains repeated-image identities, and the depth discrepancy persists without
the one competing-ID observation or one triangle-conflict observation.

The strongest explanation is **inherited local pose/depth inconsistency combined
with concentrated, mostly two-view support**. This better explains the systematic
accepted-set discrepancy than a single ambiguous identity. Matching noise,
sensor/calibration error and nonlinear pose sensitivity remain possible
contributors; no covariance or independent physical truth distinguishes their
causal shares. Do not claim the sole or proven primary physical cause.

No feature indexing, unit conversion, fixed-intrinsic mutation or native candidate
collection bug is found. The audit provides no evidence-backed deterministic
registration change. Do not tighten/relax gates, discard short tracks, introduce
sensor poses, or adopt XFeat based on this result. Keep production SIFT and all
geometry/acceptance guards unchanged. No production fix, commit or push is made.

## Tests, evidence and reproducibility

- Initial focused suite:36 passed in1.65s, before adding a source-conflict reporting
  case; final relevant suite: **129 passed in2.94s**, including13 new tests.
- Full current-worktree regression: **311 passed in44.63s**, zero failing tests.
- Two authoritative read-only audits exit0; candidate rows, groups, source motion
  metrics and reproduction checks repeat exactly. Runtimes5.840/5.587s.
- Source reconstruction,32-view/6187-point final baseline and native1.480503px
  mean error remain unchanged. Accepted/local/final rotation disagreement stays
 7.842073/6.590696/6.520814deg. There is **no shipped before/after improvement**.

Preserve two preliminary diagnostic failures. The first API probe cannot
round-trip the native serialized empty-set string into typed cache options;
build those options from the frozen mapping fields instead. The first full audit
stops because its initial diagnostic guard rejects the source repeated-feature
track. Correct only the auditor to report this quality flag, keeping all source
observations. The final audits use fresh directories. Neither failure indicates
a production defect or modifies a reconstruction.

Use fresh output names; retain native stdout/stderr as UTF-8 with Python
`subprocess.run(...,stdout=log,stderr=STDOUT)`:

```powershell
.\.venv\Scripts\python.exe scripts/diagnostics/audit_registration_support.py --trial demo/phase3_preregistration/trial1 --out demo/phase3_registration_support/audit3
.\.venv\Scripts\python.exe scripts/diagnostics/audit_registration_support.py --trial demo/phase3_preregistration/trial2 --out demo/phase3_registration_support/audit4
.\.venv\Scripts\python.exe -m pytest -q tests/test_registration_support.py tests/test_registration_stage.py tests/test_registration_snapshots.py tests/test_late_landmarks.py tests/test_mapping_only.py tests/test_fixed_intrinsics.py tests/test_transition_odometry.py tests/test_xfeat_context.py tests/test_transition_context.py tests/test_transition_tracks.py tests/test_transition_matchers.py
.\.venv\Scripts\python.exe -m pytest -q
```

Retained experiments and ignored fixtures are required; this is not a clean-clone
rehearsal. New isolated code: [audit_registration_support.py](../../../scripts/diagnostics/audit_registration_support.py)
and [test_registration_support.py](../../../tests/test_registration_support.py).
Evidence: [compact manifest](../../../benchmarks/results/registration_support_summary.json),
`demo/phase3_registration_support/audit1_final/audit.json` and `audit2_final`,
the exact-repeat comparison, support plot, source provenance and logs.

REQ-03/05/10/27/29 remain partial. The diagnostic explains why connectivity and
native reprojection alone cannot validate video/property geometry. Floor coverage
remains25/176 and the0.702677m ceiling-boundary movement remains unvalidated.
Measured three-tier property/repeats, calibration/uncertainty, openings/damage
truth, drift/Fix Loop, consumer comparison, official schema/gates and cold/walk-in
evidence remain outstanding. No centimetre accuracy or assessment acceptance.

**ONE next technical step:** replay native frame31 registration from the saved
29-view snapshot26, capture accepted pose and newly triangulated landmarks before
local/global refinement, and require unchanged refinement to reproduce snapshot27.
This locates where the34 newly appearing, depth-biased support landmarks acquire
their discrepancy; sensor poses remain post-hoc only.
