"""Render the frozen five-page report and editable evidence diagrams.

Reads documentation and verifies saved evidence; never runs reconstruction.
Requires the evaluation extra (matplotlib). Outputs must be fresh.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import textwrap


def validate_evidence(root: Path) -> None:
    manifest = json.loads((root / 'docs/evidence/final_state.json').read_text(encoding='utf-8'))
    for record in manifest['evidence'].values():
        raw = (root / record['source']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record['sha256']:
            raise ValueError(f"Evidence hash mismatch: {record['source']}")
        obj = json.loads(raw)
        for pointer, expected in record['values'].items():
            value = obj
            for part in pointer.strip('/').split('/'):
                value = value[int(part)] if isinstance(value, list) else value[part]
            if value != expected:
                raise ValueError(f"Evidence field mismatch: {record['source']}{pointer}")


def render(root: Path, out: Path) -> dict:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import FancyBboxPatch
    from matplotlib.font_manager import FontProperties

    if out.exists() and any(out.iterdir()):
        raise FileExistsError('Report output must be fresh')
    validate_evidence(root)
    parts = re.split(r'<!-- PAGE \d+ -->', (root / 'docs/TECHNICAL_REPORT.md').read_text(encoding='utf-8'))[1:]
    if len(parts) != 5:
        raise ValueError('The canonical report must contain exactly five declared pages')
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.2, 'pdf.fonttype': 42, 'svg.fonttype': 'none'})
    ink, blue, muted = '#183545', '#246783', '#556873'

    def clean(s):
        s = re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', s)
        return s.replace('`', '').replace('**', '')

    def diagram(kind, ax):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        if kind == 'validation':
            boxes = [(.005,.52,.235,.42,'Tests / sensors / trials\nSeparate evidence types'),
                     (.005,.02,.235,.42,'Software claim ledger\nScoped passes / limits'),
                     (.39,.52,.235,.42,'Survey / repeats\nMISSING'),
                     (.73,.52,.265,.42,'Physical acceptance\nNOT DEMONSTRATED')]
            for x,y,w,h,label in boxes:
                ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.004',
                    facecolor='#eef4f7',edgecolor='#9badb6',linewidth=.8))
                ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=8,color=ink)
            ax.annotate('',xy=(.1225,.44),xytext=(.1225,.52),arrowprops={'arrowstyle':'->','color':blue})
            ax.annotate('',xy=(.73,.73),xytext=(.625,.73),arrowprops={'arrowstyle':'->','linestyle':'--','color':blue})
            ax.text(.62,.16,'Software consistency does not establish physical accuracy.',ha='center',fontsize=7.4,color=muted)
            return
        labels = {
            'architecture': ['Capture intake\nIdentity / timing', 'RGB SfM or\nmetric RGB-D', 'Supported walls\nExplicit stitching', 'Surfaces / damage\nContract checks', 'Review exports\nSeparate scoring'],
            'validation': ['Controlled tests\nSoftware invariants', 'Supplied sensors\nInternal consistency', 'Isolated alternatives\nGeometry audits', 'Survey / repeats\nMISSING', 'Physical acceptance\nNOT DEMONSTRATED'],
            'fix_loop': ['Failed gate\nObserved metric', 'Hypothesis\nDiagnostic evidence', 'Supported fix\nAdvance prediction', 'Matched before/after\nRegression checks', 'Measured status\nLimit / postmortem'],
        }[kind]
        for i, label in enumerate(labels):
            x = .005 + .2*i
            ax.add_patch(FancyBboxPatch((x, .18), .182, .64, boxstyle='round,pad=0.004',
                facecolor='#eef4f7' if i < 3 else '#f4f1eb' if kind == 'validation' else '#eef4f7',
                edgecolor='#9badb6', linewidth=.8))
            ax.text(x+.091, .50, label, ha='center', va='center', fontsize=8.0, color=ink)
            if i < 4:
                ax.annotate('', xy=(x+.200, .5), xytext=(x+.183, .5),
                    arrowprops={'arrowstyle':'->', 'color':blue, 'lw':1,
                    'linestyle':'--' if kind == 'validation' else '-'})
        if kind == 'validation':
            ax.text(.5, .01, 'Evidence types are separate; software passes cannot imply a physical pass.',
                    ha='center', fontsize=7.5, color=muted)
        elif kind == 'fix_loop':
            ax.text(.5, .01, 'Unsupported causality → diagnostic / inconclusive; retain production.',
                    ha='center', fontsize=7.5, color=muted)

    for kind in ('architecture', 'validation', 'fix_loop'):
        fig, ax = plt.subplots(figsize=(10, 1.7), layout='constrained')
        diagram(kind, ax)
        fig.savefig(out/f'{kind}.svg', metadata={'Date': None})
        svg = out/f'{kind}.svg'
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')
        plt.close(fig)

    def wrap(fig, text, size, fraction=.85, weight='normal'):
        renderer = fig.canvas.get_renderer()
        prop = FontProperties(family='DejaVu Sans', size=size, weight=weight)
        max_width = fig.bbox.width*fraction
        lines, current = [], ''
        for word in text.split():
            candidate = (current+' '+word).strip()
            if current and renderer.get_text_width_height_descent(candidate, prop, False)[0] > max_width:
                lines.append(current); current=word
            else:
                current=candidate
        if current: lines.append(current)
        return lines

    def table(fig, rows, y):
        widths = [.30, .42, .28]
        wrapped = []
        for row in rows:
            if len(row) != 3:
                raise ValueError('Report tables require three columns')
            wrapped.append(['\n'.join(wrap(fig, clean(cell), 8.2, fraction=.85*w*.90))
                            for cell, w in zip(row, widths)])
        heights = [.0125*max(c.count('\n')+1 for c in row)+.013 for row in wrapped]
        total = sum(heights)
        ax = fig.add_axes([.075, y-total, .85, total]); ax.axis('off')
        t = ax.table(cellText=wrapped[1:], colLabels=wrapped[0], cellLoc='left',
                     colWidths=widths, bbox=[0, 0, 1, 1])
        t.auto_set_font_size(False); t.set_fontsize(8.2)
        for (r, c), cell in t.get_celld().items():
            cell.set_height(heights[r]/total)
            cell.set_edgecolor('#d3dce1'); cell.set_linewidth(.45)
            cell.set_facecolor('#e8f0f5' if r == 0 else '#fafcfd' if r % 2 else 'white')
            cell.set_text_props(color=ink, weight='bold' if r == 0 else 'normal')
            cell.PAD = .045
        return y-total-.016

    min_y = []
    with PdfPages(out/'technical_report.pdf') as pdf:
        pdf.infodict().update(Title='Phone to Floorplan — final technical report',
            Subject='Frozen implementation, existing evidence and explicit assessment limitations',
            CreationDate=None, ModDate=None)
        for number, part in enumerate(parts, 1):
            fig = plt.figure(figsize=(8.27, 11.69), facecolor='white')
            fig.text(.075, .957, 'PHONE TO FLOORPLAN', fontsize=10, color=blue, weight='bold')
            fig.text(.075, .932, 'Final development state · Physical acceptance not demonstrated',
                     fontsize=8.3, color=muted)
            fig.text(.075, .035, 'Source fields and SHA-256: docs/evidence/final_state.json · Details: docs/INDEX.md',
                     fontsize=7.2, color=muted)
            fig.text(.925, .035, f'{number} / 5', fontsize=8.5, ha='right', color=muted)
            blocks = re.split(r'\n\s*\n', part.strip())
            y = .895
            for block in blocks:
                if block.startswith('## '):
                    lines = wrap(fig, clean(block[3:]), 16, weight='bold')
                    fig.text(.075, y, '\n'.join(lines), fontsize=16, weight='bold', va='top', color=ink)
                    y -= .030*len(lines)+.019
                elif block.startswith('|'):
                    rows = [[s.strip() for s in line.strip().strip('|').split('|')]
                            for line in block.splitlines() if not re.fullmatch(r'[|:\- ]+', line)]
                    y = table(fig, rows, y)
                elif '<!-- FIGURE ' in block:
                    kind = re.search(r'<!-- FIGURE (\w+) -->', block).group(1)
                    h = .094
                    ax = fig.add_axes([.075, y-h, .85, h]); diagram(kind, ax)
                    y -= h+.018
                else:
                    size = 9.5 if number == 5 else 10.2
                    lines = wrap(fig, clean(' '.join(block.splitlines())), size)
                    fig.text(.075, y, '\n'.join(lines), fontsize=size, va='top',
                             linespacing=1.30, color=ink)
                    y -= (size*1.3/841.68+.00035)*len(lines)+(.012 if number == 5 else .015)
            if y < .068:
                plt.close(fig)
                raise ValueError(f'Report page {number} overflows: bottom={y:.3f}')
            min_y.append(y)
            fig.savefig(out/f'page_{number}.png', dpi=135)
            pdf.savefig(fig); plt.close(fig)
        pages = pdf.get_pagecount()
    receipt = {'pages':pages, 'minimum_content_y':min_y, 'evidence_validated':True,
               'pdf_sha256':hashlib.sha256((out/'technical_report.pdf').read_bytes()).hexdigest(),
               'reconstruction_run':False}
    (out/'render.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(render(Path(__file__).resolve().parents[1], args.out.resolve()), indent=2))


if __name__ == '__main__':
    main()
