"""Submission packaging must not hide missing source or leak private paths."""
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from scripts import package_assessment as package


@pytest.mark.parametrize('dirty,untracked', [(' M floorplan/cli.py', ''), ('', 'floorplan/new.py\0')])
def test_source_inventory_rejects_nonfinal_git_state(tmp_path, monkeypatch, dirty, untracked):
    def git(root, *args):
        if args[0] == 'status':
            return dirty
        if '--others' in args:
            return untracked
        return 'floorplan/cli.py\0'
    monkeypatch.setattr(package, 'git', git)
    with pytest.raises(ValueError):
        package.source_files(tmp_path)


def test_source_inventory_contains_only_tracked_files(tmp_path, monkeypatch):
    (tmp_path/'floorplan').mkdir()
    (tmp_path/'floorplan/cli.py').write_text('')
    (tmp_path/'scratch.py').write_text('')
    monkeypatch.setattr(package, 'git', lambda root, *args:
                        'floorplan/cli.py\0' if '--cached' in args else '')
    assert package.source_files(tmp_path) == [tmp_path/'floorplan/cli.py']


def test_portable_archive_preserves_values_and_original_hash(tmp_path):
    record = tmp_path/'record.json'
    original = json.dumps({'path':str(tmp_path/'cloud.bin'), 'error_m':0.7026770276005543,
                           'sensor_timestamp':123.5}).encode()
    record.write_bytes(original)
    output = tmp_path/'evidence.zip'
    result = package.archive(tmp_path, [record], output, portable=True)
    with zipfile.ZipFile(output) as z:
        published = z.read('record.json')
    assert str(tmp_path).encode() not in published
    assert json.loads(published)['error_m'] == json.loads(original)['error_m']
    assert json.loads(published)['sensor_timestamp'] == 123.5
    assert result['files']['record.json']['original_sha256'] == hashlib.sha256(original).hexdigest()
    assert result['files']['record.json']['sha256'] == hashlib.sha256(published).hexdigest()


def test_verify_rejects_changed_archive(tmp_path):
    data = tmp_path/'data.bin'; data.write_bytes(b'original')
    record = package.archive(tmp_path,[data],tmp_path/'source.zip')
    (tmp_path/'package_manifest.json').write_text(json.dumps({'archives':{'source.zip':record}}))
    assert package.verify(tmp_path)['files_verified'] == 1
    with (tmp_path/'source.zip').open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError,match='Archive hash mismatch'):
        package.verify(tmp_path)


def test_verify_rejects_changed_process_bundle(tmp_path):
    bundle = tmp_path/'repository.bundle'; bundle.write_bytes(b'original history')
    manifest = {'archives':{}, 'git_bundle':{'file':bundle.name,
                'sha256':package.digest(bundle), 'bytes':bundle.stat().st_size}}
    (tmp_path/'package_manifest.json').write_text(json.dumps(manifest))
    assert package.verify(tmp_path)['git_bundle_hash_verified'] is True
    bundle.write_bytes(b'altered history')
    with pytest.raises(ValueError,match='Git bundle hash/size mismatch'):
        package.verify(tmp_path)


def test_evidence_package_keeps_offline_review_and_plan_exports(tmp_path):
    output = tmp_path/'demo/final_qa/live_ceiling/result'; output.mkdir(parents=True)
    for name in ['report.html', 'plan.dxf', 'assessment.json', 'plan.svg']:
        (output/name).write_text('{}')
    files, unavailable = package.evidence_files(tmp_path)
    assert {p.name for p in files} == {'report.html', 'plan.dxf', 'assessment.json', 'plan.svg'}
    assert unavailable == []


def test_source_inventory_excludes_personal_notes_and_keeps_benchmarks(tmp_path, monkeypatch):
    names = ['floorplan/cli.py', 'benchmarks/report.md', '.local/notes/design_notes.md',
             'DESIGN_NOTES.md', 'docs/PHASE3_DESIGN.md']
    for name in names:
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('')
    monkeypatch.setattr(package, 'git', lambda root, *args:
                        '\0'.join(names)+'\0' if '--cached' in args else '')
    files = {p.relative_to(tmp_path).as_posix() for p in package.source_files(tmp_path)}
    assert files == {'floorplan/cli.py', 'benchmarks/report.md'}


def test_evidence_package_uses_current_documentation_layout(tmp_path):
    names = ['benchmarks/results/result.json', 'benchmarks/manifests/final_state.json',
             'docs/engineering/investigations/001_supported_cells.md',
             '.local/notes/design_notes.md', 'demo/notices/PHASE3_DESIGN.md']
    for name in names:
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')
    pinned = 'demo/notices/PHASE3_DESIGN.md'
    (tmp_path/'benchmarks/results/result.json').write_text(json.dumps({
        'input_sha256': {pinned: package.digest(tmp_path/pinned)}}))
    files, unavailable = package.evidence_files(tmp_path)
    assert {p.relative_to(tmp_path).as_posix() for p in files} == set(names[:3])
    assert len(unavailable) == 1
    assert unavailable[0]['path'] == pinned
    assert 'Personal planning record' in unavailable[0]['reason']
