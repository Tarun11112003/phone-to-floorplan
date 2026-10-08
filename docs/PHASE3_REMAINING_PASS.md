# Remaining Phase 3 implementation pass — Scope: [approved plan](PHASE3_IMPLEMENTATION_PLAN.md), [assignment](Applied%20AI.html).
No commits or pushes. Existing local work is preserved. This ledger distinguishes
software changes from surveyed acceptance; it is updated as checks finish.

This is the earlier frozen checkpoint. The subsequent
[supplied-data continuation](PHASE3_SUPPLIED_DATA_PASS.md) records the latest
wall/floor/ceiling, loop, damage and intake fixes, 133 serial passing tests and
fresh partial supplied-data results. Numbers below retain their historical meaning.

## Priority and observed outcomes

1. CHANGE-06 calibration consistency: confirmed that inferred depth was being
   backprojected with a different SfM camera. The pinned MoGe API accepts horizontal
   FOV only; a centered square-pixel virtual camera now conditions inference, and
   depth is resampled back into the rectified source camera. Invalid calibration
   is rejected; unsupported borders are masked. RGB-inferred K uses pixel-center
   coordinates consistently. This remains an experimental metric prior.
2. CHANGE-09 camera alternatives: same public six-second development video,
   same quality selection and exhaustive matching: explicitly shared SIMPLE_RADIAL
   camera registered **2/12**, versus the historical auto-camera checkpoint **6/12**.
   Shared calibration is an explicit configuration option, not the new default.
   This comparison does not establish an advantage on other captures or lenses.
3. CHANGE-06 actual replay: `demo/phase3_remaining/icl_conditioned/result/run.json`
   recorded unchanged source, 33.03 s reconstruction / 33.46 s including intake.
   Previously the same RGB-only synthetic development control rejected its metric
   prior. Conditioned inference accepts **233 tracks across three views**, log-ratio
   p80 **0.09473** against the unchanged 0.25 development rejection bound. Still
   **3/4** original images register; no supported closed room is produced. This is
   a development diagnostic improvement, not physical accuracy or Part 4 proof.
4. CHANGE-09: requested correction on/off reaches the experimental RGB sequence
   and roomwise fallback. Rejected frames preserve original path boundaries;
   tracking gaps cannot manufacture doorway traversal. Continuous pieces refine
   independently, without sequential constraints/interpolation between photo views.
   ICP additionally bounds rotation, and rejected sequential ICP keeps a weak raw
   pose prior instead of claiming strong geometric information.
5. CHANGE-10: capture links now check rigid transforms and verified cycle residuals;
   redundant cycle constraints are uncertain. Registered views/poses/depth units
   survive property fusion for shared opening/damage projection. Room identities
   use one-to-one transformed polygon overlap; unresolved identities stay failures.
6. CHANGE-11: shared walls use camera-side/room visibility so one image does not
   assign the same mark to both faces. Evaluated-no-candidates is explicitly
   different from no registered views. Independent annotation scoring reports
   misses, phantoms, class precision/recall, IoU and metric extents, including clean
   control surfaces. It never promotes an unvalidated classifier automatically.
7. CHANGE-04/12/13: the survey CSV importer rejects blank templates, missing walls,
   mixed property identities and missing external reading evidence. Direct surveyed
   wall lengths are preserved in assignment/repeatability scoring. Raw tables and
   evidence are hashed; derived references never enter reconstruction. Unannotated
   damage is unavailable, while explicit clean-control rows can be scored. Shared
   wall net-area references remain unavailable without their face association.
8. CHANGE-12: calibration records now have a builder from frozen assessment/run
   artifacts and independent measurement references. Missing estimates/references,
   mismatched units/kinds, duplicate records and mixed producers are explicit.
   Producer identity includes tier/camera grouping; calibration is fitted per tier
   and frozen recipe. A source/configuration change requires refitting.
9. CHANGE-05/09: orientation-corrected normalized and selected photos retain their
   EXIF camera metadata. Every quality candidate is accounted for with its selection
   or rejection reason. Metadata remains a camera prior, not a surveyed K matrix.
10. CHANGE-06/09: independent-photo registration now searches any of up to 24
    registered views, rather than relying on filename order or video-sized motion.
    Default ordered-video motion bounds remain unchanged. All paths require at
    least 20 mutually consistent depth correspondences and verified reprojection
    after metric refinement. Previously a failed metric-depth refinement could
    leave a successful PnP pose eligible for use; it is now rejected. An unusable
    first view can be skipped without preventing later initialization.
11. CHANGE-03/06: repeated video runs exposed sensitivity at the scale bound.
    Matching now uses one CPU thread, while all existing seed controls remain.
    Three actual serial SfM trials produce identical camera parameter arrays,
    registered counts (**6/12**) and sparse point counts (**85**). Torch inference
    additionally sets seed 7 and deterministic algorithm mode. This establishes
    only the tested configuration's repeatability, not cross-machine guarantees.
12. CHANGE-08: observed jamb/header measurements no longer require an observed
    ceiling. Sufficient actual wall support bounds the detector raster; it does
    not become a ceiling estimate or an assumed opening height. The existing
    multi-view through-ray and raw-edge evidence requirements remain.
13. CHANGE-06/10: a successful verified roomwise fallback is not downgraded by
    the failed initial global SfM model. Conversely, a partial child plan is not
    enough to enter property fusion. Experimental and incomplete assessment
    contracts still cannot report assignment success.

## Alternatives evaluated from source

Reference A at `d5105858440bdb549626845948bc51da8a8b9f02`:
`scanplan/ingest/photos.py`, `ingest/video.py`, `geometry/register.py`.
Exif-informed camera selection and floor-orientation handling were considered.
Its photo path explicitly does not reconstruct SfM or automatically stitch;
fixed default FOV/rectangular estimates/side-by-side placement cannot close our
strict-photo requirements. Its video requires external poses. Raster registration
is useful for evaluation pairing but lacks the visual verification needed for
repetitive-room inference. Those substitutions were not adopted.

Reference B at `c9dfacbed60ddb6554a7c9b6721696dfb748013a`:
`cozmoscan/capture/photo_tier.py`, `video_tier.py`, `geometry/stitching.py`,
`damage/scope.py`. Motion/coverage-aware keyframe selection and surface-linked
scope were considered. Its photo scale assumes camera height/levelness; video
consumes VIO; stitching requires connectors and lacks cycle closure. These do not
solve our selected stock-camera route. Retain verified constraints, calibrated
intervals and inspection scope; do not introduce assumed heights, manual links
or automatic drywall removal from a visual candidate.

The MoGe conditioning change follows its documented, inspected pinned API:
[MoGe infer](https://github.com/microsoft/MoGe/blob/74fbce054ebed49800de42d0ad0e83495065719a/moge/model/v2.py).
Source alternatives were inspected; they were not installed or benchmarked here.

## Validation so far

- Camera/contract/SfM targeted suite: 26 passed (4.67 s).
- Boundaries/cycles/identity/camera/contract/existing plan suite: 32 passed (8.36 s).
- Shared-wall visibility/damage scoring/assessment/boundaries: 12 passed (2.85 s).
- Shared-camera SfM experiment and conditioned RGB replay described above.
- Survey/calibration/ablation/accuracy/repeatability targeted suite: 28 passed
  (6.22 s). Expanded full suite: 105 passed (19.87 s), before adding the RGB
  correction-off regression; that targeted six-test file passes (1.24 s).

The first full replay against the earlier checkpoint expectations verified three
cases, but the video case no longer satisfies its historical partial-output claim.
Conditioning depth on the actual estimated camera rejects the public clip's global
metric prior. The failed reproduction is retained in
`demo/phase3_remaining/reproduction`. This is a stricter failure outcome, not a
video capability improvement. A second replay crossed the same bound in the other
direction and did not reproduce rejection (`reproduction_final`, retained).
After serializing matching, the full video replay `serial_video` produces a
partial result: 6/12 sparse registration, 6/6 derived views tracked, 257 supported
tracks across five views, log-ratio p80 **0.2476736**, no plan; 55.37 s reconstruction.
Its ledger records unchanged source. The current manifest expects this tested
partial state, retaining the **0.25** bound. It does not count failure cases as
successful captures. `metric_scale_attempt.json` records verified sparse/model depth samples
and the accepted scale evidence or rejection reason for reproducible diagnosis.

The actual overlap/fusion path was exercised with the generated two-room control
in two coordinate gauges (the SAME synthetic frames, deliberately not independent
captures): `demo/phase3_remaining/stitch_control/stitched`. It finds one verified
edge (2,000 visual inliers), one connected component, two room polygons, and
retains **194/194 unique merged frame IDs** with depths normalized to metres in
**10.59 s**. One-to-one room association correctly reports duplicate source-room
identities as unresolved. This cannot count as a same-tier physical repeat or a
strict photo-property acceptance pass. The second-gauge reconstruction's ledger
records unchanged source.

The actual identical-input correction on/off synthetic control keeps two rooms
in both modes. It compares 97 shared frames, union footprints 20.000019 / 19.998554
m², and no verified loops. Maximum camera change is approximately 1e-15 m, so
`verified_drift_correction_demonstrated` is **false**. Tiny voxel/plane differences
are not reported as drift repair. This synthetic run cannot close the required
physical multi-room drift row.

Further targeted registration/intake/contract suite: **29 passed (7.99 s)**.
Expanded full suite before the last deterministic-Torch flag: **110 passed
(19.01 s)**. The final source/reproduction results follow.

### Final verified source checkpoint

- The last opening/fallback changes pass their targeted suite: **24 tests in
  5.37 s**.
- Fresh isolated-source full suite: **113 passed in 22.73 s**, under
  `demo/phase3_remaining/isolated_source_v2`. Package import was independently
  checked to resolve within that copy; it has no `datasets/` or previous `demo/`
  assets. It reuses the installed workstation environment, so this is not a
  clean-machine installation or timing claim.
- [Final reproduction summary](../demo/phase3_remaining/reproduction_verified_v2/reproduction.json):
  **4/4 cases verified, 25/25 declared claims passed**, none skipped/historical.
  Each run records `code_changed_during_run: false` and a written assessment.
  Photo/video/LiDAR nonzero exits are expected incomplete outcomes, not successful
  assignment captures.
- [Three-page checkpoint PDF](../demo/phase3_remaining/technical_checkpoint_verified_v2/technical_checkpoint.pdf)
  was generated from those four fresh cases and inspected visually on all three
  rendered pages. It has no clipping/overlap and remains explicitly
  `final_submission: false`. Full ledger hashes and measured timings are in its
  companion `report_metadata.json`.
- Final source comparison confirms all **37 Python modules** match the tested
  isolated copy. The actual `import-survey` CLI rejects the blank template with
  exit 1; its log is `demo/phase3_remaining/blank_survey_cli.log`. Git whitespace
  validation passes with CRLF-aware settings. No commits or pushes were made.

| Fresh case | Geometry outcome | Reconstruction s | Total capture s |
|---|---|---:|---:|
| Supplied extracted RGB photos | incomplete; 1/4 derived views; no closed plan | 54.59 | 55.93 |
| Public video proxy | partial; 6/12 sparse originals, 6/6 derived views; no plan | 57.78 | 58.13 |
| Supplied single-room LiDAR | incomplete boundary; 115/115 tracked; no plan | 11.84 | 33.05 |
| Generated two-room control | research proposal; two rooms, one adjacency | 9.39 | unavailable: normalized input |

The control's ceiling and interval gates still fail. No fresh case satisfies the
complete assignment contract. Timings exclude first model/asset installation.
Passing reproduction checks establish the stated outcomes, including failures.

### Requirement disposition

The approved plan's complete-requirement statuses are not replaced with green
rows for component function presence. The following maps the remaining holds
back to its REQ IDs.

| REQs | Locally completed paths | What still prevents acceptance |
|---|---|---|
| 01, 04, 06, 39 | Stock-route documentation, supplied sensor intake, CPU operation, provenance/disclosures | Literal operator rehearsal, native/current-app exports and measured device evidence |
| 02, 03, 05, 07-10, 17-18, 28-29 | RGB feasibility path, verified poses/fusion/identity, supported geometry/openings, common contract, CLI and rendering | Strict RGB and supplied geometry remain incomplete; all-tier measured property output and accuracy are not proved |
| 11-13, 20, 40 | Face-aware damage projection, conservative fired rules/inspection scope, independent class/extent scorer | Furnished two-class damage and clean/adverse-condition annotations; validated detector behavior |
| 14-15 | Frozen record builder, producer-bound property-grouped fitting and independent audit | Adequate independent calibration/audit properties and complete measurement groups |
| 16 | Internal validation explicitly separated from official acceptance | Published schema absent; external-spec hold |
| 19, 21-27, 30, 38 | Benchmark audit, direct-survey importer, detection/repeat/drift/consumer scorers | Same measured property with three rooms plus connector across tiers, independent repeat, raw truth and actual two-room app export; effective physical drift demonstration |
| 31 | Prospective declaration/snapshot/replay/diff and integrity checks | A future own worst measured gate declared before fixing; raw measured before/after |
| 32-37, 41-42 | Saved plan/design/decisions, portable tests, fresh verified development reproduction, checkpoint PDF and failure/integrity checks | Genuine milestone history, measured final bundle/report, official rule resolution, timed clean install/fresh result and unseen-phone rehearsal |

REQ-04 and rendering/rules/scope have tested local implementations as in the
approved plan; their full all-tier physical acceptance is a separate obligation.
The missing Round 1/LiDAR wall definition remains unavailable. No assumptions,
synthetic properties or undocumented scale controls were introduced to close it.

## Acceptance dependencies that remain

Strict RGB still lacks complete native-photo/property reconstruction and measured
accuracy; no available data establish cm accuracy. The physical benchmark needs
three nonconnector rooms plus a connector, furnished two-class damage/clean
annotations, identical property across all tiers, independent repeat, laser/tape
truth, actual two-room consumer export/version and calibration/audit properties.
Official schema/Round 1 definitions, prospective worst-measured-gate fix,
clean-machine timing and unseen-phone rehearsals are still pending. Component
success must not be presented as any of these acceptance results.

## Files changed in this remaining-gap pass

This list identifies this pass's work rather than claiming every dirty file in
the workspace was changed here. Earlier Phase 3 changes remain intact.

- Added `floorplan/pose_graph.py`, `damage_evaluation.py`, `survey.py` and
  `calibration_records.py` for verified constraints/identity and independent
  annotation, survey and calibration evidence paths.
- Updated `floorplan/rgb_metric.py`, `sfm.py`, `ingest.py`, `rgbd.py`,
  `mapping.py`, `stitching.py`, `workflow.py` and `openings.py` for camera/depth
  consistency, capture accounting, deterministic matching, metric registration,
  pose correction modes, property fusion and observed opening handling.
- Updated `floorplan/damage.py`, `ablation.py`, `assignment_gates.py`,
  `repeatability.py`, `provenance.py`, `uncertainty.py`, `benchmark.py` and
  `cli.py` for face visibility, independent evaluation and producer binding.
- Added `tests/test_rgb_camera_consistency.py`, `test_pose_boundaries.py`,
  `test_damage_validation.py`, `test_survey_records.py`,
  `test_metric_registration.py`; updated `test_ablation.py`, `test_ingest.py`,
  `test_openings.py` and `test_phase3_contract.py`.
- Updated the CPU dependency lock (`requirements/windows-cpu.txt`), README,
  Phase 3 design/status/operations, assignment compliance/brief map and this ledger; updated
  `docs/benchmark/phase3_checkpoint_reproduction.json` with current verified
  development outcomes. The approved implementation plan stays unchanged.

New CLI paths are documented in [operations](PHASE3_OPERATIONS.md). Real data
remain outside inference truth inputs and outside the small tracked fixtures.

## Recommended next acceptance sequence

1. Supply native 2/4/8 stills and a native video of one furnished room, with an
   independently surveyed floor, every wall, ceiling and opening. Include doorway
   context. Run inference before evaluating the sealed truth. The first goal is
   complete supported geometry; then score dimensions and detection errors.
2. If a required measured gate fails, freeze that baseline and evaluator and make
   the prospective declaration before the next corrective producer change.
   Existing changes in this pass cannot satisfy that prospective requirement.
3. Expand to the required three rooms plus connector, all tiers, independent
   repeat and labelled two-class damage/clean controls. Obtain an actual named,
   versioned consumer export for two of those rooms.
4. After the measurement recipe freezes, collect adequate independent calibration
   properties and separate audits; refit after any subsequent producer change.
5. Resolve the official schema/Round 1 definitions, regenerate the measured bundle
   and final report, and perform clean-machine and unseen-phone rehearsals.

This sequence is a validation path, not a claim that measured data alone will fix
RGB registration or incomplete geometry. Those capabilities remain engineering
risks until the native and measured runs succeed.
