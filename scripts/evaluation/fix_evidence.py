"""Freeze a prospective fix declaration; verify later replay without inventing history.

This tool does not run a fix or select its cause. Supply an independently scored
development failure and a numeric prediction before editing the chosen producer.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import difflib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from floorplan.provenance import sha256


def _read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def _number(document,field):
    value=document
    for key in field: value=value[int(key)] if isinstance(value,list) else value[key]
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Fix metric must be an observed finite number')
    return value


def _fresh(path):
    path=Path(path).resolve()
    if path.exists() and any(path.iterdir()): raise FileExistsError('Fix evidence output must be fresh')
    path.mkdir(parents=True,exist_ok=True)
    return path


def declare(baseline,metrics,reference,source,output,*,gate,field,prediction,root_cause,intended_change,evidence):
    baseline=Path(baseline).resolve(); metrics=Path(metrics).resolve(); source=Path(source).resolve()
    ledger=_read(baseline/'run.json'); scoring=_read(metrics)
    if ledger.get('code_changed_during_run') is not False or not ledger.get('inputs'):
        raise ValueError('Baseline needs frozen producer and input hashes')
    if scoring.get(gate,{}).get('gate')!='fail': raise ValueError('Declare a measured failing gate')
    observed=_number(scoring,field)
    if not math.isfinite(prediction) or not root_cause.strip() or not intended_change.strip() or not evidence:
        raise ValueError('Finite prediction, evidenced cause and intended change are required')
    code=ledger.get('code_sha256',{})
    if not code: raise ValueError('Baseline source snapshot is missing')
    for name,digest in code.items():
        path=(source/name).resolve()
        if not path.is_relative_to(source) or not path.is_file() or sha256(path)!=digest:
            raise ValueError('Current source differs from baseline; a declaration cannot be retrospective')
    evidence_hashes={str(Path(path).resolve()):sha256(path) for path in evidence}
    output=_fresh(output)
    (output/'source_before').mkdir()
    for name in code:
        target=output/'source_before'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((source/name).read_bytes())
    for name,path in [('baseline_run.json',baseline/'run.json'),('baseline_metrics.json',metrics),('reference.json',Path(reference))]:
        (output/name).write_bytes(path.read_bytes())
    declaration=dict(version='prospective-fix-evidence-v1',declared_utc=datetime.now(timezone.utc).isoformat(),
        gate=gate,metric_field=field,baseline_value=observed,predicted_after_value=prediction,
        root_cause=root_cause,intended_change=intended_change,evidence_sha256=evidence_hashes,
        evaluator_version=scoring.get('evaluator_version'),reference_sha256=sha256(reference),
        baseline_run_sha256=sha256(output/'baseline_run.json'),baseline_metrics_sha256=sha256(output/'baseline_metrics.json'),
        source_sha256=code,baseline_producer=ledger.get('measurement_producer_fingerprint'),
        caveat='Operator must select the worst measured required development gate and retain raw replay assets. This declaration alone is not a shipped fix.')
    (output/'declaration.json').write_text(json.dumps(declaration,indent=2),encoding='utf-8')
    return declaration


def verify(declaration_dir,after,metrics,reference,source,output):
    directory=Path(declaration_dir).resolve(); after=Path(after).resolve(); source=Path(source).resolve()
    declaration=_read(directory/'declaration.json')
    before=_read(directory/'baseline_run.json'); later=_read(after/'run.json'); scoring=_read(metrics)
    if sha256(directory/'baseline_run.json')!=declaration['baseline_run_sha256'] or sha256(directory/'baseline_metrics.json')!=declaration['baseline_metrics_sha256']:
        raise ValueError('Frozen baseline evidence changed')
    if sha256(reference)!=declaration['reference_sha256'] or sha256(directory/'reference.json')!=declaration['reference_sha256']:
        raise ValueError('Reference changed between before and after')
    if later.get('code_changed_during_run') is not False:
        raise ValueError('After run producer changed during execution')
    if datetime.fromisoformat(later['started_utc'])<=datetime.fromisoformat(declaration['declared_utc']):
        raise ValueError('After run must start after the prospective declaration')
    if not later.get('inputs') or Counter(later['inputs'].values())!=Counter(before['inputs'].values()):
        raise ValueError('Before/after inference inputs differ')
    if scoring.get('evaluator_version')!=declaration['evaluator_version']:
        raise ValueError('Evaluator changed; regenerate both sides with identical rules')
    for name in ('acceptance.py','assignment_gates.py','benchmark.py','assessment_io.py','repeatability.py'):
        if before.get('code_sha256',{}).get(name)!=later.get('code_sha256',{}).get(name):
            raise ValueError('Evaluator source changed even if its version label did not; rescore both sides with identical rules')
    differences=[]
    for name in sorted(set(declaration['source_sha256'])|set(later.get('code_sha256',{}))):
        before_path=directory/'source_before'/name; after_path=(source/name).resolve()
        if not after_path.is_relative_to(source): raise ValueError('Source path escapes root')
        if before_path.is_file() and sha256(before_path)!=declaration['source_sha256'].get(name):
            raise ValueError('Frozen source snapshot changed')
        if name in later.get('code_sha256',{}) and (not after_path.is_file() or sha256(after_path)!=later['code_sha256'][name]):
            raise ValueError('Current source differs from after producer')
        a=before_path.read_text(encoding='utf-8').splitlines(keepends=True) if before_path.is_file() else []
        b=after_path.read_text(encoding='utf-8').splitlines(keepends=True) if after_path.is_file() else []
        differences.extend(difflib.unified_diff(a,b,fromfile=f'before/{name}',tofile=f'after/{name}'))
    a=json.dumps(before['configuration'],sort_keys=True,indent=2).splitlines(keepends=True)
    b=json.dumps(later['configuration'],sort_keys=True,indent=2).splitlines(keepends=True)
    differences.extend(difflib.unified_diff(a,b,fromfile='before/configuration.json',tofile='after/configuration.json'))
    observed=_number(scoring,declaration['metric_field'])
    result=dict(version='fix-replay-review-v1',gate=declaration['gate'],baseline_value=declaration['baseline_value'],
        predicted_after_value=declaration['predicted_after_value'],observed_after_value=observed,
        prediction_error=observed-declaration['predicted_after_value'],after_gate=scoring[declaration['gate']]['gate'],
        identical_input_hash_multisets=True,source_or_configuration_changed=bool(differences),
        declared_before_after_execution=True,after_run_sha256=sha256(after/'run.json'),after_metrics_sha256=sha256(metrics),
        caveat='Review causality, capture completeness, worst-gate selection and actual raw baseline regeneration separately.')
    output=_fresh(output)
    (output/'source_config.diff').write_text(''.join(differences),encoding='utf-8')
    (output/'fix_review.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); commands=parser.add_subparsers(dest='command',required=True)
    first=commands.add_parser('declare'); first.add_argument('--baseline',required=True,type=Path)
    first.add_argument('--gate',required=True); first.add_argument('--field',required=True,nargs='+')
    first.add_argument('--prediction',required=True,type=float); first.add_argument('--root-cause',required=True)
    first.add_argument('--intended-change',required=True); first.add_argument('--evidence',required=True,nargs='+',type=Path)
    second=commands.add_parser('verify'); second.add_argument('--declaration',required=True,type=Path)
    second.add_argument('--after',required=True,type=Path)
    for command in (first,second):
        command.add_argument('--metrics',required=True,type=Path); command.add_argument('--reference',required=True,type=Path)
        command.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[2]/'floorplan')
        command.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    if args.command=='declare':
        result=declare(args.baseline,args.metrics,args.reference,args.source,args.out,gate=args.gate,field=args.field,
            prediction=args.prediction,root_cause=args.root_cause,intended_change=args.intended_change,evidence=args.evidence)
    else: result=verify(args.declaration,args.after,args.metrics,args.reference,args.source,args.out)
    print(json.dumps(result,indent=2))
