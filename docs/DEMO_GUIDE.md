# Code-only assignment demonstration

Personal presentation notes, 2026-10-06. Present this as a working research
prototype with explicit acceptance gaps, not a completed three-tier accuracy claim.

## What to show

1. Start with `docs/RESTORATION_FLOW.md`: three capture tiers, common geometry,
   surface assessment, uncertainty, restoration evidence and independent evaluation.
2. Open `demo/given_restoration_on/report.html`. It contains a partial dimensioned
   room from the company's supplied scan, a measurement table, candidate overlays,
   inspection scope and explicit remaining requirements.
3. Open adjacent `assessment.json`: surface-linked IDs, quantities, intervals,
   candidate classes, rule IDs and scope. Explain that this is an internal schema
   awaiting the externally published schema. Engineering intervals are uncalibrated.
4. Show `run.json`: input/code hashes, effective settings, status, runtime, memory,
   assessment status and deliverable hashes. Raw and corrected trajectories remain
   in `artifacts/` for inspection.
5. Show the controlled V3 two-room result as a geometry regression, clearly labeled
   synthetic. It uses many views and does not demonstrate the required 2–8-photo tier.
6. Show `docs/results/given_pose_ablation.json` and
   `docs/results/given_metric_depth_small.json`. Explain why zero accepted loops
   cannot prove drift improvement and why the learned-depth experiment was rejected
   as a direct measurement source.
7. Finish with the current acceptance gaps in `ASSIGNMENT_COMPLIANCE.md` and the
   incremental experiments in `ASSIGNMENT_E2E_STATUS.md`.

## Reproduce the supplied capture

Use a fresh directory for each run. Partial results deliberately return exit code 1;
their reports and geometry remain available. Exit code 0 is not a certification of
assignment accuracy: inspect independent gate results.

```powershell
& .\.venv\Scripts\python.exe -m floorplan.cli run-capture --tier lidar --source datasets/Given_dataset/single_room/c00a170fe1 --out runs/company_room --max-frames 172
Invoke-Item runs/company_room/result/report.html
```

That command includes fresh intake; its uniformly selected frames may differ from
the frozen stride-10, 172-frame experiment. To reproduce the exact experiment use
the preserved prepared manifest:

```powershell
& .\.venv\Scripts\python.exe -m floorplan.cli reconstruct demo/given_single_room_run_v2/intake/capture.json --out runs/company_room_exact --pose-correction on
```

For other raw tiers use `run-capture --tier photos` with per-room folders containing
2–8 photos, or `--tier video` with a MOV/MP4 file. Intake support does not guarantee
overlap, scale, coverage or a reconstructed plan. The actual supplied sparse-photo
trials currently fail to form a model and retain a failure report.

## Questions to expect

**Where does metric scale come from?** LiDAR depth units and camera calibration,
or independent measured scale controls in the RGB multi-view path. RGB monocular
geometry alone has scale ambiguity. The tested learned scale is not accurate enough.

**Why is this room partial?** Camera coverage is 36.6% in the supplied-data experiment;
some boundary spans are inferred and ceiling evidence is absent. A plausible rectangle
is insufficient evidence for a complete property.

**Are the marks confirmed water damage or cracks?** No. Current masks are an
experimental candidate baseline with observed false positives. Scope requests
inspection; concealed moisture is a rule-based possibility, not an observed fact.

**What does the open-source work contribute?** Existing COLMAP/OpenMVS/Open3D geometry
components, plus an actually executed, pinned Depth Anything experiment. RoomFormer,
Floor-SP and Grounded SAM 2 are evaluated research directions; they have not been
presented as installed or validated solutions.

**Have we met the brief?** Not yet. Real survey truth, independent repeats, consumer
comparison, unseen-room capture, published-schema conformance, successful sparse-photo
geometry and validated damage/calibration remain necessary. A fresh-machine setup
within 15 minutes has not been demonstrated.
