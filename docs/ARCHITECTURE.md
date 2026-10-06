# Architecture and visual flows

Personal engineering reference. Updated 2026-10-05. The target is a code-driven system for restoration estimators: photos, video, and mobile LiDAR observations become editable metric room geometry, stitched plans, dimensions, quantities, and source evidence. **The full three-tier requirement is not yet met.** Current code supports actual mobile LiDAR, concave multiroom layouts and verified RGB-D capture stitching. RGB-only metric clouds remain incomplete as floor plans. See the V2 implementation link below for the current architecture; this page retains the original research diagrams.

![Historical baseline architecture](figures/architecture.png)

## Current implementation update

The implementation has advanced beyond the baseline diagrams on this page.
Use [restoration flow](RESTORATION_FLOW.md) for the current executable flow,
internal assessment contract, uncertainty and damage scope, and explicit remaining
gaps. [Open-source decisions](OPEN_SOURCE_DECISIONS.md) records actual model experiments.
The [V3 implementation](V3_IMPLEMENTATION.md) documents the geometry baseline.
The diagrams below preserve the initial target and baseline for comparison.

## 1. Intended three-tier architecture

Green = shared output contract. Blue = capture/reconstruction. Amber = explicit measurement/review gates. This diagram describes the intended system; the implementation map below distinguishes delivered components.

```mermaid
flowchart TB
  subgraph capture[CAPTURE ADAPTERS]
    direction LR
    P["Photos<br/>overlapping calibrated views"]
    V["Video<br/>timestamps and keyframes"]
    L["Mobile LiDAR / RGB-D<br/>depth, RGB, calibration, poses"]
  end
  P --> QA["Capture QA<br/>blur, overlap, lens distortion, orientation"]
  V --> QA
  QA --> RGB["Visual reconstruction<br/>SfM / SLAM + depth proposals"]
  L --> D["Depth QA and registration<br/>units, confidence, synchronization"]
  RGB --> S{"Metric scale<br/>observable?"}
  REF["Measured control<br/>distance, marker, or camera height"] --> S
  S -->|yes| G["Shared scene representation<br/>metric points, poses, gravity, uncertainty"]
  S -->|no| U["Relative geometry only<br/>withhold metric dimensions"]
  D --> G
  G --> STRUCT["Structural extraction<br/>floor, walls, doors, room polygons"]
  STRUCT --> GRAPH["Room pose graph<br/>shared doorway / wall constraints"]
  GRAPH --> OPT["Global optimization<br/>loop closure and consistency"]
  OPT --> REVIEW{"Evidence and<br/>geometry adequate?"}
  REVIEW -->|partial| FIX["Review / correction / recapture"]
  FIX --> GRAPH
  REVIEW -->|accepted| OUT["Vector plan + quantities<br/>SVG / DXF / JSON / CSV"]
  OUT --> AUDIT["Measurement provenance<br/>source frames, residuals, review status"]
  classDef input fill:#e6effb,stroke:#416a99,color:#122d4d;
  classDef gate fill:#fff1d7,stroke:#c0872e,color:#5a3b12;
  classDef output fill:#e3f3eb,stroke:#32745c,color:#174233;
  class P,V,L,QA,RGB,D,G,STRUCT,GRAPH,OPT input;
  class S,REF,U,REVIEW,FIX gate;
  class OUT,AUDIT output;
```

Photos and ordinary RGB video cannot geometrically determine absolute scale without a metric observation. A learned metric-depth estimate is a hypothesis whose measurement error must be checked. LiDAR supplies metric depth but still has calibration, drift, occlusion, and boundary-estimation error. The architecture therefore records scale provenance explicitly for every tier.

## 2. Historical baseline implementation

```mermaid
flowchart LR
  subgraph rgb[RGB EXPERIMENT]
    P[Photo directory] --> C[PyCOLMAP features and matching]
    V[Video file] --> F[FFmpeg frame extraction]
    F --> C
    C --> M["Sparse cameras and cloud<br/>coverage report; scale unknown"]
    M -. missing .-> A["Metric alignment and<br/>automatic room extraction"]
  end
  subgraph depth[AUTOMATIC RGB-D BASELINE]
    PAIR[Calibrated RGB/depth pairs] --> FEAT[SIFT and depth-supported matches]
    FEAT --> POSE["PnP RANSAC<br/>metric 3D refinement"]
    POSE --> CLOUD["Fuse estimated poses<br/>2 cm voxel deduplication"]
    CLOUD --> PL[Robust plane extraction]
    PL --> REC["Opposing walls<br/>rectangular-room proposal"]
  end
  subgraph assisted[ASSISTED GEOMETRY BASELINE]
    ANN["Marked image/video corners<br/>calibration and scale"] --> PROJ[Ground-plane projection]
    PROJ --> STITCH[Shared doorway anchor alignment]
  end
  REC --> EXP[SVG / DXF / JSON / CSV]
  STITCH --> EXP
  classDef ready fill:#e3f3eb,stroke:#32745c,color:#174233;
  classDef experiment fill:#e6effb,stroke:#416a99,color:#122d4d;
  classDef missing fill:#fff1d7,stroke:#c0872e,color:#5a3b12,stroke-dasharray: 5 5;
  class PAIR,FEAT,POSE,CLOUD,PL,REC,ANN,PROJ,STITCH,EXP ready;
  class P,V,F,C,M experiment;
  class A missing;
```

`floorplan/rgbd.py` reads only `sequence.json`, RGB images, and depth images. It estimates every relative pose. It never reads ground-truth trajectories, floor polygons, semantic masks, or the reference scene mesh. It currently assumes a single rectangular Manhattan room, an approximately level initial camera, and observable opposing walls. It does not estimate doors, room count, stairs, slanted walls, or native phone LiDAR formats. Four observed planes are necessary for a proposal; that check is not proof of a complete, correctly segmented room.

`floorplan/pipeline.py` supplies the separate assisted baseline. Its doorway alignment is tested on the two-room synthetic example. There is currently **no demonstrated automatic stitch from two independently reconstructed real rooms**. A diagram arrow must not be read as evidence that this missing integration is complete.

## 3. Benchmark isolation and feedback

```mermaid
flowchart TB
  DATA["Public dataset acquisition<br/>source URL, license, hash"] --> SPLIT[Dataset adapter]
  SPLIT --> INPUT["Inference inputs<br/>RGB, depth, camera intrinsics"]
  SPLIT --> TRUTH["Held-out reference<br/>mesh geometry and trajectory"]
  INPUT --> RUN[Reconstruction process]
  RUN --> PRED["Saved predictions<br/>plan, poses, cloud, stage status"]
  PRED --> EVAL[Evaluation process]
  TRUTH --> EVAL
  EVAL --> NUM["Errors and coverage<br/>no scale fit for dimension scoring"]
  NUM --> REPORT["JSON metrics + visual report<br/>pass / fail / unsupported by tier"]
  REPORT --> CHANGE["Choose next improvement<br/>tracking, coverage, wall fit, stitching"]
  CHANGE --> NEW[Next version and separate validation scenes]
  NEW --> RUN
  classDef input fill:#e6effb,stroke:#416a99,color:#122d4d;
  classDef truth fill:#f0e8f8,stroke:#84609d,color:#4a2c60;
  classDef result fill:#e3f3eb,stroke:#32745c,color:#174233;
  class DATA,SPLIT,INPUT,RUN,PRED input;
  class TRUTH truth;
  class EVAL,NUM,REPORT,CHANGE,NEW result;
```

The mesh-sampled `benchmark-icl` command is deliberately a different experiment: it samples known wall surfaces and adds noise. Its semantic wall selection and complete coverage make it an **oracle component test**. Its sub-centimetre result cannot be substituted for the raw RGB-D experiment's error.

## 4. Measurement and acceptance contract

```mermaid
stateDiagram-v2
  [*] --> InputsChecked
  InputsChecked --> RelativeOnly: no metric scale
  InputsChecked --> Tracking: metric observations available
  Tracking --> Partial: tracking fails or coverage missing
  Tracking --> Geometry: sufficient registered observations
  Geometry --> Partial: opposing walls unavailable
  Geometry --> Proposal: supported room polygon
  Proposal --> ReviewRequired: assumptions or uncertainty remain
  Proposal --> Evaluated: held-out measurements available
  Evaluated --> TargetMissed: error exceeds threshold
  Evaluated --> CasePassed: meets target on this case
  CasePassed --> FieldValidation: expand properties and capture tiers
  RelativeOnly --> [*]
  Partial --> [*]
  ReviewRequired --> [*]
  TargetMissed --> [*]
```

Candidate field target: P95 edge-length error <=3 cm and stitched corner error <=5 cm, with accepted-output coverage reported. Current single-room evaluation has only two independent side lengths, so it reports both errors and their maximum. It does not produce a statistically meaningful population P95 or a stitched-corner score. Quantity errors are reported separately in square metres. Camera-trajectory error is a tracking diagnostic and cannot replace dimension error.

## 5. Decisions to explain in the take-home

| Decision | Reason | Evidence or limit |
| --- | --- | --- |
| Separate inference and evaluation processes | Prevent accidental use of answer geometry | RGB-D module has no ground-truth input |
| Start with classical geometry | Obtain a measurable baseline on the available CPU | SIFT/PnP/depth refinement runs locally; no model training |
| Preserve incomplete states | Missing observations should remain visible | First RGB-D version stopped at incomplete geometry |
| Keep a constrained rectangle model | Demonstrate a small automated vertical slice | Cannot represent L-shaped or multi-room layouts |
| Compare metric dimensions without fitted scale | Preserve real scale error | Evaluator only permutes the two rectangle axes |
| Treat frames/photos from one sequence as one scene | Avoid inflating evidence | RGB/photo/video tests are correlated views of ICL trajectory 2 |
| Use global constraints next | Pairwise pose errors accumulate | Refined RGB-D tracking and dimensions still miss target |

See [dataset research](DATASETS.md), [measured results](BENCHMARK_RESULTS.md), and [personal design notes](../DESIGN_NOTES.md).
