"""Render a three-page development checkpoint from actual run artifacts.

This is deliberately labelled a checkpoint, not the final surveyed submission.
Re-run it with later accepted artifacts; never substitute render presence for
the required field benchmark or confidence calibration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import textwrap

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from floorplan.provenance import sha256


def snapshot(label,directory):
    directory=Path(directory).resolve()
    ledger=json.loads((directory/'run.json').read_text(encoding='utf-8'))
    assessment=json.loads((directory/'assessment.json').read_text(encoding='utf-8'))
    result=ledger['result']
    sparse=result.get('sparse_reconstruction',{})
    metadata=result.get('plan_metadata',{})
    reason=result.get('reason') or result.get('geometry_failure')
    if not reason and metadata.get('unclosed_geometry'):
        coverage=metadata.get('camera_center_coverage_fraction')
        reason=('Incomplete property coverage'+(f' ({coverage:.1%})' if coverage is not None else '')+
                '; room boundaries and identities need review')
    record=dict(label=label,tier=ledger['tier'],status=result['status'],rooms=len(assessment['rooms']),
        input_frames=result.get('input_frames'),tracked_frames=result.get('tracked_frames'),
        source_input_images=sparse.get('input_images'),source_registered_images=sparse.get('registered_images'),
        runtime_s=ledger['runtime_s'],capture_runtime_s=ledger.get('capture_runtime_s'),
        geometry_ready=result.get('floor_plan_ready',False),
        contract_complete=assessment.get('contract_complete',False),
        producer_frozen=ledger.get('code_changed_during_run') is False,
        calibrated=assessment.get('calibration_status',{}).get('status')=='applied',
        blockers=assessment.get('contract_blockers',[]),
        reason=reason or '',
        producer=ledger.get('measurement_producer_fingerprint'),
        paths={name:str(directory/name) for name in ('run.json','assessment.json')},
        hashes={name:sha256(directory/name) for name in ('run.json','assessment.json')})
    scoring=directory/'assignment_metrics.json'
    if scoring.is_file():
        gates=json.loads(scoring.read_text(encoding='utf-8'))
        record['known_gate_status']={key:gates[key]['gate'] for key in ('walls','openings','ceiling','intervals','property','topology')}
        record['hashes'][scoring.name]=sha256(scoring)
    return record


def render(records,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import FancyBboxPatch

    output=Path(output).resolve()
    if output.exists() and any(output.iterdir()): raise FileExistsError('Report output must be fresh')
    if not 1<=len(records)<=6: raise ValueError('Checkpoint supports one to six explicitly selected runs')
    output.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'pdf.fonttype':42})

    def page(title,number):
        fig=plt.figure(figsize=(8.27,11.69),facecolor='white')
        fig.text(.08,.952,'PHONE TO FLOORPLAN',fontsize=10,color='#25647f',weight='bold')
        fig.text(.08,.912,title,fontsize=22,weight='bold',color='#173445')
        fig.text(.08,.875,'Development checkpoint · Not field acceptance',fontsize=11,color='#a34b2b')
        fig.text(.08,.035,'Evidence from selected local run artifacts; independent survey remains outstanding.',fontsize=8,color='#576b75')
        fig.text(.92,.035,str(number),fontsize=9,ha='right',color='#576b75')
        return fig

    def prose(fig,y,text,size=10,width=88):
        lines='\n'.join(textwrap.wrap(text,width))
        fig.text(.08,y,lines,fontsize=size,va='top',linespacing=1.5,color='#263e4b')
        return y-.022*(lines.count('\n')+1)-.025

    pdf_path=output/'technical_checkpoint.pdf'
    with PdfPages(pdf_path) as pdf:
        fig=page('Architecture and measurement decisions',1)
        y=prose(fig,.82,'The code-only Windows CPU pipeline accepts room photo folders, native video or raw Stray LiDAR. Inputs are hashed before reconstruction; independent survey files are evaluated separately and never supply strict-photo inference scale.')
        y=prose(fig,y,'RGB uses seeded COLMAP plus an opt-in pinned learned metric-depth experiment. Learned scale is labelled model_scaled and is not accepted merely because geometry exists. LiDAR retains sensor scale and verified pose constraints. Missing observations remain unavailable.')
        ax=fig.add_axes([.08,.35,.84,.26]); ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis('off')
        labels=[('Capture','RGB / video / LiDAR'),('Geometry','Verified support / poses'),('Assessment','Surfaces / openings / scope'),('Evidence','Calibration / independent gates')]
        for index,(heading,body) in enumerate(labels):
            x=index*.25
            ax.add_patch(FancyBboxPatch((x+.01,.28),.22,.48,boxstyle='round,pad=0.008',facecolor='#eaf2f6',edgecolor='#6993a8'))
            ax.text(x+.12,.60,heading,ha='center',weight='bold',fontsize=10,color='#173445')
            ax.text(x+.12,.43,'\n'.join(textwrap.wrap(body,17)),ha='center',va='center',fontsize=8,color='#263e4b')
            if index<3: ax.annotate('',xy=(x+.26,.52),xytext=(x+.235,.52),arrowprops={'arrowstyle':'->','color':'#25647f'})
        y=prose(fig,.32,'Supported finite wall lines, occupied ceiling support, physical opening identities and a coherent room graph produce one canonical internal assessment. SVG, DXF, CSV and an offline HTML review accompany supported geometry. Completeness is checked separately from accuracy.')
        prose(fig,y,'Final deployment, damage validation, calibrated uncertainty, a surveyed all-tier property and unseen-phone rehearsal remain required. Reviewed alternatives and executed experiments are distinguished in the documentation; external models have pinned revisions and explicit provenance.')
        fig.savefig(output/'page_1.png',dpi=120); pdf.savefig(fig); plt.close(fig)

        fig=page('Observed end-to-end outcomes',2)
        prose(fig,.82,'These selected development runs may include failures or generated regression controls. None is a surveyed physical acceptance benchmark. Runtime excludes initial model/data installation; a ready research plan does not establish a complete assignment contract.')
        ax=fig.add_axes([.08,.41,.84,.30]); ax.axis('off')
        rows=[]
        for r in records:
            # Derived depth views omit unregistered RGB. Show original SfM
            # registration when available, preserving derived counts in metadata.
            tracked=(f"{r['source_registered_images']}/{r['source_input_images']}"
                     if r['source_input_images'] is not None else
                     f"{r['tracked_frames']}/{r['input_frames']}" if r['input_frames'] is not None else 'n/a')
            total=f"{r['capture_runtime_s']:.2f}" if r['capture_runtime_s'] is not None else 'n/a'
            rows.append([r['label'],r['tier'],r['status'].replace('_','\n'),str(r['rooms']),tracked,f"{r['runtime_s']:.2f}",total])
        table=ax.table(cellText=rows,colLabels=['Case','Tier','Status','Rooms','Views','Recon s','Total s'],cellLoc='left',loc='upper center',colWidths=[.18,.08,.24,.08,.14,.14,.14])
        table.auto_set_font_size(False); table.set_fontsize(8)
        for (row,col),cell in table.get_celld().items():
            cell.set_height(.13 if row==0 else .19)
            cell.set_edgecolor('#d4e0e7')
            cell.set_facecolor('#eaf2f6' if row==0 else '#ffffff' if row%2 else '#f5f8fa')
            if row==0: cell.set_text_props(weight='bold',color='#173445')
        prose(fig,.415,'Views: original SfM registered/selected RGB when available; otherwise tracked/input sensor frames. Derived RGB-D counts remain in report_metadata.json.',size=8,width=104)
        y=.35
        for r in records:
            note=r['reason'] or ('Supported geometry; required heights/calibration remain unavailable' if r['geometry_ready'] else 'Inspect the source ledger for failure details')
            y=prose(fig,y,f"{r['label']}: {note}",size=9,width=94)
        fig.savefig(output/'page_2.png',dpi=120); pdf.savefig(fig); plt.close(fig)

        fig=page('Acceptance holds and reproducibility',3)
        y=.82
        for number,text in enumerate([
            'Strict Native Camera photos and base-phone video must produce automatic whole-property geometry and meet surveyed wall, opening, ceiling, footprint and adjacency gates.',
            'Collect three non-connector rooms plus a separate connector in all tiers, furnished staged damage, independent repeats, survey/raw logs and original two-room consumer exports.',
            'Freeze the producer before property-grouped calibration. Nine independent properties per tier/kind/unit are needed for finite 90% groups; audit is separate and small samples carry uncertainty.',
            'Obtain the missing published schema and earlier Round 1 rules. Internal validation and provisional known gates cannot certify official compliance.',
            'Declare an evidenced numerical prediction before a future worst-gate fix; preserve identical raw before/after replay and a readable diff. Finish clean-machine timing and unseen-phone rehearsal.'
        ],1): y=prose(fig,y,f'{number}. {text}',size=10,width=87)
        y=prose(fig,y,'Reproduction uses the explicit checkpoint manifest, fresh output directories, expected exit codes and stable artifact claims. Regenerated failures are evidence of pipeline behavior, not successful assessment outputs. Historical copies and skipped assets are counted separately.',size=9,width=95)
        fig.text(.08,y,'Source ledger SHA-256 prefixes (full hashes in report_metadata.json)',fontsize=9,weight='bold',color='#173445'); y-=.025
        for r in records:
            fig.text(.08,y,f"{r['label']}: {r['hashes']['run.json'][:20]}  · frozen={r['producer_frozen']} · contract={r['contract_complete']}",fontsize=8,color='#263e4b'); y-=.025
        fig.savefig(output/'page_3.png',dpi=120); pdf.savefig(fig); plt.close(fig)
    result=dict(version='phase3-checkpoint-report-v1',page_count=3,final_submission=False,runs=records,pdf_sha256=sha256(pdf_path))
    (output/'report_metadata.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,action='append',help='LABEL=directory containing run.json and assessment.json')
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    records=[snapshot(*value.split('=',1)) for value in args.run]
    result=render(records,args.out)
    print(json.dumps({'pdf':str(args.out/'technical_checkpoint.pdf'),'page_count':result['page_count'],'final_submission':False},indent=2))
