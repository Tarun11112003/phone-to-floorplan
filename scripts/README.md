# Assessment tools

Run commands from the repository root after installing the project. The supported
capture entry point remains `python -m floorplan.cli run-capture`; these tools are
setup, reproduction and evaluation utilities, not alternative production paths.

| Location | Purpose |
|---|---|
| `bootstrap_windows.ps1` | Tested Windows/Python 3.12 CPU installation |
| `package_assessment.py` | Clean tracked-source/evidence packaging and integrity verification |
| `render_assessment_report.py` | Saved-evidence validation and five-page report rendering |
| `install_openmvs.py` | Optional pinned native dense-reconstruction dependency |
| `datasets/` | Acquisition/preparation of public references and controlled fixtures |
| `evaluation/` | Result comparison, benchmark scoring, artifact verification and reproduction |
| `diagnostics/` | Read-only geometry, timing, track and sensor-support audits |
| `experiments/` | Isolated alternatives/ablations; not production defaults |

For example, `python scripts/diagnostics/trace_observed_ceiling.py --help` shows
the retained audit interface. Every tool's own help lists required arguments;
the [reproduction guide](../docs/reproducibility.md) supplies concrete evidence
commands and prerequisites. Optional experiments require their pinned assets
and native environment. Closed investigations are retained for evidence, not as
instructions to resume development.
