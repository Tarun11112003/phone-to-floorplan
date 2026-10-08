# Prospective fix: expose assignment output coverage in every run report

Scoring target: walk-in readiness (30%) and compliance coverage
(10%). Source requirements are mapped in `docs/ASSIGNMENT_BRIEF_MAP.md`.

## Baseline and failure

The current HTML review report shows estimates and generic remaining requirements,
but has no per-deliverable checklist tying a cold capture to the assignment's
dimensioned rooms, ceiling, openings, property stitch, damage, concealed flags,
scope, calibrated intervals, rendered plan and published schema. A cold photo run
on two 256x192 ARKitScenes RGB frames (`demo/walkin_contract_e2e/captures/living/`)
produced `no_model`, registered 0/2 images, and no plan. It did emit a run ledger
and HTML report, but the report did not make the full required-output coverage
machine-readable. Baseline `floorplan/assessment.py` SHA-256:
`fa6c183ba8ac83e448d57dae9902a98c7372a0e39dc60f135a0a4ed1373bd841`.

Input SHA-256 values:

- `41418140_1285.995.png`: `7bc2af64726844f2bc4ddc8e771877342fd105bce387a8c156399aec65efbdb5`
- `41418140_1289.994.png`: `bf1b4283002a2e7c21000066933d5761df8919fedd2b3ebdce98de646927055d`

## Hypothesis and prediction

Hypothesis: the report's generic caveats make it too easy to miss which mandatory
outputs a particular cold run omitted. A generated coverage artifact plus an HTML
table will expose missing, partial, uncalibrated and externally blocked outputs
for the exact run without implying an accuracy pass.

Prediction: after the change, the same capture still fails honestly with no plan;
`contract_coverage.json` and `report.html` list all required output groups, classify
their state, link the evidence context, and explicitly leave the published schema
pending. The run ledger hashes the new sidecar as a deliverable.

Falsify if any missing output is marked passed/present, if the report and JSON
coverage disagree, if adding the checklist alters reconstruction geometry/status,
or if a covered item is omitted from the supplied HTML output contract.

## Verification

Run assessment/report unit tests, then repeat the exact `run-capture` command on
the same two source images with a fresh output directory. Compare reconstruction
status and registration counts to baseline; inspect the new checklist in JSON and
HTML. This increment improves auditability only. It does not fix sparse-photo
registration, absolute scale, whole-property photo stitching or cm accuracy.

## Measured outcome

Targeted assessment tests passed (5/5). The fresh after-run reproduced the baseline
failure exactly: `no_model`, 0/2 registered, no plan. Runtime was 0.81 s versus
1.28 s at baseline; this variation is not an algorithmic speed claim. The after-run
contains all 12 coverage rows in `result/contract_coverage.json` and the HTML report;
the baseline contains neither. The rows correctly mark room plan/area/ceiling/render
as not produced, scale intervals incomplete, and the published schema pending. No
coverage row claims accuracy is validated. The new report did not alter the geometric
result, as predicted.
