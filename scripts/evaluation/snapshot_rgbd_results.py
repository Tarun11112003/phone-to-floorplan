"""Publish concise, source-linked results and inspectable figures from saved runs."""
import json
from pathlib import Path
from datetime import datetime, timezone
from xml.etree import ElementTree

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PolygonPatch

from floorplan.benchmark import evaluate_polygons

ROOT=Path(__file__).resolve().parents[2]


def read(path): return json.loads((ROOT/path).read_text(encoding='utf-8'))


def snapshot():
    public=read('demo/v2_public_verified/benchmark.json')
    rgb=read('demo/v2_rgb_verified/benchmark.json')
    truth=read('datasets/controlled_multimodal_v2/reference.json')
    controlled_plan=read('demo/v2_controlled_verified/plan.json')
    stitched_plan=read('demo/v2_stitched_verified/component_0/plan.json')
    controlled=evaluate_polygons(controlled_plan,truth)
    stitched=evaluate_polygons(stitched_plan,truth)
    tests=ElementTree.parse(ROOT/'demo/v2_tests.xml').getroot()
    suites=list(tests.iter('testsuite'))
    verification={key:sum(int(s.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
    artifact={'generated_utc':datetime.now(timezone.utc).isoformat(),'tests':verification,
              'public_cases':public['cases'],'rgb_cases':rgb['cases'],'controlled_sensor':controlled,'stitched_sensor':stitched,
              'evidence_categories':{'controlled':'synthetic exact simulated sensor poses','phone_reference':'provisional manually selected FARO wall regions; 1cm assumed uncertainty floor','rgb':'synthetic controlled capture with measured scale; same scene for photo/video'},
              'real_phone_cm_accuracy_validated':False,
              'source_runs':['demo/v2_public_verified','demo/v2_rgb_verified','demo/v2_controlled_verified','demo/v2_stitched_verified']}
    result=ROOT/'benchmarks/results/rgbd_component_results.json'; result.write_text(json.dumps(artifact,indent=2),encoding='utf-8')
    cases=public['cases']+rgb['cases']
    rows=[]
    for case in cases:
        m=case.get('metrics',{})
        if m.get('p95_dimension_error_m') is not None:
            measurement=f"{100*m['p95_dimension_error_m']:.2f} cm P95; nominal {'pass' if m['targets_met'] else 'fail'}"
        elif 'max_dimension_error_m' in m:
            measurement=f"{100*m['max_dimension_error_m']:.2f} cm max; dimensions only"
        elif 'missing_rooms' in m:
            measurement=f"{m['missing_rooms']} missing / {m['extra_rooms']} unmatched rooms; fails"
        else: measurement=case.get('reason') or 'Reference polygon annotation unavailable'
        rows.append(f"| {case['id']} | {case['status']} | {measurement} | {case['runtime_s']:.1f} |")
    content=['# V2 implementation results','',f"Recorded {artifact['generated_utc']}. CPU execution on the local Windows machine.",'',
        '**The complete three-tier cm-accuracy requirement is not achieved.** Depth-based multiroom geometry and verified capture stitching work on a controlled fixture. RGB completeness/topology remains unresolved.','',
        '| Case | Pipeline status | Measurement / limitation | Seconds |','|---|---|---|---|',*rows,'',
        f"Controlled two-room sensor fixture: P95 dimension error **{100*controlled['p95_dimension_error_m']:.3f} cm**, P95 corner error **{100*controlled['p95_corner_error_m']:.3f} cm**, correct two-room topology and full reference boundary coverage. These tiny errors reflect ideal synthetic data and exact simulated sensor poses; they do not measure phone accuracy.",'',
        f"Separate synthetic captures, with independently rotated/translated coordinate frames: verified visual overlap plus ICP recovers one connected component. P95 dimension error **{100*stitched['p95_dimension_error_m']:.3f} cm**; topology target passed. No manual doorway anchors were supplied to stitching.",'',
        f"Tests: **{verification['tests']} executed, {verification['failures']} failures, {verification['errors']} errors, {verification['skipped']} skipped**. See `demo/v2_tests.xml` for the actual test record.",'',
        '![Plans and measured errors](../../docs/figures/rgbd_component_results.png)','',
        '## How to interpret the evidence','',
        '- ICL development maximum side error improved from 5.07 cm to 0.89 cm. The unseen trajectory still fails geometry coverage. These trajectories share a synthetic room.',
        '- The phone development reference was prepared from an independent FARO scan using manually inspected wall regions and robust line fits. Its assumed 1 cm annotation uncertainty floor and lack of independent review make the nominal pass provisional. Only four correlated wall edges are evaluated.',
        '- Two other phone venues produce geometry but lack reviewed structural reference polygons. Their FARO data and inspection plots are downloaded; they are not counted as accuracy passes.',
        '- RGB photos and video registered all 97 controlled-fixture views. A weak initial scale control was correctly rejected; a revised control passed triangulation. The final photo cloud has no closed plan; the video proposal has incorrect topology and is not a success.',
        '- RGB times in the table measure the calibrated dense/layout stage using validated cached SfM. Initial photo SfM took about 317 seconds; include feature reconstruction time when budgeting a fresh demo. The cache is disclosed in each run ledger.',
        '- Additional public ICL photo/video stereo experiments also produced metric clouds but incomplete wall boundaries. Their independent scale-control preparation uses only two depth patches to simulate a measured distance; RGB inference receives no depth maps.',
        '- Partial plans preserve evidence and do not imply complete property coverage. There is no app, field certification, learned depth model, or GPU requirement.','',
        '## Reproduction and source evidence','',
        '- [Implementation and manifest guide](../../docs/engineering/history/rgbd_baseline.md)',
        '- [Machine-readable complete snapshot](../results/rgbd_component_results.json)',
        '- [Public-case suite](../examples/public_benchmark.json)',
        '- Local immutable runs: `demo/v2_public_verified`, `demo/v2_rgb_verified`, `demo/v2_controlled_verified`, `demo/v2_stitched_verified`.',
        '- Regenerate this page and plot with `python scripts/evaluation/snapshot_rgbd_results.py` after the named runs finish.','',
        '## Remaining priority','',
        'Improve RGB dense wall coverage and reject geometrically inconsistent reconstructions before proposing a room. Then annotate the held-out laser references, test real multiroom phone captures, add tracking recovery/free-space reasoning, and estimate measurement uncertainty. Keep the existing failures as regression cases.']
    (ROOT/'benchmarks/reports/rgbd_component_report.md').write_text('\n'.join(content)+'\n',encoding='utf-8')
    fig,axes=plt.subplots(2,2,figsize=(13,10),layout='constrained')
    def draw(ax,plan,title,reference=None,metrics=None):
        rotation=np.eye(2); translation=np.zeros(2)
        if metrics:
            rotation=np.asarray(metrics['alignment']['rotation']); translation=np.asarray(metrics['alignment']['translation_m'])
        for room in plan['rooms']:
            points=np.asarray(room['corners'])@rotation+translation
            ax.add_patch(PolygonPatch(points,closed=True,facecolor='#dcebf4',edgecolor='#234c67',lw=2))
            for a,b in zip(points,np.roll(points,-1,axis=0)):
                mid=(a+b)/2
                ax.text(*mid,f'{np.linalg.norm(a-b):.2f} m',ha='center',va='bottom',fontsize=8,bbox={'facecolor':'white','edgecolor':'none','alpha':.8})
        if reference:
            for room in reference['rooms']:
                ax.add_patch(PolygonPatch(room['corners'],closed=True,fill=False,edgecolor='#bf6332',linestyle='--',lw=1.5))
        ax.autoscale(); ax.margins(.15); ax.set_aspect('equal'); ax.set_title(title,loc='left',fontweight='bold'); ax.set_xlabel('metres'); ax.set_ylabel('metres')
        ax.spines[['top','right']].set_visible(False)
    draw(axes[0,0],controlled_plan,'Controlled sensor: L-shaped + rectangular room',truth,controlled)
    phone_plan=read('demo/v2_public_verified/arkit_development/plan.json')
    phone_reference=read('datasets/arkitscenes/references/416418/reference.json')
    phone_metrics=next(c['metrics'] for c in public['cases'] if c['id']=='arkit_development')
    draw(axes[0,1],phone_plan,'Phone LiDAR: dashed = provisional laser reference',phone_reference,phone_metrics)
    icl=next(c['metrics'] for c in public['cases'] if c['id']=='icl_development')
    values=[5.07107223,100*icl['max_dimension_error_m'],100*phone_metrics['p95_dimension_error_m']]
    axes[1,0].barh(['Old ICL max','New ICL max','Phone P95 (4 edges)'],values,color=['#aab4bd','#347a69','#347a69'])
    axes[1,0].axvline(3,color='#be683b',ls='--',label='3 cm target'); axes[1,0].set_xlabel('absolute dimension error (cm)')
    axes[1,0].set_title('Different evidence categories; not pooled',loc='left',fontweight='bold'); axes[1,0].legend()
    axes[1,1].axis('off')
    axes[1,1].text(0,1,'What the demo establishes',fontsize=15,fontweight='bold',va='top')
    axes[1,1].text(0,.86,'• CPU reconstruction and dimensioned exports\n• Concave rooms and verified RGB-D stitching\n• Independent evaluation with failure reporting\n\nWhat remains unresolved\n\n• RGB wall completeness and room topology\n• Held-out phone reference annotations\n• Real multiroom cm-accuracy validation\n\nSynthetic sensor poses are exact.\nPhone reference is provisional.\nNo general field-accuracy claim.',fontsize=12,va='top',linespacing=1.6)
    directory=ROOT/'docs/figures'; directory.mkdir(exist_ok=True)
    fig.savefig(directory/'rgbd_component_results.png',dpi=170); fig.savefig(directory/'rgbd_component_results.svg'); plt.close(fig)
    print(result)


if __name__=='__main__': snapshot()
