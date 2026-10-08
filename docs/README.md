# Assessment documentation index

The current implementation is the final
development state; this handoff adds documentation and packaging only.
The project is **ready for honest engineering review, not full assessment acceptance**.

## Evaluator reading order

| Read | Purpose |
|---|---|
| [Final QA](submission_qa.md) | Initial-state audit, actual runnable checks and final handoff boundaries |
| [README](../README.md) | Inputs, behavior, outputs, status and setup |
| [Technical report](technical_report.md) / [five-page PDF](technical_report.pdf) | Concise engineering account and final assessment status |
| [Architecture](architecture.md) | Actual branches, modules, guards and tradeoffs |
| [Processing flow](pipeline.md) | End-to-end execution and output availability |
| [Validation and decisions](validation.md) | Supplied-data results, controlled before/after numbers and adoption decisions |
| [Benchmark ledger](../benchmarks/report.md) | Metric → result → evidence → status → limitation |
| [Compliance matrix](compliance_matrix.md) | Required inputs, outputs, benchmarks and gates |
| [Fix loops](fix_loop.md) | Shipped fixes versus diagnostic/rejected investigations |
| [Limitations](limitations.md) | What, why, impact and current status |
| [Reproduction and package](reproducibility.md) | Real commands, assets, Git/source scope and missing dependencies |
| [Capture protocol](capture_protocol.md) / [device matrix](device_matrix.md) | Route 2 candidate; hardware and evidence limits |
| [Source/attribution decisions](third_party.md) | Dependencies, optional models and retained upstream notices |

The original [Applied AI.html](specification/applied_ai.html) defines success. Its published
schema and earlier Round 1 definitions were not included and remain unresolved.

## Evidence navigation

[Curated evidence manifest](../benchmarks/manifests/final_state.json) selects recorded metrics
from published reports with original-byte provenance, records source SHA-256 and exact JSON field paths,
and separates production, experimental, diagnostic and evaluation evidence.
The separate handoff bundle retains full records and selected native artifacts.
Published copies remove private path prefixes; original-byte provenance is
recorded separately. Portable publication does not prove exact native replay.

The [engineering index](engineering/README.md), investigation records and
`benchmarks/results/` retain the deeper evidence. Historical component records
remain available with their original input/producer scope. Their next-step
instructions are **superseded by the freeze**; they are not permission or a plan
to continue experiments. No failed experiment is promoted in this handoff.

The final Git tree contains the frozen implementation and required tooling.
A clean checkout is the intended submission. See [final QA](submission_qa.md) and
[Python/tool inventory](repository_inventory.md) for execution and cleanup scope.
Independent physical acceptance is not packaged.

Personal design notes and planning material are kept locally outside the public
tree. The documents above are the evaluator entry points; archived investigations
are supporting evidence rather than the primary reading path.

## Editable visuals

Mermaid source lives in the architecture (two diagrams), processing flow,
validation and fix-loop documents. Readable SVG exports accompany the final
report: [architecture](figures/architecture.svg),
[validation](figures/validation.svg) and [fix loop](figures/fix_loop.svg).
`scripts/render_assessment_report.py` regenerates those exports and the PDF;
their boxes describe implemented stages or the explicitly labelled evidence
process, not an autonomous repair service.
