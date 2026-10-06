"""Build the compact V3 results record and chart from completed run ledgers."""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def main():
    controlled = json.loads((ROOT/'demo/v3_verified/benchmark.json').read_text(encoding='utf-8'))
    public = json.loads((ROOT/'demo/v3_public_final/benchmark.json').read_text(encoding='utf-8'))
    trajectory = json.loads((ROOT/'docs/results/v3_unique_texture_trajectory.json').read_text(encoding='utf-8'))
    rows = []
    for case in controlled['cases']:
        metrics = case['metrics']
        rows.append(dict(case=case['id'], status=case['status'], full_targets=case['targets_met'],
                         dimension_p95_cm=100*metrics['p95_dimension_error_m'],
                         corner_p95_cm=100*metrics['p95_corner_error_m'],
                         opening_p95_cm=100*metrics['p95_opening_width_error_m'], runtime_s=case['runtime_s']))
    public_rows=[]
    for case in public['cases']:
        metrics=case.get('metrics',{})
        public_rows.append(dict(case=case['id'],status=case['status'],runtime_s=case['runtime_s'],
                                dimension_error_m=metrics.get('p95_dimension_error_m',metrics.get('max_dimension_error_m')),
                                limitation=case.get('evaluation_limitation'),reason=case.get('reason')))
    result=dict(controlled=rows, public=public_rows,
                rgb_camera_trajectory=dict(rigid_ate_rmse_cm=100*trajectory['rigid_ate_rmse_m'],
                                           rigid_ate_p95_cm=100*trajectory['rigid_ate_p95_m']),
                interpretation='Controlled synthetic passes are demo evidence, not real-phone field certification.')
    target=ROOT/'docs/results/v3_results.json'; target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    labels=[r['case'] for r in rows]; x=range(len(rows))
    fig,ax=plt.subplots(figsize=(9,4.8)); width=.24
    ax.bar([i-width for i in x],[r['dimension_p95_cm'] for r in rows],width,label='Wall dimensions')
    ax.bar(x,[r['corner_p95_cm'] for r in rows],width,label='Corners')
    ax.bar([i+width for i in x],[r['opening_p95_cm'] for r in rows],width,label='Door width')
    ax.axhline(3,color='#b33',linestyle='--',label='3 cm dimension/opening target')
    ax.set_xticks(list(x),labels); ax.set_ylabel('P95 absolute error (cm)'); ax.set_title('Controlled two-room end-to-end benchmark')
    ax.legend(ncol=2); ax.grid(axis='y',alpha=.25); fig.tight_layout()
    fig.savefig(ROOT/'docs/figures/v3_results.png',dpi=180); plt.close(fig)
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
