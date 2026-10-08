# Sparse photo overlap diagnosis

## Question and prediction

The existing 2/4/8 RGB-only trials sampled widely spaced views from a supplied
LiDAR capture's RGB stream and produced no sparse model. Before changing matching
code, test whether a contiguous, image-only subset from that same stream can
register. If overlap is the main issue, some 4- or 8-view groups should register;
this would demonstrate an overlap-sensitive SfM path, not validate independent
phone stills or metric plans. Failure of every group would point toward a broader
camera/matching issue.

## Method

- Source: `demo/given_single_room_run_v2/intake/frames/rgb_*.png` (1920x1440).
- Groups: consecutive frames starting at 0 and 80, with 2, 4 or 8 images each.
- Reconstruction: current `floorplan.sfm.reconstruct_rgb`, exhaustive matching,
  default `SIMPLE_RADIAL` camera, no supplied camera calibration.
- Inputs passed to inference: copied RGB images only. No LiDAR depth, poses,
  calibration stream, ground truth, or scale references were read by SfM.
- Outputs: ignored local artifacts in `demo/sparse_overlap_trials/`.

## Result

| Start frame | Views | Registered | Sparse points | Status |
|---:|---:|---:|---:|---|
| 0 | 2 | 0/2 | 0 | no model |
| 0 | 4 | 0/4 | 0 | no model |
| 0 | 8 | 8/8 | 223 | reconstructed |
| 80 | 2 | 0/2 | 0 | no model |
| 80 | 4 | 4/4 | 62 | reconstructed |
| 80 | 8 | 7/8 | 106 | partial |

The prediction is partly supported: two 4-view and one 8-view groups register,
while the 2-view trials and one 4-view group fail. Thus overlap and view choice
matter, but this tiny test does not isolate parallax from texture, blur, or camera
model effects. Successful sparse registration is still unscaled and is not a
dimensioned room plan.

## Decision and limits

Do not relax COLMAP geometric checks based on this result. Do not claim the photo
tier works: these are adjacent video-derived views from the provided LiDAR scan,
not independently captured 2-8 phone photos. The current project has no supplied
standalone photo set with survey truth. The next useful photo-phase change needs
an allowed 2-8 still capture set (or an explicitly suitable public set) with
independent dimensions; otherwise implementation can only establish a capture-
quality/SfM diagnostic, not the photo accuracy gate. Any later view-selection
change must preserve the user's input-count contract and report excluded images.

## Real mobile RGB check

To check a public phone capture before waiting for the planned physical-phone
session, the same image-only reconstruction was run on held-out ARKitScenes scene
41418140. Eight RGB frames were sampled evenly across a four-second segment;
the 2- and 4-view inputs used subsets of those same timestamps. ARKitScenes stores
this `lowres_wide` stream at 256x192. Inference used only those PNGs and the
default camera model; its separate depth, intrinsics, trajectories and FARO scan
were not read by reconstruction.

| Views | Registered | Sparse points | Status |
|---:|---:|---:|---|
| 2 | 0/2 | 0 | no model |
| 4 | 0/4 | 0 | no model |
| 8 | 2/8 | 56 | partial |

This is a real iPhone RGB failure case for the low-resolution stream, not an
accuracy result. It makes the missing requirement concrete: we need a supported
full-resolution still/video input or a benchmark where the source views match the
assignment capture tier. Do not use this 25%-registered sparse cloud as a plan.

## Controlled 2/4/8 photo-count check

The public ICL-NUIM living-room RGB sequence provides an additional controlled
test with 640x480 images, documented camera intrinsics and a metric room mesh.
The first 22 prepared frames span 3.5 seconds. Evenly spaced 2-, 4- and 8-image
subsets were reconstructed with exhaustive matching and the published PINHOLE
intrinsics (`481.2,480,319.5,239.5`). Depth, camera trajectory and mesh were not
passed into reconstruction. Outputs are in the ignored local directory
`demo/icl_sparse_photo_trials2/`.

| Views | Registered | Sparse points | Status |
|---:|---:|---:|---|
| 2 | 2/2 | 126 | reconstructed |
| 4 | 4/4 | 220 | reconstructed |
| 8 | 8/8 | 491 | reconstructed |

After the seeded single-thread SfM change, a fresh 2/4/8 rerun produced
126/220/491 sparse points respectively. The earlier 221/488 counts above are
historical observations from the original run; the final repeatable counts are
recorded in the E2E status ledger. This small change reflects triangulation
ordering and does not change the arbitrary-scale limitation.

This is synthetic imagery and a known calibrated camera, so it does not establish
performance on phone stills with unknown calibration. COLMAP's reconstruction is
still up to arbitrary scale; the mesh was not used to fit scale or evaluate a
floor plan in this trial. The result shows that the 2-image entry path can work
when overlap, parallax and calibration are favorable. It does not close the
metric photo-plan gate.
