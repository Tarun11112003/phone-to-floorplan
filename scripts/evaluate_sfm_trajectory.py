"""Evaluation-only camera trajectory audit. Never imported by reconstruction."""
import argparse
import json
from pathlib import Path

import numpy as np
import pycolmap
from floorplan.dense import measured_scale


def evaluate(model_path, sequence_path, capture_path, output):
    model = pycolmap.Reconstruction(str(model_path))
    sequence = json.loads(sequence_path.read_text(encoding='utf-8'))
    controls = json.loads(capture_path.read_text(encoding='utf-8'))['scale_references']
    truth = {Path(frame['rgb']).name: np.array(frame['camera_to_world'])[:3, 3] for frame in sequence['frames']}
    images = sorted((i for i in model.images.values() if i.name in truth), key=lambda i: i.name)
    if len(images) < 3:
        raise ValueError('At least three matching camera poses required')
    scale, evidence = measured_scale(model, controls)
    actual = np.array([i.projection_center()*scale for i in images])
    expected = np.array([truth[i.name] for i in images])
    x, y = actual-actual.mean(0), expected-expected.mean(0)
    u, singular, vt = np.linalg.svd(x.T@y)
    correction = np.eye(3)
    correction[-1, -1] = np.linalg.det(u@vt)
    rotation = u@correction@vt
    aligned = x@rotation+expected.mean(0)
    errors = np.linalg.norm(aligned-expected, axis=1)
    # Similarity is diagnostic only: it must not replace metric evaluation.
    fitted_scale = float((singular*np.diag(correction)).sum()/np.sum(x*x))
    similarity_error = np.linalg.norm(x@rotation*fitted_scale-y, axis=1)
    result = dict(registered_images=len(images), metric_scale=scale, scale_evidence=evidence,
                  rigid_ate_rmse_m=float(np.sqrt(np.mean(errors**2))),
                  rigid_ate_p95_m=float(np.percentile(errors, 95)),
                  diagnostic_similarity_scale=fitted_scale,
                  diagnostic_similarity_ate_rmse_m=float(np.sqrt(np.mean(similarity_error**2))),
                  alignment='one global proper rigid transform; measured scale unchanged',
                  per_image=[dict(image=i.name, error_m=float(e)) for i, e in zip(images, errors)])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(expected[:, 0], expected[:, 2], label='Reference')
    axes[0].plot(aligned[:, 0], aligned[:, 2], label='RGB estimate')
    axes[0].axis('equal'); axes[0].legend(); axes[0].set(xlabel='x (m)', ylabel='z (m)', title='Global rigid alignment, no rescaling')
    axes[1].plot(errors*100); axes[1].set(xlabel='Frame index', ylabel='Position error (cm)', title=f'ATE RMSE {result["rigid_ate_rmse_m"]*100:.2f} cm')
    fig.tight_layout(); fig.savefig(output.with_suffix('.png'), dpi=160); plt.close(fig)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('model', 'sequence', 'capture', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.model, args.sequence, args.capture, args.output), indent=2))
