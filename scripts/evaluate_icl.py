"""Evaluate a saved RGB-D plan against the separate ICL-NUIM mesh reference."""
import argparse
import json
from pathlib import Path

from floorplan.evaluation import evaluate_icl


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("mesh_archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--trajectory", type=Path)
    parser.add_argument("--trajectory-truth", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate_icl(args.plan, args.mesh_archive, args.output, args.trajectory, args.trajectory_truth), indent=2))
