# Final frame31 replay: reproduction failure and diagnostic closure

Continue [batch027](027_registration_support_audit.md), using
[component research](../alternative_approaches.md) and the retained native
stage/history records. This is the final registration-chain diagnostic.

**The native replay does not reproduce snapshot27. Its intermediate states
cannot establish where the original geometry discrepancy arose. Close this
investigation as inconclusive at the registration/triangulation/refinement level.**
No production defect is proven, no reconstruction fix is made, and XFeat stays
experimental. Do not trace earlier frames or vary solver settings to force a result.

## Controlled experiment

Run one native replay from saved29-view snapshot26, using frame31 (native image28)
and the same32 RGB inputs, XFeat correspondences, original verified rows and
fixed supplied intrinsics. Rebuild the pose-free correspondence cache with the
frozen PyCOLMAP4.2.1 options. Odometry and sensor poses are not read or supplied
to reconstruction. No matching, verification, threshold or guard changes.

Capture the native model before registration, after accepted registration, after
triangulation, after local refinement, after global refinement, after frame
filtering, and after color extraction. The original native log explicitly records
global refinement between frame31 registration and snapshot27; this is included
with unchanged options and the default normalization behavior. No gauge or private
mapper-state changes are attempted. Native selection is `[28,31]`, with107 visible
features /479 observations, matching the retained registration log. Frame filtering
removes0 frames. Triangulation reports171 added observations.

The saved initial model reproduces snapshot26 exactly under the existing strict
model-state definition: cameras, frames, points and rigs match byte-for-byte;
all29 complete image-record payloads match, with record ordering alone different.
No numerical tolerance is introduced. All32 original RGB hashes, six database
table row digests and fixed intrinsics remain unchanged. The copied database has
no sensor/pose-prior data. The final read-only auditor verifies1329 prior pinned
entries and preserves source models and historical evidence.

## Captured states and failed reproduction gate

| Saved state | Registered views | Sparse points |
|---|---:|---:|
| Before registration |29|6024|
| Accepted registration |30|6024|
| After triangulation |30|6090|
| After local refinement |30|6082|
| After global refinement |30|6045|
| After frame filtering |30|6045|
| After color extraction |30|6045|
| Required retained snapshot27 |30|6055|

These counts inventory an unsuccessful control; they are not geometry improvements.
The strict final gate raises `Refinement does not reproduce native model bytes`.
Cameras and rigs match the retained snapshot27; frames, images and points differ.
The replay emits37 linear-solver warnings during global refinement, versus0 in
the original frame31 interval. Original upstream warnings are excluded from this
interval comparison. The native replay process exits1. There is only one native
attempt; no solver/gauge/order variations or earlier-frame replays follow it.

Reading and writing model binaries preserves the saved input model state, but
that does not prove restoration of every piece of in-memory mapper/solver history.
The failure demonstrates a continuation/reproducibility limitation for this
checkpoint. It does not identify a faulty production solver, feature identity,
intrinsic parameter or triangulation rule. No particular private-state, gauge or
ordering explanation is asserted as the cause.

## Stage attribution and classification

The earliest trusted saved state for34 of37 accepted frame34 landmarks remains
**snapshot27, after frame31 registration, triangulation and local/global refinement**.
Batch027's retained sensor-reference discrepancy is observable there. This run
cannot distinguish accepted registration, point creation, local refinement or
global refinement as its original point of onset, because the required final
state does not reproduce. No intermediate pose/depth sensor audit is performed.
Do not report new rotation, direction or relative-depth values from this control.
Separately, the previous exact frame34 replay already establishes that31->34
orientation disagreement is present at accepted frame34 registration, before
triangulation/local refinement; this final frame31 control does not overturn it.

Classification for this final diagnostic: **4 — insufficient trusted saved-state
evidence to localize the original substage**. The previously supported explanation,
**3 — inherited local geometry/model bias with concentrated support**, remains a
hypothesis. This is distinct from proving insufficient raw sensor observations;
the limitation here is trustworthy replay provenance and unquantified sensor/model
uncertainty. No concrete, reproducible production software defect is established.

Retained, unchanged findings from batches026/027:

-34/37 accepted landmarks first appear in snapshot27; the other3 predate it.
- Accepted-frame34 / local-refined / final31->34 rotation disagreements remain
  7.842073 /6.590696 /6.520814deg against withheld odometry.
- Source27->31 rotation disagreement is4.206027deg, normalized motion length
  ratio1.318052; accepted native/sensor-reference depth median ratio1.194292.
- Identity ambiguity is limited and does not account for the systematic discrepancy;
  support is spatially concentrated. Sensor covariance and independent geometry truth
  are unavailable, so those discrepancies are not physical-accuracy verdicts.
- The retained final baseline remains32 registered views,6187 sparse points and
  native mean reprojection residual1.480503px. No shipped before/after improvement.

**Registration investigation: CLOSED as inconclusive/evidence-limited.**
This closes the diagnostic chain, not the geometry defect or assessment requirement.
Keep production SIFT, all guards, existing geometry and previous evidence unchanged.
No matcher adoption, filtering intervention, sensor-assisted correction, commit
or push is justified. Prior alternatives are reused as research; no repeated
alternative-implementation or public matcher investigation is performed.

## Reproduction, validation and artifacts

Original captured native command, run once from the repository root:

```powershell
.\.venv\Scripts\python.exe demo/phase3_frame31_final/native_api_probe.py
```

This retained probe requires the supplied local experiment fixtures and an absent
`demo/phase3_frame31_final/probe` directory. It deliberately refuses to overwrite
the current control. Do not rerun or delete retained evidence as a next step.
Preserve its source/log/model hashes in the compact summary.

The new isolated auditor inventories the already saved control, enforces the
existing exact gate, and never runs reconstruction or opens sensor files:

```powershell
.\.venv\Scripts\python.exe scripts/diagnostics/audit_final_frame31.py --out demo/phase3_frame31_final/saved_audit_check.json
.\.venv\Scripts\python.exe -m pytest -q tests/test_final_frame31.py tests/test_registration_support.py tests/test_registration_stage.py tests/test_registration_snapshots.py tests/test_late_landmarks.py tests/test_mapping_only.py tests/test_fixed_intrinsics.py tests/test_transition_odometry.py tests/test_xfeat_context.py tests/test_transition_context.py tests/test_transition_tracks.py tests/test_transition_matchers.py
.\.venv\Scripts\python.exe -m pytest -q
```

Use a fresh audit JSON filename. Its exit2 explicitly means the replay gate failed;
an executed audit is not a successful reconstruction experiment. Expected recorded
output: `snapshot27_reproduced=false`, `intermediate_interpretation_allowed=false`,
`native_solver_warnings=37`, `investigation_closed=true`.

Initial evidence-parser tests:1 failed /143 passed. The generic count-row parser
mistook `support 107 479` for a stage. Restrict the diagnostic parser to the seven
explicit capture labels; retain the initial failing test/audit logs. This changes
only the new auditor, not reconstruction or the native experiment. Final targeted
tests: **144 passed in3.99s**, including15 new exact-gate/log-provenance cases.
Full current-worktree regression: **326 passed in45.67s**, zero failures. Results
are retained in `full_tests.log` and the compact summary. Do not confuse test
success with the failed native reproduction gate. No further native experiment
is run.

New files: [audit_final_frame31.py](../../../scripts/diagnostics/audit_final_frame31.py),
[test_final_frame31.py](../../../tests/test_final_frame31.py), this report, and
[phase3_frame31_final_summary.json](../../../benchmarks/results/frame31_final_summary.json).
Six engineering documents receive a current closure notice; their previous
contents remain intact as historical records. Large diagnostic artifacts remain
ignored under `demo/phase3_frame31_final`. Existing uncommitted work is preserved.

## Requirement impact and remaining acceptance dependencies

REQ-03/05/10/27/29 remain partial. This establishes an honest stop condition and
reproducibility boundary, not reliable whole-property video geometry. Floor
coverage remains25/176 with151 uncovered samples; the0.702677m ceiling-boundary
shift remains unvalidated. No new connecting boundary is introduced.

Same-property surveyed three-tier captures and repeats, calibrated uncertainty,
opening/damage truth, measured drift/Fix Loop evidence, consumer-app comparison,
official schema/gate details and cold/walk-in acceptance remain outstanding.
Software tests and internal consistency do not demonstrate centimetre accuracy or
assessment acceptance. Resume the separate acceptance roadmap; do not extend this
registration-chain investigation without new independent evidence and authorization.
