# Final limitations and impact

No additional algorithm experiment is planned
for this handoff. [Validation](BENCHMARK_RESULTS.md) provides the supporting
record and [compliance](ASSIGNMENT_COMPLIANCE.md) maps the assessment consequences.

| What | Why /existing evidence | Impact | Current status |
|---|---|---|---|
| Partial property reconstruction | Floor-only camera containment25/176; incomplete finite boundaries/inferred cells | Whole-property product and adjacency cannot be certified | PARTIAL |
| room_2 floor/ceiling unavailable | Retained plane support14.1246% <unchanged25% guard; ceiling exits without local floor | Height/net-wall quantities remain unavailable | PARTIAL; no fabricated fallback |
| Sampling/frame-selection support loss | Selected dense29.2154%, all-source raw44.0880%; native fusion loses no occupied cells | Resource policy discards useful observations; dense fused acceptance untested | DIAGNOSTIC; production unchanged |
| Unvalidated0.703 m notch | Footprint10.477367→9.945720m²; semantic/survey perimeter truth absent | Coverage gains cannot establish boundary accuracy | INCONCLUSIVE |
| Strict RGB metric/property solution incomplete | SfM scale ambiguous; learned metric path unpromoted | Mandatory photo/video whole-property gates not demonstrated | PARTIAL |
| RGB registration causality unresolved | Final saved-state replay not exact; landmark/sensor/model uncertainties remain | No solver fix can be defended from the chain | INCONCLUSIVE; investigation CLOSED |
| Learned alternatives not production | Match counts/joint membership failed geometry/adoption evidence | Experimental outputs cannot certify useful geometry or accuracy | Experimental only |
| Denser global LiDAR rejected | Increased containment changed an accepted polygon | Cannot substitute a plausible denser plan for preserved supported geometry | Rejected |
| Opening accuracy/recall unknown | Physical jamb/header/width truth and challenging-case labels absent | Missed/phantom/dimension gate unproven | NOT DEMONSTRATED |
| Damage classifier/extent validation absent | Candidate detector and surface fusion lack independent two-class/clean controls | Damage and scope are review evidence, not validated restoration diagnosis | PARTIAL |
| Independent accuracy/ground truth absent | Supplied depth/poses are capture inputs, not laser/tape truth | No centimetre-level claim across tiers | NOT DEMONSTRATED |
| Repeatability/drift field evidence absent | Same saved artifact replay is not repeat capture; no qualifying effective field on/off delta | Required repeat and drift gates unproven | NOT DEMONSTRATED /PARTIAL mechanism |
| Calibrated interval coverage absent | Adequate independent fitting/audit properties unavailable | Null or uncalibrated groups cannot be called90% field coverage | NOT DEMONSTRATED |
| Benchmark/consumer composition missing | Same-property3+rooms/connector, damage, repeats and original consumer export unavailable | Required benchmark and≥70% head-to-head cannot be scored | NOT DEMONSTRATED |
| Published specification gaps | Output schema and earlier Round1 gates absent from suppliedHTML | Internal evaluator remains provisional | NOT DEMONSTRATED |
| Device/cold setup route untested | Native HEIC/MOV/current app and nonengineer unseen rehearsal missing | No<15min clean machine or cold walk-in acceptance | NOT DEMONSTRATED |
| Reproduction portability incomplete | Raw/model assets excluded fromGit; historical native producer/path identities may need remounting; public text uses portable paths | Source/evidence integrity bundle is not every-number live regeneration | PARTIAL |

Physical closure requires independently identified room/perimeter/surface
measurements, the prescribed same-property three tiers and repeats, staged damage
annotations, calibration/audit properties and original consumer exports. None is
invented or manufactured for the deadline. The report's honest final status is
**reviewable partial implementation**, not complete floor/ceiling geometry,
centimetre-level accuracy or assessment acceptance.
