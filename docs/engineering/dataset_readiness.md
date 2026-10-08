# Dataset sufficiency and pre-phone readiness

Updated . This inventory distinguishes pipeline integration evidence
from independent floor-plan accuracy truth. A dataset can exercise a tier without
qualifying that tier's centimeter-accuracy gate.

## What the local datasets establish

| Dataset | Present evidence | Good for | Cannot establish |
| --- | --- | --- | --- |
| `Given_dataset` | Three Stray Scanner session exports with RGB MP4, depth/confidence PNGs, camera intrinsics, odometry and IMU. Final-source replays produce one partial room per scan with 34.78%, 10.29%, 8.00% camera coverage. RGB-only supplied video registers 2/24 views, with no closed room. See [supplied-data pass](implementation_history.md#supplied-capture-reconstruction-integration). | Highest-priority supplied-data integration tests for LiDAR and synchronized video/RGB. | Surveyed wall lengths, ceilings, openings, room outline, repeatability or a scored floor-plan truth. The sensor trajectory/depth are inference inputs, not independent plan truth. |
| ARKitScenes local subset | Three iPhone RGB-D sequences with intrinsics/trajectory and three local FARO PLY scans (one development, two held-out). The development venue has one provisional manually selected room polygon; held-out scans have inspection plots but no vetted room polygon. | Photo/video RGB-only ablations; mobile depth and trajectory integration; reference-only geometry comparison while FARO geometry is withheld from inference. | Tape-measured room dimensions, complete room/opening labels, damage/scope truth or one shared 3+ room property across all tiers. One provisional development annotation is not independent field certification. |
| ICL-NUIM living room | Synthetic RGB-D sequence, known camera calibration and reference mesh. | Controlled RGB-only 2/4/8 SfM feasibility; metric evaluation against synthetic geometry where the reference is withheld from inference. | Consumer-phone realism, multiroom topology, damage, native video behavior or field accuracy. |
| TUM `freiburg1_room` | Public RGB movie and timestamped ground-truth camera trajectory. | Video decode, frame selection, camera-motion and SfM integration. | Measured room polygon/dimensions; the trajectory is not a floor-plan survey. |
| `controlled_multimodal_v3` | Analytic two-room synthetic scene with reference plan and simulated photo/video/LiDAR captures. | Deterministic evaluator, export, regression and negative-case tests. | Independent property generalization, genuine sensor noise, a 3+ room connector benchmark, or real capture accuracy. |

Therefore, **the supplied dataset is sufficient to exercise the current LiDAR
ingestion and expose failures, but it is not sufficient to prove the requested
accuracy.** Existing public data adds RGB, video, calibration and geometry checks;
it does not replace the missing same-property survey benchmark.

## Public benchmark candidates

| Source | Potential value | Access/fit decision |
| --- | --- | --- |
| [ARKitScenes](https://github.com/apple/ARKitScenes) | iPhone RGB-D, camera intrinsics/trajectory and high-resolution stationary laser scans. | Best immediately relevant public mobile-sensor comparison. Three RGB-D scenes and their FARO reference PLYs are local. One development room has a provisional polygon annotation; two held-out PLYs still need blind room annotation and review. The scan data does not automatically supply tape dimensions or complete room/opening truth. |
| [Multi-view room-layout benchmark](https://github.com/ghanning/MultiViewRoomLayout) | Multi-view image tuples, room-layout ground truth, evaluation scripts, and a multi-room split. | Strong next photo/layout benchmark candidate. Underlying ScanNet++/2D-3D-Semantics/Aria assets and their access terms must be checked separately; layout tuples do not exercise the required LiDAR/video workflow by themselves. |
| [ScanNet++](https://scannetpp.mlsg.cit.tum.de/scannetpp/) | High-resolution laser scans, DSLR views, and commodity iPhone RGB-D; recent releases include iPhone benchmark material. | Best potential same-scene multi-sensor source, but download requires account/application approval and dataset terms. It is not presently local and should not be represented as acquired/usable. |
| [Zillow Indoor Dataset (ZInD)](https://github.com/zillow/zind) | Real home panoramas, room layouts, openings and merged floor plans. | Not selected for this company take-home: Zillow says the data is academic/non-commercial only and prohibits using it to improve a company product absent separate permission. Also uses 360° panoramas rather than the required ordinary photos. |
| [Structured3D](https://structured3d-dataset.org/) | 3.5K synthetic designed homes, photorealistic views and rich 3D structure annotations. | Strong synthetic layout benchmark in principle, but dataset download requires agreement approval and its separate terms. No LiDAR/phone realism; not presently available locally. |
| [Realsee3D](https://dataset.realsee.ai/) | Recent release reports real LiDAR RGB-D scenes and synthetic scenes with depth/semantic assets. | Potential multimodal research benchmark, but access requires an approved data-use agreement and the site says commercial use needs separate licensing. Do not use for the take-home without permission; ground-truth floor plans are listed as forthcoming. |
| [HouseLayout3D](https://houselayout3d.github.io/) | Real multi-floor wall/floor/ceiling/door/window/stair layout annotations derived from Matterport3D, with poses and intrinsics. | Useful topology/structure reference, but the annotation repository is not a raw phone RGB-D/video/LiDAR capture set; underlying imagery has separate Matterport access/terms. |
| Kaggle indoor/floor-plan competitions | Some contain floor-plan drawings, area labels, or non-visual indoor localization telemetry. | No located Kaggle set matches phone RGB still/video/LiDAR input paired with surveyed room dimensions. Floor-plan-from-floor-plan data cannot validate image-to-plan capture reconstruction. |

No additional restricted or approval-gated dataset is silently downloaded into
the benchmark. Existing public datasets and their terms remain separate from
third-party source-code/model licenses.

The three FARO PLYs are already present under
`datasets/arkitscenes/references/{416418,416411,416407}/`. Reference geometry is
used only for scoring/inspection, never as an inference input. The development
venue `416418` has a provisional region-selected polygon and inspection plot.
The two held-out venues have raw FARO clouds and inspection plots, but no blind,
reviewed room-polygon annotation yet; they must remain unscored until that is
created. This corrects the earlier inventory statements that the scans were
remote/not local.

## Phase status before a phone capture

| Assignment phase | Ready evidence available before phone | Remaining gate |
| --- | --- | --- |
| 0. Acceptance definitions/data | Inventory, internal provisional metrics, capture/truth templates and assignment map exist. | Official schema/Round 1 gates are absent; no one-property, three-room, all-tier laser survey, independent repeat, damage annotations or consumer-app export. |
| 1. Photos | 2/4/8 still intake, RGB-only SfM, overlap diagnostics and report coverage run; supplied, ARKitScenes and ICL subsets have been exercised. | Metric photo scale/geometry is not solved. Need high-overlap 2–8 phone views and held-out dimension truth. |
| 2. LiDAR/ceiling | Given-dataset parser and three raw sessions have been replayed; partial results are reported honestly. Controlled ceiling tests and depth-reference probes exist. | No closed surveyed plan from the supplied sessions; no independent ceiling/footprint score. |
| 3. Video | TUM and supplied RGB MP4 ingest/reconstruction paths have been exercised. | Native iPhone video, stable full-room registration, drift, scale and measured gate are pending. |
| 4. Property stitch | Manifest stitch path now has a deterministic three-room chain test, with analytic zero-error output and an inconsistent-anchor rejection test. | Physical independently captured rooms, visual connector evidence and cross-tier 3+ room truth remain untested. |
| 5. Damage/scope | Review overlays, heuristic candidates and report fields exist. | Annotated restoration damage truth; precision/recall, extent error and defensible quantities are absent. |
| 6. Uncertainty | Property-held-out calibration utility and explicit uncalibrated status exist. | Enough independent measured-property residuals to fit and validate intervals; no calibrated output claim. |
| 7. Output/evaluator | Internal JSON schema, SVG/DXF/CSV/HTML reports, provisional evaluator and coverage table exist. | Published schema and missing official gate definitions; all actual gates not passing. |
| 8. Benchmark/fix loop | Reproducible experiments and fix declarations/results are recorded. | Shared surveyed all-tier benchmark, independent repeat, consumer comparison and official worst-gate score. |
| 9. Walk-in/demo | CLI one-command flow and offline review report exist; supplied data can be replayed locally. | Clean examiner-machine run, unseen iPhone, cold setup under 15 minutes, laser comparison and final scored report. |

**Pre-phone readiness conclusion:** the software can accept and report the
available media, and the deterministic components can be rehearsed. It is not
assignment-complete or centimeter-validated. The later phone session should be
treated as the first real capture/evaluation stage, not a final confirmation of a
finished accurate system.
