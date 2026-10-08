# Repository hygiene and Python tooling inventory

Development is closed. All Python files were inspected with AST parsing, imports,
text references, README/documentation, benchmark/reproduction commands and existing
tests. A missing textual reference alone does not make a CLI tool obsolete.
Experimental tools are retained for evidence inspection; their presence does not
promote them to production. The supported evaluator command is in README.

## Safe cleanup

Fourteen ignored one-off documentation-pass helpers were retired to a local
private archive as `.py.txt` with their original byte hashes. They were never
production imports, test dependencies or public reproduction commands. Their
generated evidence is preserved. No production, benchmark or diagnostic Python
file was deleted merely to make the repository appear smaller. No caches, raw
data, weights or bulk generated outputs are committed. Published evidence summaries
are intentionally tracked.

## Retired one-off helpers

| Original Python file | Why safe to retire |
|---|---|
| `demo/assessment_handoff/attach_final_checks.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff/build_manifest.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff/check_requirements.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff/extract_evidence.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff/final_git_check.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff/quality_check.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff/recover_package.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff/refresh_source.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff/validate_snapshot.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff_inspect.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff_operations.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff_sources.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff_start.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |
| `demo/assessment_handoff_write_docs.py` | Superseded by the tracked final package/report tools and final QA receipts; no public import/command reference. |

## Retained Python inventory

| File | Classification | Purpose / retained value |
|---|---|---|
| `floorplan/__init__.py` | PRODUCTION | Code-only floor plan demonstration. |
| `floorplan/ablation.py` | PRODUCTION | Compare identical-input pose-correction runs without mistaking change for accuracy. |
| `floorplan/acceptance.py` | PRODUCTION | Explicit August gates and visibly provisional interpretations. |
| `floorplan/assessment.py` | PRODUCTION | Surface-keyed measurements and an offline review report for every run status. |
| `floorplan/assessment_io.py` | PRODUCTION | Read canonical assessments and historical plans without changing metric scale. |
| `floorplan/assignment_gates.py` | PRODUCTION | Versioned evaluator for gates stated in the August 2026 assignment. |
| `floorplan/benchmark.py` | PRODUCTION | Independent polygon/topology evaluation, invoked only after reconstruction. |
| `floorplan/benchmark_manifest.py` | PRODUCTION | Audit benchmark composition and raw identities; metadata is not accuracy proof. |
| `floorplan/calibration_records.py` | PRODUCTION | Build calibration residuals from frozen outputs and independent measurements. |
| `floorplan/capture_sync.py` | PRODUCTION | Audit decoded sensor-video identity before pairing it with depth and poses. |
| `floorplan/cli.py` | PRODUCTION | Command-line entry point. |
| `floorplan/consumer_comparison.py` | PRODUCTION | Auditable shared-dimension comparison; no geometry changes enter inference. |
| `floorplan/contracts.py` | PRODUCTION | Internal deliverable contract. The assignment's published schema is still absent. |
| `floorplan/damage.py` | PRODUCTION | Experimental wall discoloration/crack candidates with RGB-D surface projection. |
| `floorplan/damage_evaluation.py` | PRODUCTION | Independent surface annotation scoring; never imported by reconstruction. |
| `floorplan/demo.py` | PRODUCTION | Make a fully known scene for a reproducible geometry smoke test. |
| `floorplan/dense.py` | PRODUCTION | Measured-scale COLMAP bridge and bounded CPU stereo reconstruction. |
| `floorplan/evaluation.py` | PRODUCTION | Held-out metric evaluation. This module is not imported by reconstruction. |
| `floorplan/geometry.py` | PRODUCTION | Image-ground projection and rigid room alignment. |
| `floorplan/icl_benchmark.py` | PRODUCTION | Reproducible, idealized metric wall-scan benchmark using ICL-NUIM. |
| `floorplan/ingest.py` | PRODUCTION | Convert stock phone captures into auditable capture manifests. |
| `floorplan/layout.py` | PRODUCTION | Conservative CPU wall-segment polygonization; no reference geometry inputs. |
| `floorplan/mapping.py` | PRODUCTION | CPU geometric refinement and pose graph; all transforms are camera-to-world. |
| `floorplan/metric_depth.py` | PRODUCTION | Optional, pinned RGB-only depth proposals; sensor comparison is a separate stage. |
| `floorplan/openings.py` | PRODUCTION | Conservative aperture proposals from wall support and observed through-rays. |
| `floorplan/openmvs.py` | PRODUCTION | Optional external OpenMVS CPU backend; no reference geometry enters inference. |
| `floorplan/pipeline.py` | PRODUCTION | Reproducible floor-plan processing from annotated images and video frames. |
| `floorplan/pose_graph.py` | PRODUCTION | Conservative cycle checks for independently verified rigid capture links. |
| `floorplan/provenance.py` | PRODUCTION | Producer fingerprints separate model/config identity from capture identity. |
| `floorplan/repeatability.py` | PRODUCTION | Compare independently captured plans using the surveyed wall identities. |
| `floorplan/rgb_metric.py` | EXPERIMENTAL | Bounded, opt-in RGB metric-geometry experiment. Not an accepted scale source. |
| `floorplan/rgbd.py` | PRODUCTION | CPU RGB-D mapping and supported floor-plan proposals. |
| `floorplan/sfm.py` | PRODUCTION | Optional COLMAP Structure-from-Motion experiment for RGB media. |
| `floorplan/stitching.py` | PRODUCTION | Join independently reconstructed RGB-D captures using verified visual overlap. |
| `floorplan/supported_cells.py` | PRODUCTION | Bounded room hypotheses from measured wall fragments, with explicit gaps. |
| `floorplan/survey.py` | PRODUCTION | Import independent survey tables for evaluation, never reconstruction. |
| `floorplan/uncertainty.py` | PRODUCTION | Explicit uncalibrated envelopes and property-held-out conformal calibration. |
| `floorplan/workflow.py` | PRODUCTION | Common capture entry point and reproducible run ledger. |
| `scripts/datasets/acquire_references.py` | BENCHMARK / REPRODUCTION | Acquire separate reference assets and an unseen ICL sequence. |
| `scripts/datasets/annotate_laser_reference.py` | BENCHMARK / REPRODUCTION | Fit reference wall lines inside manually inspected FARO regions, independently |
| `scripts/diagnostics/audit_ceiling_boundary_shift.py` | DIAGNOSTIC / EVALUATION | Read-only sensor audit of the footprint notch in the supplied ceiling scan. |
| `scripts/diagnostics/audit_final_frame31.py` | DIAGNOSTIC / EVALUATION | Close the final frame31 diagnostic from saved evidence; never rerun mapping. |
| `scripts/diagnostics/audit_floor_boundary.py` | DIAGNOSTIC / EVALUATION | Audit frozen uncovered samples and omitted wall support; no reconstruction edits. |
| `scripts/diagnostics/audit_late_attachment.py` | DIAGNOSTIC / EVALUATION | Read-only temporal-attachment and exact triangle witnesses for batch024. |
| `scripts/diagnostics/audit_late_landmarks.py` | DIAGNOSTIC / EVALUATION | Read-only saved-landmark audit; no matching, verification or mapping calls. |
| `scripts/diagnostics/audit_registration_snapshots.py` | DIAGNOSTIC / EVALUATION | Post-hoc native stage audit; sensor poses never enter the replay runner. |
| `scripts/diagnostics/audit_registration_stage.py` | DIAGNOSTIC / EVALUATION | Read-only post-hoc audit, gated on exact native snapshot reproduction. |
| `scripts/diagnostics/audit_registration_support.py` | DIAGNOSTIC / EVALUATION | Read-only audit of saved frame34 registration candidates and associations. |
| `scripts/diagnostics/audit_room_floor_returns.py` | DIAGNOSTIC / EVALUATION | Read-only source-return inventory for a fixed room and horizontal plane. |
| `scripts/diagnostics/audit_sfm_components.py` | DIAGNOSTIC / EVALUATION | Inspect frozen verified-pair connectivity and sparse models without remapping. |
| `scripts/diagnostics/audit_transition_initialization.py` | DIAGNOSTIC / EVALUATION | Audit native initialization suitability on a frozen-copy matcher database. |
| `scripts/diagnostics/audit_transition_odometry.py` | DIAGNOSTIC / EVALUATION | Post-hoc sensor audit of saved RGB-only models; never map or optimize poses. |
| `scripts/diagnostics/audit_transition_tracks.py` | DIAGNOSTIC / EVALUATION | Read-only track/safety audit of the frozen 24-view matcher experiments. |
| `scripts/evaluation/compare_boundary_runs.py` | DIAGNOSTIC / EVALUATION | Compare identical-input boundary runs; camera coverage is not metric truth. |
| `scripts/evaluation/compare_frozen_partial_cells.py` | DIAGNOSTIC / EVALUATION | Isolate a layout change on frozen geometry; retain strict raw-run failures. |
| `scripts/evaluation/compare_residual_wall_search.py` | DIAGNOSTIC / EVALUATION | Isolate residual discovery from native reconstruction variation and truth. |
| `scripts/evaluation/compare_transition_context.py` | DIAGNOSTIC / EVALUATION | Compare repeated 32-view context models to the frozen 24-view evidence. |
| `scripts/evaluation/compare_transition_matchers.py` | DIAGNOSTIC / EVALUATION | Read-only comparison of retained SIFT and repeated pinned LightGlue trials. |
| `scripts/evaluation/compare_video_bridge_trials.py` | DIAGNOSTIC / EVALUATION | Compare frozen bridge trials and trace native matcher support before RANSAC. |
| `scripts/evaluation/compare_wall_support.py` | DIAGNOSTIC / EVALUATION | Compare historical/global and local/spatial wall support on one frozen cloud. |
| `scripts/diagnostics/diagnose_capture_sync.py` | DIAGNOSTIC / EVALUATION | Compare scanner RGB playback and encoded timelines with all sensor frames. |
| `scripts/diagnostics/diagnose_supplied_geometry.py` | DIAGNOSTIC / EVALUATION | Inspect frozen reconstruction evidence; no survey inputs or accuracy claims. |
| `scripts/evaluation/evaluate_fixed_intrinsics.py` | DIAGNOSTIC / EVALUATION | Evaluate fixed-intrinsics controls with the unchanged withheld-odometry audit. |
| `scripts/evaluation/evaluate_icl.py` | DIAGNOSTIC / EVALUATION | Evaluate a saved RGB-D plan against the separate ICL-NUIM mesh reference. |
| `scripts/evaluation/evaluate_lidar_sampling.py` | DIAGNOSTIC / EVALUATION | Evaluate the saved density control without refitting or changing production. |
| `scripts/evaluation/evaluate_mapping_only.py` | DIAGNOSTIC / EVALUATION | Post-hoc odometry/track audit of the frozen-inlier mapping-only ablation. |
| `scripts/evaluation/evaluate_moge_depth.py` | DIAGNOSTIC / EVALUATION | RGB-only MoGe-2 depth probe against withheld ARKitScenes LiDAR depth. |
| `scripts/evaluation/evaluate_sfm_trajectory.py` | DIAGNOSTIC / EVALUATION | Evaluation-only camera trajectory audit. Never imported by reconstruction. |
| `scripts/evaluation/evaluate_xfeat_context.py` | DIAGNOSTIC / EVALUATION | Audit two isolated XFeat trials against retained, never rerun, 32-view controls. |
| `scripts/experiments/experimental_boundary_precision.py` | EXPERIMENTAL | Measure precision-grid sensitivity without adding wall support or gap closure. |
| `scripts/experiments/experimental_fixed_intrinsics.py` | EXPERIMENTAL | Isolated fixed-calibration control over retained XFeat feature/match indices. |
| `scripts/experiments/experimental_lidar_sampling.py` | EXPERIMENTAL | Isolated stride4 LiDAR control with frozen frames/poses and unchanged guards. |
| `scripts/experiments/experimental_lightglue_sfm.py` | EXPERIMENTAL | Isolated CPU LightGlue+DISK comparison using only input RGB. |
| `scripts/experiments/experimental_mapping_only.py` | EXPERIMENTAL | Map original XFeat verified rows with fixed calibration; no frontend rerun. |
| `scripts/experiments/experimental_planar_patches.py` | EXPERIMENTAL | Compare local observed-wall patches with the existing frozen plane proposals. |
| `scripts/experiments/experimental_registration_snapshots.py` | EXPERIMENTAL | Native snapshot replay of batch023; no frontend or pose-prior inference. |
| `scripts/experiments/experimental_registration_stage.py` | EXPERIMENTAL | Isolated native frame34 registration replay; no matching or sensor poses. |
| `scripts/experiments/experimental_seed_replay.py` | EXPERIMENTAL | Frozen-cloud original-seed/residual-consensus trial; no production edits. |
| `scripts/experiments/experimental_semantic_walls.py` | EXPERIMENTAL | Evaluation-only furniture rejection on an audited supplied LiDAR cloud. |
| `scripts/experiments/experimental_transition_context.py` | EXPERIMENTAL | Matched 32-view RGB context trial with frozen correspondence/mapping recipes. |
| `scripts/experiments/experimental_transition_matchers.py` | EXPERIMENTAL | Pinned, isolated matcher comparison on the retained 24-view RGB transition. |
| `scripts/experiments/experimental_video_bridge.py` | EXPERIMENTAL | Bounded RGB-only bridge-view experiment; never changes production policy. |
| `scripts/experiments/experimental_wall_density.py` | EXPERIMENTAL | Frozen-cloud comparison of height-band line proposals with raw 3D validation. |
| `scripts/experiments/experimental_wall_seed_budget.py` | EXPERIMENTAL | Frozen-cloud seed-budget alternative; production source remains unchanged. |
| `scripts/experiments/experimental_xfeat_context.py` | EXPERIMENTAL | Isolated pinned XFeat/LighterGlue trial on the frozen 32-view RGB context. |
| `scripts/evaluation/fix_evidence.py` | BENCHMARK / REPRODUCTION | Freeze a prospective fix declaration; verify later replay without inventing history. |
| `scripts/datasets/inspect_laser_reference.py` | BENCHMARK / REPRODUCTION | Memory-bounded FARO reference inspection; never imported by inference. |
| `scripts/install_openmvs.py` | EVALUATOR UTILITY | Acquire the official pinned CPU-only Windows OpenMVS release locally. |
| `scripts/datasets/make_multimodal_fixture.py` | BENCHMARK / REPRODUCTION | Render a controlled two-room RGB/video/depth fixture with isolated references. |
| `scripts/datasets/make_sequence_video.py` | BENCHMARK / REPRODUCTION | Encode calibrated sequence RGB images into a video for input-path testing. |
| `scripts/datasets/make_split_fixture.py` | BENCHMARK / REPRODUCTION | Create independently framed overlapping captures from the synthetic fixture. |
| `scripts/package_assessment.py` | EVALUATOR UTILITY | Package the current source and saved evidence without executing inference. |
| `scripts/datasets/prepare_arkit.py` | BENCHMARK / REPRODUCTION | Selectively acquire ARKitScenes mobile inputs; keep laser references separate. |
| `scripts/datasets/prepare_icl.py` | BENCHMARK / REPRODUCTION | Extract a small, evenly sampled ICL-NUIM RGB-D sequence safely. |
| `scripts/datasets/prepare_icl_rgb_controls.py` | BENCHMARK / REPRODUCTION | Simulate an independent measured reference from two ICL depth samples. |
| `scripts/datasets/refresh_fixture_controls.py` | BENCHMARK / REPRODUCTION | Simulate re-measuring a control in the controlled fixture, without rerendering. |
| `scripts/render_assessment_report.py` | EVALUATOR UTILITY | Render the frozen five-page report and editable evidence diagrams. |
| `scripts/evaluation/render_checkpoint_report.py` | BENCHMARK / REPRODUCTION | Render a three-page development checkpoint from actual run artifacts. |
| `scripts/evaluation/render_reports.py` | BENCHMARK / REPRODUCTION | Render architecture and measured benchmark figures from saved artifacts. |
| `scripts/evaluation/reproduce_artifacts.py` | BENCHMARK / REPRODUCTION | Regenerate explicitly inventoried artifacts into a fresh directory. |
| `scripts/evaluation/snapshot_results.py` | BENCHMARK / REPRODUCTION | Collect the recorded local benchmark artifacts into a small reviewable JSON. |
| `scripts/evaluation/snapshot_rgbd_results.py` | BENCHMARK / REPRODUCTION | Publish concise, source-linked results and inspectable figures from saved runs. |
| `scripts/evaluation/snapshot_multiview_results.py` | BENCHMARK / REPRODUCTION | Build the compact V3 results record and chart from completed run ledgers. |
| `scripts/diagnostics/trace_adjoining_span.py` | DIAGNOSTIC / EVALUATION | Audit a diagnostic span against measured returns; never create geometry. |
| `scripts/diagnostics/trace_exterior_strip.py` | DIAGNOSTIC / EVALUATION | Trace an aligned exterior strip from sensor pixels to frozen wall proposals. |
| `scripts/diagnostics/trace_observed_ceiling.py` | DIAGNOSTIC / EVALUATION | Read-only native floor/ceiling decision trace on retained room geometry. |
| `scripts/evaluation/verify_layout_artifact.py` | BENCHMARK / REPRODUCTION | Replay frozen geometry artifacts; this verifies reproducibility, not accuracy. |
| `tests/test_ablation.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_adjoining_span_trace.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_assessment.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_assessment_package.py` | BENCHMARK / TEST | Submission packaging must not hide missing source or leak private paths. |
| `tests/test_assignment_gates.py` | BENCHMARK / TEST | The exact brief must not pass when old geometry-only outputs omit essentials. |
| `tests/test_benchmark_evidence.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_boundary_comparison.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_capture_sync.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_ceiling.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_ceiling_boundary_shift.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_checkpoint_report.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_damage_validation.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_final_frame31.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_fix_evidence.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_fixed_intrinsics.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_floor_boundary_audit.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_floorplan.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_ingest.py` | BENCHMARK / TEST | Capture normalization tests with source-shaped, deliberately small fixtures. |
| `tests/test_late_landmarks.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_layout_artifact.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_lidar_sampling.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_mapping_only.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_metric_depth.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_metric_registration.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_observed_ceiling_trace.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_openings.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_assessment_contract.py` | BENCHMARK / TEST | Regression coverage for actual contract/evaluator and command failure defects. |
| `tests/test_pose_boundaries.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_registration_snapshots.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_registration_stage.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_registration_support.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_repeatability.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_reproduction.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_rgb_camera_consistency.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_rgbd.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_room_floor_returns.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_semantic_diagnostic.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_sfm_components_audit.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_sfm_diagnostics.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_supported_cells.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_survey_records.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_transition_context.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_transition_matchers.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_transition_odometry.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_transition_tracks.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_video_bridge_trial.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_wall_completion.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_wall_planes.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_workflow.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |
| `tests/test_xfeat_context.py` | BENCHMARK / TEST | Regression test/module; see functions and test discovery. |

Scripts without a current README command, including historical fixture/snapshot
collectors and isolated plane/precision/density comparisons, remain explicitly
nonproduction. They preserve earlier evidence paths or independently callable
diagnostics; executing every historical tool is not required to run a capture.
Some require optional assets/native producers absent from a clean baseline.
Do not run closed registration investigations as a new development task.

## Submission boundaries

`floorplan/` plus schemas is the runtime; `rgb_metric.py` is opt-in experimental.
`tests/` checks controlled behavior; it is not a laser/tape benchmark.
`scripts/` contains the catalogued utilities above. `docs/engineering/investigations` and `benchmarks/results`
are historical evidence with canonical status in the compliance/validation docs.
The detailed personal pending queue is retained privately; the tracked file
points to final statuses. Old local packages remain private backups and are
superseded by the final clean-tree package.
