# Evaluator operation and reproduction

Development is closed. These are existing interfaces. Final QA ran the documented
production capture path; it did not introduce another reconstruction experiment.
[QA results](FINAL_QA.md) separate execution checks from assessment acceptance.

## Setup and source

Use the final submitted Git commit, or extract `source.zip` from the handoff.
All required source/test modules are now tracked; a private worktree snapshot
is not a substitute for the repository. Run commands from the source root.
Windows/Python 3.12/CPU is the baseline. The root `requirements.txt` references
`requirements/windows-cpu.txt` and installs this project with capture support.

```powershell
& .\scripts\bootstrap_windows.ps1
& .\.venv\Scripts\python.exe -m floorplan.cli --help
& .\.venv\Scripts\python.exe -m pytest -q
```

To create a separate environment, add
`-EnvironmentDirectory .tmp_final_qa\review_env`. Offline preparation can use
`-Wheelhouse <folder>` containing compatible wheels **and build dependencies**.
An existing environment is preserved. Network/cache-assisted setup is not a
cold machine/no-cache benchmark; the measured scope is in the QA evidence.

There are no production API keys/environment variables/checkpoints. PyCOLMAP,
Open3D and image decoding need compatible native wheels; FFmpeg comes through
imageio-ffmpeg. The baseline does not require a separately installed COLMAP CLI.
An optional reference-scaled OpenMVS research path needs the pinned native binary;
`-WithOpenMVS` installs it separately under disclosed upstream terms.

## Input structure and one command per capture

Supplied data is private assessment transfer, not Git content. Place each export
under `datasets/Given_dataset/<case>/<export_id>/` with `rgb.mp4`,
`camera_matrix.csv`, `odometry.csv`, `imu.csv`, `depth/`, and `confidence/`.
Keep source filenames and timestamps. Do not manually reorder/renumber frames.
Photos are `captures/property_photos/<room_id>/` with 2?8 originals per room;
video is one original MOV/MP4. Truth/consumer measurements belong outside inference.

```powershell
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier lidar --source datasets\Given_dataset\single_scan_with_ceiling\c7d28f72c6 --out runs\ceiling_review --profile assignment --property-id supplied_ceiling
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier photos --source captures\property_photos --out runs\photos_review --profile assignment --property-id property_01
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier video --source captures\walkthrough.mov --out runs\video_review --profile assignment --property-id property_01
```

Use a fresh output path. Final QA's supplied LiDAR run exited **1**, wrote
`partial`/readiness false and produced conditional plans and review artifacts.
This is an observed incomplete result, not an expected acceptance pass.
Strict RGB can stop at unresolved metric scale or failed registration. Do not
add manual scale/poses/adjacency to make a strict tier appear successful.

## Verify outputs

Inspect `result/run.json`, `assessment.json`, `contract_coverage.json` and open
`report.html`/`plan.svg`. Geometry also exports plan JSON, DXF and quantities CSV.
Outputs can be absent on early failure. `intake/` records identity/calibration;
preflight failures may write `capture_attempt.json`. There is no
`capture_workflow.json`. A schema check from the repository root is:

```powershell
& .\.venv\Scripts\python.exe -c "import json; from floorplan.contracts import validate_assessment; validate_assessment(json.load(open('runs/ceiling_review/result/assessment.json', encoding='utf-8'))); print('Internal schema valid; inspect readiness separately')"
```

The official published schema is unavailable; internal validity is provisional.

## Existing evidence and scoring interfaces

```powershell
& .\.venv\Scripts\python.exe scripts/verify_layout_artifact.py demo/phase3_strip_trace/current_exterior/ceiling --out demo/ceiling_verification_fresh
& .\.venv\Scripts\python.exe scripts/reproduce_artifacts.py docs/benchmark/phase3_exterior_seed_reproduction.json --out demo/exterior_reproduction_fresh
& .\.venv\Scripts\python.exe -m floorplan.cli evaluate-assignment runs\lidar_review\result survey\reference.json --tier lidar --out runs\lidar_review\gates.json
& .\.venv\Scripts\python.exe -m floorplan.cli evaluate-repeatability runs\repeat_a\result\plan.json runs\repeat_b\result\plan.json survey\reference.json --out runs\repeatability.json
& .\.venv\Scripts\python.exe -m floorplan.cli compare-pose-correction runs\off runs\on --reference survey\reference.json --out runs\drift.json
```

Artifact replay requires its original cloud, planes, normalized source mappings
and producer. Published documents use workspace-relative paths, but historic
native ledgers/binaries may embed original path identities. Read the pinned
manifest; do not suppress mismatch failures or silently substitute producers.
Exact native experiment regeneration remains PARTIAL. `survey/reference.json`,
repeat captures and consumer exports above describe **missing evidence**, not
files supplied with the assessment. Templates and help are available:

```powershell
& .\.venv\Scripts\python.exe -m floorplan.cli import-survey --help
& .\.venv\Scripts\python.exe -m floorplan.cli build-calibration-records --help
& .\.venv\Scripts\python.exe -m floorplan.cli calibrate-intervals --help
& .\.venv\Scripts\python.exe -m floorplan.cli audit-calibration --help
& .\.venv\Scripts\python.exe -m floorplan.cli compare-consumer --help
& .\.venv\Scripts\python.exe scripts/fix_evidence.py --help
```

## Package and report

Package only the **clean intended Git tree**. The packager rejects dirty tracked
source and untracked submission files; it does not hide implementation in an
archive. Source, public evidence and supplied raw data are separate archives.
`repository.bundle` preserves the real Git history for offline evaluator review.
Clone it with `git clone repository.bundle phone-to-floorplan`; no history is
rewritten. Older commit contents remain historical process evidence, including
older development/path wording; the final publication files are cleaned.
Private prior-document backups/finalization scratch helpers are not exported.
Published text evidence has personal path prefixes removed; the manifest records
both published hashes and original hashes when bytes differ. Numeric values,
sensor timestamps and historical producer/input hashes are preserved.

```powershell
& .\.venv\Scripts\python.exe scripts/package_assessment.py --out demo\final_qa\handoff
& .\.venv\Scripts\python.exe scripts/package_assessment.py --verify demo\final_qa\handoff
& .\.venv\Scripts\python.exe scripts/render_assessment_report.py --out demo\report_review
```

Outputs must be fresh. Package creation requires Git metadata and supplied raw
data; verification only requires the package and Python. Extract its three
archives into the same fresh root, then follow README. The report reads indexed
evidence and produces five PDF pages plus source-editable SVGs. Original private
records remain local; [publication provenance](evidence/publication_provenance.json)
explains which hashes name original bytes versus published copies.

The handoff is **PARTIAL** against the every-number live regeneration requirement.
External native/model assets, incomplete physical evidence, historical producer
pins and machine-dependent numerical behavior prevent a blanket reproducibility claim.

## Optional assets: experimental only

`--experimental-rgb` uses MoGe, not the default SIFT route. Its retained code pin
is `74fbce054ebed49800de42d0ad0e83495065719a`; model
`Ruicheng/moge-2-vits-normal` revision `26b477f41595707c5db6770294c0d1721e8ed4ed`,
SHA-256 `79a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc`.
Weights/code under `.tools/`, torch/torchvision and model-specific packages are
separate prerequisites; inspect the retained experimental CLI help before use.
XFeat pin `e92685f57f8318b18725c5c8c0bd28c7fe188d9a` and LightGlue pin
`eb42fee2d71449efb0aa5c10549752b5d75384d8` remain isolated alternatives.
Matching helpers set their own `TORCH_HOME` cache; it is not a baseline dependency.
Full optional asset setup was not clean-machine-tested in final QA.

[Source decisions and attribution](OPEN_SOURCE_DECISIONS.md) disclose recorded
rights/pins. No weights or downloaded upstream source/native binaries are
redistributed in the source archive. Experimental connectivity is not physical
accuracy and does not close an assessment gate.
