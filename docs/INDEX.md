# Assessment documentation index

The current implementation is the final
development state; this handoff adds documentation and packaging only.
The project is **ready for honest engineering review, not full assessment acceptance**.

## Evaluator reading order

| Read | Purpose |
|---|---|
| [Final QA](FINAL_QA.md) | Initial-state audit, actual runnable checks and final handoff boundaries |
| [README](../README.md) | Inputs, behavior, outputs, status and setup |
| [Technical report](TECHNICAL_REPORT.md) / [five-page PDF](TECHNICAL_REPORT.pdf) | Concise engineering account and final assessment status |
| [Architecture](ARCHITECTURE.md) | Actual branches, modules, guards and tradeoffs |
| [Processing flow](RESTORATION_FLOW.md) | End-to-end execution and output availability |
| [Validation](BENCHMARK_RESULTS.md) | Metric → result → evidence → status → limitation |
| [Compliance matrix](ASSIGNMENT_COMPLIANCE.md) | Required inputs, outputs, benchmarks and gates |
| [Fix loops](FIX_LOOP.md) | Shipped fixes versus diagnostic/rejected investigations |
| [Limitations](LIMITATIONS.md) | What, why, impact and current status |
| [Reproduction and package](PHASE3_OPERATIONS.md) | Real commands, assets, Git/source scope and missing dependencies |
| [Capture protocol](CAPTURE_PROTOCOL.md) / [device matrix](DEVICE_MATRIX.md) | Route 2 candidate; hardware and evidence limits |
| [Source/attribution decisions](OPEN_SOURCE_DECISIONS.md) | Dependencies, optional models and retained upstream notices |

The original [Applied AI.html](Applied%20AI.html) defines success. Its published
schema and earlier Round 1 definitions were not included and remain unresolved.

## Evidence navigation

[Curated evidence manifest](evidence/final_state.json) selects recorded metrics
from published reports with original-byte provenance, records source SHA-256 and exact JSON field paths,
and separates production, experimental, diagnostic and evaluation evidence.
The separate handoff bundle retains full records and selected native artifacts.
Published copies remove private path prefixes; original-byte provenance is
recorded separately. Portable publication does not prove exact native replay.

`docs/fixes/` and `docs/results/` retain detailed records. Older Phase 3,
V2/V3, design and roadmap documents are historical context. Their next-step
instructions are **superseded by the freeze**; they are not permission or a plan
to continue experiments. No failed experiment is promoted in this handoff.

The final Git tree contains the frozen implementation and required tooling.
A clean checkout is the intended submission. See [final QA](FINAL_QA.md) and
[Python/tool inventory](REPOSITORY_HYGIENE.md) for execution and cleanup scope.
Independent physical acceptance is not packaged.

## Editable visuals

Mermaid source lives in the architecture (two diagrams), processing flow,
validation and fix-loop documents. Readable SVG exports accompany the final
report: [architecture](figures/architecture.svg),
[validation](figures/validation.svg) and [fix loop](figures/fix_loop.svg).
`scripts/render_assessment_report.py` regenerates those exports and the PDF;
their boxes describe implemented stages or the explicitly labelled evidence
process, not an autonomous repair service.
