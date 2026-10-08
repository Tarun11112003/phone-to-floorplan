# External components, attribution and evaluated alternatives

Finalization uses the existing local research record; no new external research
or model experiment is performed. Architecture and claims are bounded by
[validation](BENCHMARK_RESULTS.md). Portable research records are published with original-byte provenance; private
original records are retained locally.

## Components actually used

| Component | Use | Existing recorded terms /provenance | Final state |
|---|---|---|---|
| COLMAP /PyCOLMAP4.2.1 | Production SIFT SfM and isolated native mapping controls | Upstream COLMAP BSD terms; package version in environment/ledgers | Baseline retained |
| OpenCV, NumPy, SciPy, Shapely | Projection, poses, masking, structural geometry | Installed package provenance and upstream notices; observed pins in requirements | Baseline dependencies |
| Open3D0.19 | Pose graph/registration support | Existing dependency and upstream notices | No new TSDF backend adopted |
| OpenMVS | Optional research dense reconstruction binary | Recorded AGPL-3.0 upstream terms; separate pinned installer | Not bundled; not the strict-photo metric solution |
| MoGe-2 ViT-S | Opt-in camera-conditioned learned metric RGB experiment | Recorded MIT code/card, bundled DINOv2 Apache-2.0; revision/model SHA in operations/original records | Experimental, model_scaled, unpromoted |
| DISK /LightGlue | Isolated feature/matching comparisons | Recorded Apache-2.0 code/checkpoints; upstream notices in isolated cache | Not adopted into production |
| XFeat /XFeat-trained LightGlue variant | Isolated transition comparison | Recorded official revisione92685f, Apache-2.0 checkpoints; Kornia0.8.1 strict loading; original provenance retained | Experimental; registration chain CLOSED |
| TUM /ICL /ARKitScenes research data | Earlier decoding/controlled or provisional sensor comparisons | Original dataset SOURCE/README records and applicable separate data terms | Historical evidence; not required physical benchmark |
| Supplied assessment captures | Primary sensor/source-support development evidence | Provided locally for this task; original files/hashes retained | Separate local handoff, not a public redistribution licence claim |

This table records existing reviews, not a new legal audit. Code, weights,
binaries and datasets have separate rights. Dependencies are not relicensed by
this repository. No restricted/unlicensed code, model or asset is newly
incorporated during finalization. Optional upstream code/weights remain outside
the source archive; retained relevant notices/provenance accompany the evidence
archive. Fetch/use them only under their actual upstream terms.

The locally retained LightGlue/XFeat notice texts and exact source pins are
indexed in [attribution](attribution/README.md). No project licence is invented.

## Engineering decisions

We evaluated alternative feature, calibration, registration, geometry and
fusion approaches against fixed inputs and correctness guards. More matches,
fewer components, a joint camera model or lower reprojection residual were
insufficient adoption evidence. SIFT remains the production baseline.

Recorded height-mode and projection-based geometry approaches informed bounded
support hypotheses, not a wholesale architectural copy. Structural neural
models/TSDF backends remain design options; this finalization does not claim
they were executed. The floor audit shows observation loss before current
fusion, so replacing fusion is not justified by the measured failure.

No alias-based reference comparison is used in the final narrative. The
consolidated [component research](ASSESSMENT_COMPONENT_RESEARCH.md) preserves
the evaluated approaches and primary source links. Past next-step suggestions
are historical: development is frozen.

## External references retained for provenance

- [COLMAP](https://github.com/colmap/colmap)
- [OpenMVS](https://github.com/cdcseacave/openMVS)
- [MoGe](https://github.com/microsoft/MoGe)
- [LightGlue](https://github.com/cvg/LightGlue)
- [XFeat](https://github.com/verlab/accelerated_features)
- [Stray Scanner export format](https://github.com/strayrobots/scanner/blob/main/docs/format.md)

Links identify the recorded upstream sources. Versions, usage and measured
results are drawn from retained local evidence, not assumed from today's upstream.
