# Engineering evidence index

The primary reading path is [validation and decisions](../validation.md),
[Fix Loop](../fix_loop.md), [architecture](../architecture.md) and the
[technical report](../technical_report.md). The records below preserve detailed
inputs, controls, reproduction commands, failures and limitations. They are
supporting evidence; closed investigations are not a development queue.

## Investigation groups

| Area | Detailed records |
|---|---|
| Shipped geometry and correctness work | 001 to 015: supported cells, camera conventions, local wall support and original sensor traces |
| RGB alternatives and independent audits | 016 to 028: bridge sampling, matching, fixed calibration, mapping and native registration |
| LiDAR and floor/ceiling acceptance | 029 to 032: rejected density trial, boundary audit, ceiling rejection and original floor returns |

## Detailed records

| Record | Subject |
|---|---|
| [001](investigations/001_supported_cells.md) | Prospective fix declaration: supported room cells |
| [002](investigations/002_sparse_photo_entry.md) | Prospective fix: permit the stated 2 to 8 photos per room |
| [003](investigations/003_sparse_overlap_trial.md) | Sparse photo overlap diagnosis |
| [004](investigations/004_matching_diagnostics.md) | Prospective fix: report verified photo overlap and SfM initialization failures |
| [005](investigations/005_repeatable_sfm.md) | Prospective fix: seed all COLMAP SfM stages |
| [006](investigations/006_moge_metric_rgb_eval.md) | MoGe-2 RGB-only metric-depth experiment |
| [007](investigations/007_walkin_output_coverage.md) | Prospective fix: expose assignment output coverage in every run report |
| [008](investigations/008_lightglue_photo_matching.md) | Prospective experiment: LightGlue + DISK for sparse photo matching |
| [009](investigations/009_two_view_geometry_classification.md) | Prospective fix: expose two-view geometry classifications |
| [010](investigations/010_three_room_stitch_chain.md) | Prospective fix: prove a three-room stitch chain in the offline contract |
| [011](investigations/011_local_wall_support.md) | Local wall support correctness correction |
| [012](investigations/012_partial_cell_completeness.md) | Partial-cell completeness without promoting inferred geometry |
| [013](investigations/013_floor_sample_wall_audit.md) | Audit of 151 uncovered floor-scan camera samples |
| [014](investigations/014_exterior_strip_sensor_trace.md) | Exterior-strip sensor trace and original-seed recovery |
| [015](investigations/015_lower_adjoining_span_trace.md) | Batch 015: lower adjoining-span sensor and traversal audit |
| [016](investigations/016_rgb_video_bridge_trial.md) | Batch 016: original RGB bridge-frame experiment |
| [017](investigations/017_disk_lightglue_transition.md) | Pinned DISK + LightGlue on the retained RGB transition |
| [018](investigations/018_transition_track_safety.md) | Retained transition: correspondence safety and sparse-model audit |
| [019](investigations/019_rgb_transition_context.md) | Matched 32-view RGB context experiment |
| [020](investigations/020_xfeat_lighterglue_context.md) | XFeat + LighterGlue on the retained 32-view RGB context |
| [021](investigations/021_transition_odometry_audit.md) | Independent post-hoc odometry audit of the 29-view joint RGB model |
| [022](investigations/022_fixed_intrinsics_control.md) | Fixed per-frame intrinsics control on retained XFeat correspondences |
| [023](investigations/023_mapping_only_fixed_intrinsics.md) | Mapping-only fixed-intrinsics ablation with original verified rows |
| [024](investigations/024_late_landmark_support_audit.md) | Saved 31->34 landmark identity and geometry audit |
| [025](investigations/025_native_registration_snapshots.md) | Native registration snapshots: when the late pose error appears |
| [026](investigations/026_native_registration_stage.md) | Frame34 registration before local refinement |
| [027](investigations/027_registration_support_audit.md) | Frame34 registration support: ambiguity versus inherited geometry |
| [028](investigations/028_final_frame31_replay.md) | Final frame31 replay: reproduction failure and diagnostic closure |
| [029](investigations/029_lidar_floor_sampling_control.md) | Supplied LiDAR floor completeness: bounded depth-density control |
| [030](investigations/030_ceiling_boundary_sensor_audit.md) | Ceiling-scan boundary shift: original sensor evidence audit |
| [031](investigations/031_observed_ceiling_decision_trace.md) | room_2: native observed-ceiling decision trace |
| [032](investigations/032_room_floor_source_support_audit.md) | room_2: original floor returns versus sampling and fusion |

## Supporting decisions and history

- [Evaluated algorithmic alternatives](alternative_approaches.md): evidence-led comparison and rights/dependency decisions.
- [Dataset readiness](dataset_readiness.md) and [independent depth-reference review](reference_depth_review.md): scope and limits of available references.
- [End-to-end validation](end_to_end_validation.md): historical capture checks.
- [Implementation evidence history](implementation_history.md): consolidated contract, supplied-capture, synchronization and acceptance records with a section index.
- [Earlier RGB-D implementation](history/rgbd_baseline.md) and [multi-view implementation](history/multiview_baseline.md): original controlled inputs and decisions.

Numeric outputs are in [benchmark results](../../benchmarks/results/). Historical
producer hashes are retained; exact original script bytes are in Git history.
Personal design notes and plans are local and excluded from this public index.
