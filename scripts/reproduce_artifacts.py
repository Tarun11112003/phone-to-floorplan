"""Regenerate explicitly inventoried artifacts into a fresh directory.

Historical/skipped entries are never reported as regenerated. Commands are argv
lists, not shell strings. JSON claims can select stable fields; UUID/time fields
should not be published as deterministic measurement claims.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import re

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from floorplan.provenance import sha256


def reproduce(manifest,output):
    output=Path(output).resolve()
    if output.exists() and any(output.iterdir()): raise FileExistsError('Reproduction output must be fresh')
    output.mkdir(parents=True,exist_ok=True)
    rows=[]; ids=set()
    for item in manifest['artifacts']:
        identity=item['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+',identity) or identity in ids: raise ValueError('Unique simple artifact IDs required')
        ids.add(identity)
        mode=item.get('mode','regenerate')
        if mode in {'historical','skip'}:
            if not item.get('reason'): raise ValueError('Historical/skipped artifacts require a reason')
            rows.append(dict(id=identity,status=mode,reason=item['reason']))
            continue
        if mode!='regenerate': raise ValueError('Unknown reproduction mode')
        directory=output/identity; directory.mkdir()
        command=item['command']
        if not isinstance(command,list) or not command or not all(isinstance(p,str) for p in command):
            raise ValueError('Reproduction commands must be argument lists')
        command=[p.replace('{output}',str(directory)) for p in command]
        if command[0]=='python': command[0]=sys.executable
        try:
            # Keep the command log outside its output. Reconstruction deliberately
            # rejects a nonempty output directory before it reads any inputs.
            with (output/f'{identity}.command.log').open('w',encoding='utf-8') as log:
                execution=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=item.get('timeout_s',600))
        except (OSError,subprocess.TimeoutExpired) as exc:
            rows.append(dict(id=identity,status='failed',reason=str(exc),checks=[]))
            continue
        row=dict(id=identity,status='regenerated',exit_code=execution.returncode,checks=[])
        if execution.returncode!=item.get('expected_exit_code',0): row['status']='failed'
        for expected in item.get('claims',[]):
            path=(directory/expected['path']).resolve()
            if not path.is_relative_to(directory): raise ValueError('Artifact claim path escapes its output')
            if not path.is_file(): row['checks'].append(dict(path=expected['path'],passed=False,reason='missing')); row['status']='failed'; continue
            try:
                if 'sha256' in expected:
                    passed=sha256(path)==expected['sha256']
                else:
                    value=json.loads(path.read_text(encoding='utf-8'))
                    for key in expected.get('field',[]): value=value[key]
                    passed=value==expected['value']
                check=dict(path=expected['path'],passed=passed)
            except (KeyError,IndexError,TypeError,ValueError) as exc:
                passed=False; check=dict(path=expected['path'],passed=False,reason=str(exc))
            row['checks'].append(check)
            if not passed: row['status']='failed'
        if not row['checks'] and row['status']!='failed':
            row.update(status='executed_unverified',reason='No regenerated numeric claim or hash was checked')
        rows.append(row)
    result=dict(version='artifact-reproduction-v1',artifacts=rows,
                regenerated_verified=sum(r['status']=='regenerated' for r in rows),
                skipped_or_historical=sum(r['status'] in {'skip','historical'} for r in rows),
                all_claims_regenerated=bool(rows) and all(r['status']=='regenerated' for r in rows))
    (output/'reproduction.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path); parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    result=reproduce(json.loads(args.manifest.read_text(encoding='utf-8')),args.out)
    print(json.dumps(result,indent=2))
    if not result['all_claims_regenerated']: raise SystemExit(1)
