# Assessment review walkthrough

This demo presents the frozen implementation and existing evidence; it does
not promise full assessment acceptance or run another research experiment.

1. Open [README](../README.md), then the [five-page report](TECHNICAL_REPORT.pdf).
2. Show the [architecture](ARCHITECTURE.md) and explain the three branches,
   unresolved RGB scale, supplied sensor calibration and conservative output guards.
3. Review [validation](BENCHMARK_RESULTS.md) and the evidence manifest. Explain
   why390 tests and295/300 camera containment do not prove physical accuracy.
4. Show the retained ceiling result's `report.html`, `assessment.json`,
   `contract_coverage.json` and `layout_diagnostic.svg` from the evidence bundle.
   room_2 floor/ceiling remains unavailable; the0.703m notch remains unvalidated.
5. Explain [shipped fixes](FIX_LOOP.md) and rejected alternatives. The measured
   worst-gate assessment Fix Loop remains unproven; no missing prediction is fabricated.
6. Open [compliance](ASSIGNMENT_COMPLIANCE.md) and [limitations](LIMITATIONS.md).
   State exactly which physical data, app export, schema and cold-run evidence is absent.

For live software inspection, use `python -m floorplan.cli --help` and the
existing regression suite in the source snapshot. Fresh raw-capture commands
are in [operations](PHASE3_OPERATIONS.md), with explicit partial/failure expectations.
Do not present a cached artifact as a live reconstruction or silently hide a
nonzero exit status. Raw data and original evidence remain separately retained.
