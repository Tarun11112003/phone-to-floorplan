# ARKitScenes held-out FARO reference review

Reviewed from the FARO scanner samples only. The mobile proposals
were not used to select wall runs or polygon corners. The existing inspection
images are quick wall-height projections of downsampled point clouds; they are
not complete floor plans.

| Venue | Scanner evidence | Review decision |
| --- | --- | --- |
| `416411` / video `41418140` | 42.9M source points; the sampled wall-height projection shows several interrupted perimeter-like wall runs, foreground/clutter returns, and gaps whose status (opening, occlusion, or missing coverage) cannot be resolved from this projection. | Do not publish a closed room polygon from this view. No reliable room extent/corner set can be selected without inspecting the full cloud at multiple heights and checking the associated mobile sequence. |
| `416407` / video `41418155` | 42.3M source points; the sampled projection spans a large elongated footprint with multiple internal wall planes and disconnected outer runs. It appears to cover multiple spaces, not one unambiguous room. | Do not force a one-room polygon. Requires room-by-room topology annotation and connector review across the full scan. |

The generated zoom plots are in the ignored local folder
`demo/arkit_reference_review/416411_zoom.png` and
`demo/arkit_reference_review/416407_zoom.png`. Existing extraction code can fit
lines inside explicitly selected regions, but it cannot determine which returns
belong to a room boundary or whether a gap is a doorway. Choosing regions or
closing those gaps by following a model proposal would contaminate the reference.

Therefore these two runs remain **unscored**. No `reference.json` was created,
and the benchmark results were not changed. The next defensible step is a
reference annotation pass over the full FARO clouds (multiple height slices or
interactive 3D inspection), with an explicit room/topology decision and a second
reviewer. If the room extents remain ambiguous, exclude the scene from metric
accuracy scoring rather than inventing a polygon. After reviewed references are
approved, rerun:

```powershell
& .\.venv\Scripts\python.exe -m floorplan.cli benchmark examples\public_benchmark.json --out demo\public_candidates_e2e_heldout
```

The FARO references remain scoring-only inputs and must not enter reconstruction.
