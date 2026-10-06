"""Render architecture and measured benchmark figures from saved artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
import numpy as np
from PIL import Image


def architecture(output: Path) -> None:
    fig, ax = plt.subplots(figsize=(16, 9), dpi=150)
    fig.patch.set_facecolor("#f5f7fa")
    ax.set(xlim=(0, 16), ylim=(0, 9))
    ax.axis("off")
    ink, blue, green, amber = "#18364c", "#e3edfa", "#e0f2e9", "#fff0d6"
    ax.text(0.35, 8.55, "Capture to floor plan", fontsize=25, weight="bold", color=ink)
    ax.text(0.35, 8.13, "IMPLEMENTED PATHS  |  constrained research demo, October 2026", fontsize=11, color="#52677c")
    def box(x, y, w, h, label, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.1", linewidth=1.2, edgecolor="#9bacbb", facecolor=color))
        ax.text(x + w / 2, y + h / 2, label, va="center", ha="center", fontsize=11.5, color=ink, linespacing=1.5)
    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=15, color="#5b7286", linewidth=1.6))
    for y, title in [(6.3, "PHOTOS"), (4.4, "VIDEO"), (2.5, "RGB-D / DEPTH")]:
        ax.text(0.35, y + 1.2, title, fontsize=11, weight="bold", color="#45627d")
    box(0.35, 6.3, 2.6, 0.95, "Overlapping photos\nknown camera intrinsics", blue)
    box(3.4, 6.3, 3.0, 0.95, "PyCOLMAP\nall-pairs matching", blue)
    box(6.85, 6.3, 3.4, 0.95, "Camera poses + sparse cloud\nregistration coverage", blue)
    box(10.7, 6.3, 4.8, 0.95, "Metric scale + structural extraction\nSTILL NEEDED", amber)
    box(0.35, 4.4, 2.6, 0.95, "RGB video\nFFmpeg keyframes", blue)
    box(3.4, 4.4, 3.0, 0.95, "PyCOLMAP\nsequential / all-pairs", blue)
    box(6.85, 4.4, 3.4, 0.95, "Camera poses + sparse cloud\npartial scenes reported", blue)
    box(10.7, 4.4, 4.8, 0.95, "Metric scale + structural extraction\nSTILL NEEDED", amber)
    box(0.35, 2.5, 2.6, 0.95, "Calibrated RGB + depth\nmetric depth units", green)
    box(3.4, 2.5, 3.0, 0.95, "SIFT / PnP\n3D pose refinement", green)
    box(6.85, 2.5, 3.4, 0.95, "Fuse points + fit planes\nobserve opposing walls", green)
    box(10.7, 2.5, 4.8, 0.95, "Rectangular room proposal\nSVG / DXF / JSON / CSV", green)
    for y in [6.775, 4.875, 2.975]:
        for x1, x2 in [(2.95, 3.4), (6.4, 6.85), (10.25, 10.7)]:
            arrow(x1 + .04, y, x2 - .04, y)
    box(0.35, 0.55, 7.2, 1.05, "Separate assisted baseline\nmarked floor corners + metric reference + doorway stitches", "#edf0f5")
    box(8.0, 0.55, 7.5, 1.05, "Held-out evaluation\nreference mesh is read after predictions are saved", "#efe8f6")
    ax.text(0.35, 0.12, "Open gaps: automatic multi-room stitching, non-rectangular rooms, phone LiDAR validation and field centimetre accuracy.", fontsize=10.8, color="#6b4b2f")
    fig.tight_layout(pad=0.5)
    fig.savefig(output / "architecture.png", facecolor=fig.get_facecolor())
    fig.savefig(output / "architecture.svg", facecolor=fig.get_facecolor())
    plt.close(fig)


def benchmark(run: Path, first_image: Path, output: Path) -> None:
    metrics = json.loads((run / "evaluation.json").read_text(encoding="utf-8"))
    plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
    cloud = np.load(run / "cloud.npz")
    points = cloud["points"][::10]
    axis_x = np.asarray(plan["provenance"]["axis_x_in_first_camera"])
    axis_z = np.asarray(plan["provenance"]["axis_z_in_first_camera"])
    projected = np.column_stack((points @ axis_x, points @ axis_z))
    corners = np.asarray(plan["rooms"][0]["corners"])
    predicted = np.asarray(metrics["predicted_dimensions_m"])
    truth = np.asarray(metrics["reference_dimensions_m"])
    errors = np.asarray(metrics["absolute_errors_m"]) * 100
    fig, axs = plt.subplots(2, 2, figsize=(13, 10), dpi=150)
    fig.suptitle("ICL-NUIM: automatic RGB-D room reconstruction", fontsize=19, weight="bold", x=.04, ha="left")
    fig.text(.04, .935, "177 tracked frames | single synthetic room | no ground-truth geometry supplied to reconstruction", fontsize=11, color="#52677c")
    with Image.open(first_image) as image:
        axs[0, 0].imshow(image)
    axs[0, 0].set_title("Input RGB frame (paired metric depth also used)", loc="left", fontsize=12)
    axs[0, 0].axis("off")
    axs[0, 1].scatter(projected[:, 0], projected[:, 1], s=.2, c="#8ea6b5", alpha=.4, rasterized=True)
    closed = np.vstack((corners, corners[0]))
    axs[0, 1].plot(closed[:, 0], closed[:, 1], color="#d76536", linewidth=2.2, label="room proposal")
    axs[0, 1].set(title="Fused observations and inferred walls", xlabel="Local room axis 1 (m)", ylabel="Local room axis 2 (m)", aspect="equal")
    axs[0, 1].legend(loc="upper right", fontsize=9)
    axs[1, 0].add_patch(Rectangle(-truth / 2, truth[0], truth[1], fill=False, edgecolor="#248465", linewidth=2.5, label="reference mesh"))
    axs[1, 0].add_patch(Rectangle(-predicted / 2, predicted[0], predicted[1], fill=False, edgecolor="#d76536", linestyle="--", linewidth=2, label="predicted"))
    axs[1, 0].set(xlim=(-3, 3), ylim=(-3, 3), aspect="equal", title="Dimension comparison (centred, no scale fitted)", xlabel="Short side axis (m)", ylabel="Long side axis (m)")
    axs[1, 0].legend(loc="lower right", fontsize=9)
    bars = axs[1, 1].bar(["Short side", "Long side"], errors, width=.5, color=["#d76536", "#248465"])
    axs[1, 1].axhline(3, color="#52677c", linestyle="--", label="proposed 3 cm target")
    axs[1, 1].set(ylabel="Absolute dimension error (cm)", title="Target missed on one of two dimensions", ylim=(0, max(6, errors.max() * 1.3)))
    for bar, error in zip(bars, errors):
        axs[1, 1].text(bar.get_x() + bar.get_width()/2, error + .15, f"{error:.2f} cm", ha="center", fontsize=12, weight="bold")
    axs[1, 1].legend(loc="upper right", fontsize=9)
    for ax in [axs[0, 1], axs[1, 0], axs[1, 1]]:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=.15)
    fig.text(.04, .02, "Reference: 4.937 × 4.980 m. This case tests an automated baseline; it does not validate real-phone or multi-room accuracy.", fontsize=10, color="#52677c")
    fig.tight_layout(rect=(0.02, .04, .99, .92), h_pad=2)
    fig.savefig(output / "icl_rgbd_benchmark.png")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=Path("demo/icl_rgbd_refined"))
    parser.add_argument("--frame", type=Path, default=Path("datasets/icl_nuim/trajectory2/rgb/0.png"))
    parser.add_argument("--output", type=Path, default=Path("docs/figures"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    architecture(args.output)
    benchmark(args.run, args.frame, args.output)
    print(args.output)
