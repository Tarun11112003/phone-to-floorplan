"""Package the current source and saved evidence without executing inference.

The source archive includes uncommitted work; it is not a Git checkout.
Raw assessment data is separate and must not be publicly redistributed by this tool.
Outputs must be fresh. Verification checks every file and archive SHA-256/CRC.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import time
import zipfile


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=root).decode('utf-8')


def source_files(root: Path) -> list[Path]:
    names = git(root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').split('\0')
    directories = {'floorplan', 'scripts', 'tests', 'docs', 'examples', 'requirements'}
    root_names = {'README.md', 'pyproject.toml', 'requirements.txt', '.gitignore', 'LICENSE', 'LICENSE.md', 'LICENSE.txt'}
    files = []
    for name in set(names):
        p = root/name
        parts = PurePosixPath(name.replace('\\', '/')).parts
        if p.is_file() and (parts[0] in directories or name in root_names):
            if not {'__pycache__', '.pytest_cache', '.venv', '.git', '.tools'}.intersection(parts):
                files.append(p)
    if not (root/'floorplan/cli.py') in files:
        raise ValueError('Current source inventory lacks the CLI')
    return sorted(files)


def evidence_files(root: Path) -> tuple[list[Path], list[dict]]:
    files = set()
    unavailable = []
    allowed = {'.json', '.log', '.txt', '.md', '.png', '.jpg', '.jpeg', '.svg', '.csv', '.bin', '.npz', '.db', '.pdf'}
    for directory in ('docs/results', 'docs/fixes', 'docs/evidence', 'demo/assessment_handoff/prior_documents',
                      'demo/assessment_handoff/report_delivery'):
        base = root/directory
        if base.exists():
            files.update(p for p in base.rglob('*') if p.is_file() and p.suffix.lower() in allowed)
    # Preserve authoritative floor-support logs/analysis; no rerun or historical mutation.
    for directory in ('demo/phase3_floor_support',):
        base = root/directory
        if base.exists():
            files.update(p for p in base.rglob('*') if p.is_file() and p.suffix.lower() in allowed)
    for directory in ('demo/phase3_strip_trace/current_exterior/ceiling',
                      'demo/phase3_strip_trace/current_exterior/floor',
                      'demo/phase3_strip_trace/current_exterior/single'):
        base = root/directory
        if base.exists():
            # Retain native output/cloud/planes; normalized inputs come from raw archive.
            files.update(p for p in base.rglob('*') if p.is_file() and p.suffix.lower() in allowed
                         and 'intake' not in p.relative_to(base).parts and 'frames' not in p.relative_to(base).parts)

    def visit(obj):
        if isinstance(obj, dict):
            for name, value in obj.items():
                if isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value):
                    path = Path(name.replace('\\', '/'))
                    path = path if path.is_absolute() else root/path
                    try:
                        relative = path.resolve().relative_to(root.resolve())
                    except ValueError:
                        continue
                    # Do not export environments, external models, executables or arbitrary assets.
                    if relative.parts[0] == 'demo' and path.suffix.lower() in allowed:
                        if path.is_file():
                            if digest(path) == value:
                                files.add(path)
                            else:
                                unavailable.append({'path':relative.as_posix(),'reason':'Current bytes differ from historical pin; not selected from this pin'})
                        else:
                            unavailable.append({'path':relative.as_posix(),'reason':'Historical pinned asset missing locally'})
                else:
                    visit(value)
        elif isinstance(obj, list):
            for value in obj: visit(value)
    for summary in sorted((root/'docs/results').glob('*.json')):
        visit(json.loads(summary.read_text(encoding='utf-8')))
    for name in ('initial_state.json', 'final_quality.json', 'full_regression.log', 'snapshot_regression.log',
                 'snapshot_validation.json', 'documentation_checks.json'):
        p = root/'demo/assessment_handoff'/name
        if p.is_file(): files.add(p)
    # Upstream notices only; downloaded source trees/binaries/weights are not distributed.
    notices = root/'docs/attribution'
    if notices.exists(): files.update(p for p in notices.rglob('*') if p.is_file())
    return sorted(files), sorted({json.dumps(item, sort_keys=True):item for item in unavailable}.values(), key=lambda x:x['path'])


def archive(root: Path, paths: list[Path], output: Path, stored=False) -> dict:
    inventory = {}
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED,
                         compresslevel=None if stored else 1, allowZip64=True) as z:
        for number, p in enumerate(paths, 1):
            relative = p.resolve().relative_to(root.resolve()).as_posix()
            before = digest(p)
            z.write(p, relative)
            if digest(p) != before:
                raise ValueError(f'File changed during packaging: {relative}')
            inventory[relative] = {'sha256':before, 'bytes':p.stat().st_size}
            if number % 5000 == 0:
                print(f'{output.name}: {number}/{len(paths)} files', flush=True)
    return {'sha256':digest(output), 'bytes':output.stat().st_size, 'files':inventory}


def package(root: Path, output: Path) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Package output must be fresh')
    output.mkdir(parents=True, exist_ok=True)
    sources = source_files(root)
    evidence, unavailable = evidence_files(root)
    raw = sorted(p for p in (root/'datasets/Given_dataset').rglob('*') if p.is_file())
    if not raw:
        raise FileNotFoundError('Supplied raw dataset is not mounted')
    before_head = git(root, 'rev-parse', 'HEAD').strip()
    started = time.perf_counter()
    archives = {}
    for name, files, stored in [('source_snapshot.zip',sources,False), ('evidence.zip',evidence,False),
                                 ('supplied_raw_dataset.zip',raw,True)]:
        print(f'Packaging {name}: {len(files)} files', flush=True)
        archives[name] = archive(root, files, output/name, stored)
    if git(root, 'rev-parse', 'HEAD').strip() != before_head:
        raise ValueError('Git HEAD changed during packaging')
    manifest = {'format_version':1, 'git_base_at_packaging':before_head,
        'git_status_at_packaging':git(root,'status','--porcelain'),
        'source_kind':'Current worktree snapshot, including pre-existing uncommitted source; not Git HEAD',
        'archives':archives,'historical_assets_not_selected':unavailable,
        'runtime_s':time.perf_counter()-started,'reconstruction_run':False,
        'physical_accuracy':'NOT DEMONSTRATED','assessment_acceptance':'NOT DEMONSTRATED',
        'excluded':['.git','virtual environments','external model weights/source trees/binaries','caches'],
        'limitations':['Historical absolute paths remain as provenance',
                      'Not every native experimental asset is included',
                      'No independent physical survey/repeat/consumer benchmark is available',
                      'Clean-machine installation and live every-number regeneration are not demonstrated']}
    (output/'package_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (output/'HANDOFF.txt').write_text(
        'PHONE TO FLOORPLAN — frozen assessment handoff\n\n'
        'Verify: python scripts/package_assessment.py --verify <this directory>\n'
        'Extract source_snapshot.zip, evidence.zip and supplied_raw_dataset.zip to the SAME fresh root.\n'
        'Start with README.md, docs/INDEX.md and docs/TECHNICAL_REPORT.pdf.\n'
        'Source snapshot includes uncommitted implementation; it is not a Git checkout.\n'
        'Raw data is provided for assessment transfer, not public redistribution.\n'
        'No model weights/environment are bundled. See docs/PHASE3_OPERATIONS.md.\n'
        'Physical accuracy and full assessment acceptance are NOT DEMONSTRATED.\n',encoding='utf-8')
    return manifest


def verify(directory: Path) -> dict:
    manifest = json.loads((directory/'package_manifest.json').read_text(encoding='utf-8'))
    checked = 0
    for name, record in manifest['archives'].items():
        if PurePosixPath(name).name != name: raise ValueError('Invalid archive name')
        path = directory/name
        if digest(path) != record['sha256']: raise ValueError(f'Archive hash mismatch: {name}')
        with zipfile.ZipFile(path) as z:
            if len(z.infolist()) != len(record['files']) or set(z.namelist()) != set(record['files']):
                raise ValueError(f'Archive inventory mismatch: {name}')
            for relative, expected in record['files'].items():
                parts = PurePosixPath(relative).parts
                if relative.startswith('/') or '..' in parts or '\\' in relative:
                    raise ValueError(f'Unsafe archive member: {relative}')
                h = hashlib.sha256(); size = 0
                with z.open(relative) as f:
                    for block in iter(lambda:f.read(1024*1024),b''):
                        h.update(block); size+=len(block)
                if h.hexdigest() != expected['sha256'] or size != expected['bytes']:
                    raise ValueError(f'File hash/size mismatch: {relative}')
                checked += 1
        print(f'Verified {name}: {len(record["files"])} entries',flush=True)
    return {'archives_verified':len(manifest['archives']),'files_verified':checked,
            'sha256_and_crc':'PASS','reconstruction_run':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out',type=Path)
    mode.add_argument('--verify',type=Path)
    args=parser.parse_args()
    if args.verify:
        print(json.dumps(verify(args.verify.resolve()),indent=2))
    else:
        result=package(Path(__file__).resolve().parents[1],args.out.resolve())
        print(json.dumps({'archives':{k:{'files':len(v['files']),'bytes':v['bytes']} for k,v in result['archives'].items()},
                          'runtime_s':result['runtime_s']},indent=2))


if __name__=='__main__': main()
