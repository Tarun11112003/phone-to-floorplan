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
