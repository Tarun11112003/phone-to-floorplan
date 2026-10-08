"""Inspect frozen reconstruction evidence; no survey inputs or accuracy claims."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from floorplan.layout import _line
from floorplan.provenance import sha256


def inspect(run, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output.mkdir(parents=True, exist_ok=False)
    artifact = run / 'artifacts'
    points = np.load(artifact / 'cloud.npz')['points']
    result = json.loads((artifact / 'rgbd_summary.json').read_text())
    trajectory = json.loads((artifact / 'trajectory.json').read_text())
    centers = np.asarray([p['camera_to_first'] for p in trajectory])[:, :3, 3]
    metadata = json.loads((artifact / 'layout_evidence.json').read_text())
    # Render in the frozen producer frame. Refitting the basis with current
    # code or assuming world gravity can misalign old wall segments and points.
    basis = np.asarray(metadata['basis_columns_in_input'], dtype=float)
    floor = metadata.get('wall_sampling_slab_bound_m', metadata.get('floor_level_m'))
    if floor is None:
        raise ValueError('The frozen layout has no wall-sampling slab datum')
    aligned, cameras = points @ basis, centers @ basis
    fig, ax = plt.subplots(figsize=(9, 9))
    wall = aligned[(aligned[:, 1] < floor - .25) & (aligned[:, 1] > floor - 3)]
    ax.scatter(wall[::3, 0], wall[::3, 2], c=floor-wall[::3, 1], s=.3, alpha=.25, cmap='viridis')
    for i, segment in enumerate(metadata['wall_segments']):
        ends = np.asarray(_line(segment).coords)
        ax.plot(ends[:, 0], ends[:, 1], linewidth=2)
        ax.text(*ends.mean(axis=0), str(i), fontsize=8)
    ax.plot(cameras[:, 0], cameras[:, 2], color='red', alpha=.6)
    ax.set_aspect('equal'); ax.set(xlabel='x (m)', ylabel='z (m)', title='Observed cloud and fitted segments; not surveyed truth')
    fig.savefig(output / 'wall_support.png', dpi=140); plt.close(fig)
    if metadata.get('boundary_network') is not None:
        fig,axes=plt.subplots(1,2,figsize=(15,7),sharex=True,sharey=True)
        for segment in metadata['boundary_network']:
            ends=np.asarray(_line(segment).coords)
            axes[0].plot(ends[:,0],ends[:,1],color='orange' if segment['source_kind']=='traversed_gap' else 'black',linewidth=1)
        diagnostics=metadata['polygonization_diagnostics']
        for name,color in [('dangles','red'),('cut_edges','orange')]:
            for line in diagnostics[name]:
                ends=np.asarray(line); axes[1].plot(ends[:,0],ends[:,1],color=color,linewidth=1)
        for polygon in diagnostics['rejected_polygons']:
            corners=np.asarray(polygon['corners'])
            axes[1].plot(corners[:,0],corners[:,1],color='gray',alpha=.4)
        for ax in axes:
            ax.plot(cameras[:,0],cameras[:,2],color='blue',alpha=.4)
            ax.set_aspect('equal'); ax.set(xlabel='x (m)',ylabel='z (m)')
        axes[0].set_title('Finite junction network; orange = traversed gaps')
        axes[1].set_title('Red = dangles; gray = rejected cells; not survey truth')
        fig.tight_layout(); fig.savefig(output/'boundary_network.png',dpi=140); plt.close(fig)
    summary = dict(run=str(run.resolve()), cloud_sha256=sha256(artifact/'cloud.npz'),
                   run_sha256=sha256(run/'run.json'), point_count=len(points),
                   layout_evidence_sha256=sha256(artifact/'layout_evidence.json'),
                   planes=len(result['planes']), segments=len(metadata['wall_segments']),
                   floor_observation=dict(observed=metadata.get('floor_observed'),
                       vertical_source=metadata.get('vertical_source')),
                   basis_source='frozen layout evidence', accuracy_validated=False,
                   boundary_trace_available='boundary_stages' in metadata,
                   boundary_stages=metadata.get('boundary_stages'),
                   rejected_polygon_reasons=[p['reasons'] for p in metadata.get('polygonization_diagnostics',{}).get('rejected_polygons',[])])
    (output/'diagnostic.json').write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path); parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.run, args.out), indent=2))
