# Final assessment QA and handoff

**Engineering handoff: ready for review. Assessment acceptance: NOT READY.**
Development is closed. Packaging/documentation changes do not resolve physical
benchmark gaps or incomplete reconstruction. [Compliance](ASSIGNMENT_COMPLIANCE.md)
is the requirement-by-requirement status; [QA receipt](evidence/final_qa.json)
records measured checks and output hashes.

## Initial state and corrections

The previous pass added README, requirements, architecture/results/compliance,
five-page report, evidence/source packages and documentation commits. Direct Git
audit found no production-code edits in those documentation commits. However,
24 tracked modifications and 141 untracked files remained, including required
runtime modules, CLI flags, schema changes, tests and replay utilities. An archive
of the previous HEAD did not expose the documented assignment-profile flag.
The tested worktree and a clone were different. A source snapshot did not solve
that submission defect.

The existing frozen implementation and dependent tools/tests are now tracked in
`1c57676`. No reconstruction algorithm/guard was changed in final QA. Production
source byte hashes match the initial QA baseline. Subsequent changes are limited
to installer/package/report code, package integrity tests and documentation.
Experimental tools remain experimental even though they are tracked.

## What was actually checked

| Check | Result | Scope / limitation |
|---|---|---|
| Existing baseline regression | 390 passed, 50.17 s | Developer dependency environment |
| Fresh Windows Python 3.12 bootstrap | PASS, 244.436 s | Network and pre-existing wheel cache; not independent cold machine |
| Fresh dependency consistency | PASS, pip check | No broken requirements |
| Fresh full regression | 396 passed, 48.01 s | Includes six new packaging checks; no experimental weights needed |
| Production supplied capture | Exit 1, partial; internal schema valid | 300 frames, 202,477 points; not assessment pass |
| Capture runtime | 221.196 s total command / 69.057 s reconstruction ledger | Existing environment; excludes physical capture/transfer/setup |
| Written geometry | 12 room/cell hypotheses, zero accepted heights, zero adjacency | Not independently established physical room count |
| Committed checkout + fresh dependencies | Exit 1, same readiness/counts; 211.239 s command | Actual committed module origin verified; dataset junction-mounted |
| Technical report | Five pages; render/evidence validation PASS | Visual QA; maximum six-page delivery requirement |
| Source/evidence integrity | Original and published-byte hashes retained | Not exact native every-number regeneration |
| Python/tool inventory | 157 files audited | Production/test/evaluator/experimental/diagnostic classification |

The first fresh install attempt failed after dependency installation because
pip's update notice on stderr became a terminating Windows PowerShell error in
a redirected log. The bootstrap now suppresses that notice; the corrected command
passed in a different fresh environment. Real nonzero capture readiness is not
suppressed in evaluator instructions.

The fresh-checkout run reproduced the same aggregate metrics. Arrays were not
byte-identical: maximum nearest-cloud distance was 1.215e-13 m and maximum
matched-corner delta was 3.258e-14 m. These are observed numerical rerun
comparisons, not an independent physical repeat or accuracy result. No solver
change or additional reconstruction investigation was performed.

## Production and evidence boundaries

SIFT is the production RGB baseline. MoGe, DISK/LightGlue, XFeat/LightGlue,
fixed-intrinsics/mapping controls and denser sampling are not promoted. RGB
registration is CLOSED as inconclusive. The stride-4 LiDAR trial was rejected.
room_2 local floor/ceiling acceptance remains evidence-limited. The 0.703 m
footprint notch is unvalidated, not a measured ceiling-height displacement.
No thresholds, geometry or solver were changed to improve the handoff's appearance.

Public evidence removes personal path prefixes/unnecessary development dates;
numeric measurements, sensor timing and original producer/input hashes are
preserved. Private original records and retired scratch helpers are archived
locally and excluded from the handoff. See [publication provenance](evidence/publication_provenance.json).
A historical input hash may name original private bytes rather than its portable
publication copy; do not ignore those differences during native replay.

## Cleanup and Git

[Python inventory](REPOSITORY_HYGIENE.md) explains retained files and each of the
14 retired one-off documentation helpers. They had no public import/command
references and were superseded by tracked tools. Their exact original bytes were
archived as text. No required production/reproduction/diagnostic Python file or
raw evidence was deleted. Local caches/data/build environments are Git-excluded.
The prior detailed personal queue remains private; the public pending page points
to final compliance. Commit history was not rewritten; nothing was pushed. This local repository has
no configured remote. The final handoff includes a Git bundle so process evidence
can be reviewed without depending on an older GitHub checkout. Original Git
history is retained; privacy cleanup applies to final publication files, not a
rewritten commit history.

## Remaining assessment blockers

- Whole-property floor completeness, correct adjacency and strict photo/video
  metric stitching are not demonstrated.
- Independent opening <=2 cm / >=85% including misses/phantoms, ceiling <=1.5 cm,
  repeated ceiling spread <=1 cm and wall repeat <=1 cm OR 0.5% are unverified.
- Photo walls/footprint +/-8%, video walls +/-3%, tier calibration and measured
  effective drift on/off behavior lack qualifying physical evidence.
- Same property with at least three rooms plus connector, furnished/two-class
  staged damage, all tiers, repeat captures, laser/tape measurements and consumer
  app exports remain missing. No >=70% consumer score exists.
- The scored worst-gate Fix Loop lacks a qualifying measured failure, prospective
  numerical declaration and regenerable shipped before/after. Software guard
  improvements are documented separately; diagnostic work is not claimed as credit.
- Published output schema/earlier Round 1 LiDAR tolerances were not supplied.
- Unseen examiner-phone capture, novice protocol validation, cold-machine timing
  and live regeneration of every reported number are not demonstrated.

Stop development. Submit only as an honestly labelled partial engineering handoff;
do not describe it as full assessment acceptance or independently centimetre-accurate.
The essential acceptance dependency remains the prescribed measured three-tier
physical property benchmark, not another algorithm investigation.
