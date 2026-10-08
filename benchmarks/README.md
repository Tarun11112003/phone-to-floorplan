# Benchmark and evidence inventory

Start with [validation and decisions](../docs/validation.md) for the concise
before/after story and [benchmark report](report.md) for the scoped gate ledger.
The [Fix Loop](../docs/fix_loop.md) separates shipped changes from diagnostic work.

| Directory | Content |
|---|---|
| `results/` | Saved machine-readable supplied/public-data and experimental results |
| `manifests/` | Evidence pointers/hashes, reproduction configurations and QA receipts |
| `reports/` | Historical component benchmark reports, with their original scope |
| `templates/` | Capture manifest and unfilled independent ground-truth CSV templates |

`templates/ground_truth/` is not a completed physical survey. Saved sensor
comparisons and inferred-cell containment do not demonstrate centimetre accuracy.
Raw captures/native artifacts accompany the separate assessment handoff; large
data, model weights, caches and personal notes are excluded from the public tree.

Historical input/producer hashes and numeric evidence are retained. Relocated
tools have updated import/path references; exact historical producer bytes remain
available in Git history. [Reproduction](../docs/reproducibility.md) documents
asset requirements and the limits of native every-number regeneration.
