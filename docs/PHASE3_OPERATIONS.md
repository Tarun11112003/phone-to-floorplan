# Final reproduction and evidence handoff

Development freeze: 2026-10-08. These are real existing interfaces. Commands
below are documented for reproduction; **no new reconstruction experiment was
run during finalization**. See [validation](BENCHMARK_RESULTS.md) for recorded
results and [limitations](LIMITATIONS.md) for what cannot be regenerated now.

## Environment

The documented baseline is Windows, Python3.12 and CPU. `pyproject.toml` permits
Python>=3.10; the observed CPU pins are `requirements/windows-cpu.txt`.
`scripts/bootstrap_windows.ps1` preserves an existing environment and supports
an alternative environment directory and offline wheelhouse. Wheels/native
binaries still need a compatible machine; a<15min clean-install pass is absent.

The root `requirements.txt` includes the same observed Windows CPU pins and
installs this project with capture support. In an activated Python 3.12 virtual
environment, use `python -m pip install -r requirements.txt`. No duplicate pin
set or fresh-install timing claim is introduced.

```powershell
& .\scripts\bootstrap_windows.ps1
& .\.venv\Scripts\python.exe -m floorplan.cli --help
& .\.venv\Scripts\python.exe -m pytest -q
```

Optional flags: `-EnvironmentDirectory .venv-review`, `-Wheelhouse <folder>`
and `-WithOpenMVS`. Do not run the last flag to reproduce the sensor baseline;
OpenMVS is an optional research dense backend with separate upstream terms.
The bootstrap installs observed pins, not experimental learned assets.

## Source snapshot versus Git

Finalization creates focused documentation commits only. The existing validated
but uncommitted implementation is preserved and included in `source_snapshot.zip`.
That snapshot is the current development source, **not Git HEAD**. Do not claim
a documentation-only checkout contains every current module or390 tests.
Extract the snapshot to a fresh directory, install its own dependencies and
run the commands there. The handoff's source inventory records every included
file hash and the base commit; `.git`, environments, caches and model weights
are excluded. A local snapshot test in the existing dependency environment does
not prove clean-machine installation time.

## Capture commands

Run from the extracted/current source root, with original input assets available.
Output directories must be fresh. Assignment-profile runs may exit nonzero
and still write useful failed/partial review evidence; never suppress that status.

```powershell
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier lidar --source datasets\Given_dataset\single_scan_with_ceiling\c7d28f72c6 --out runs\ceiling_review --profile assignment --property-id supplied_ceiling
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier photos --source captures\property_photos --out runs\photos_review --profile assignment --property-id property_01
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier video --source captures\walkthrough.mov --out runs\video_review --profile assignment --property-id property_01
```

Strict RGB baseline can return scale_unresolved or incomplete geometry.
Photo/video metric inference is opt-in experimental using `--experimental-rgb`;
it remains unpromoted and is not an assignment success path merely because it
produces geometry. No scale marker, manual pose or adjacency is silently added.

Conditional output: `intake/capture.json`, `intake/intake.json`,
`result/run.json`, `assessment.json`, `contract_coverage.json`, `report.html`;
supported geometry adds plan JSON/SVG/DXF/CSV and/or layout diagnostics.
Intake/preflight failure can instead write `capture_attempt.json` and a failed
result. There is no `capture_workflow.json` output in this implementation.

## Existing artifact and evaluation commands

```powershell
& .\.venv\Scripts\python.exe scripts/verify_layout_artifact.py demo/phase3_strip_trace/current_exterior/ceiling --out demo/ceiling_verification_fresh
& .\.venv\Scripts\python.exe scripts/reproduce_artifacts.py docs/benchmark/phase3_exterior_seed_reproduction.json --out demo/exterior_reproduction_fresh
& .\.venv\Scripts\python.exe -m floorplan.cli evaluate-assignment runs\lidar_review\result survey\reference.json --tier lidar --out runs\lidar_review\gates.json
& .\.venv\Scripts\python.exe -m floorplan.cli evaluate-repeatability runs\repeat_a\result\plan.json runs\repeat_b\result\plan.json survey\reference.json --out runs\repeatability.json
& .\.venv\Scripts\python.exe -m floorplan.cli compare-pose-correction runs\off runs\on --reference survey\reference.json --out runs\drift.json
```

The retained-artifact commands require their original cloud, planes, camera
state and producer paths. Historical manifests contain local absolute paths;
hash verification is portable, but native replay may need equivalent mounted
paths or re-normalization from raw inputs. No blanket portable exact-replay claim
is made. Independent survey/repeat assets in the evaluation examples are
placeholders for **missing evidence**, not files supplied in the handoff.

Survey/calibration/consumer interfaces are available without inventing inputs:

```powershell
& .\.venv\Scripts\python.exe -m floorplan.cli import-survey --help
& .\.venv\Scripts\python.exe -m floorplan.cli build-calibration-records --help
& .\.venv\Scripts\python.exe -m floorplan.cli calibrate-intervals --help
& .\.venv\Scripts\python.exe -m floorplan.cli audit-calibration --help
& .\.venv\Scripts\python.exe -m floorplan.cli compare-consumer --help
& .\.venv\Scripts\python.exe scripts/fix_evidence.py --help
```

Their schemas/templates are retained; no physical benchmark, prospective
worst-gate declaration or consumer scores are created for the deadline.

## Package contents and integrity

The local `demo/assessment_handoff/package/` contains a source snapshot,
curated evidence archive, supplied raw-data archive and package manifest.
The package script inventories current sources and existing records; it does
not reconstruct, optimize or alter original evidence. FileSHA-256 and archive
integrity are verified. Original detailed summaries preserve absolute producer/
input paths; the package inventory separately records portable relative paths.

```powershell
& .\.venv\Scripts\python.exe scripts/package_assessment.py --out demo/handoff_package_fresh
& .\.venv\Scripts\python.exe scripts/package_assessment.py --verify demo/handoff_package_fresh
& .\.venv\Scripts\python.exe scripts/render_assessment_report.py --out demo/final_report_fresh
```

Full raw supplied data is kept out of Git; the separate local archive is for
assessment transfer, not public redistribution. External `.tools` code/binaries/
weights and virtual environments are excluded. Recorded upstream notices and
pins are retained. Optional assets must be downloaded/mounted separately under
their applicable terms. The provided raw captures lack independent survey truth.

The bundle is a source-and-evidence handoff, **PARTIAL against the assessment's
every-number live regeneration requirement**. Native experiment prerequisites,
hardware, missing measured benchmark and historic path assumptions remain
explicit. No source code/algorithm changes are needed to read the package.

## Optional learned assets: disclosure, not promotion

The existing experiment pins MoGe code74fbce054ebed49800de42d0ad0e83495065719a,
model `Ruicheng/moge-2-vits-normal` revision26b477f41595707c5db6770294c0d1721e8ed4ed
and SHA-25679a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc.
Its CPU assets are separate from bootstrap. DISK/LightGlue/XFeat checkpoints and
fixed-intrinsics controls are isolated alternatives; none is promoted by this
handoff. Original licensing/provenance is in [source decisions](OPEN_SOURCE_DECISIONS.md)
and the archived research records. Setup/model download times are not included
in old inference timings.
