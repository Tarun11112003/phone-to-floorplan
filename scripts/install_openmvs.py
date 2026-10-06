"""Acquire the official pinned CPU-only Windows OpenMVS release locally."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile

VERSION='v2.4.0'
URL=f'https://github.com/cdcseacave/openMVS/releases/download/{VERSION}/OpenMVS_Windows_x64.zip'
SHA256='0c31660c15c9ebc4c106873cf67564d9570d404aef7a6403451da1b6178b2167'


def install(root):
    root.mkdir(parents=True,exist_ok=True)
    archive=root/'OpenMVS_Windows_x64.zip'
    if not archive.exists():
        with urllib.request.urlopen(URL,timeout=60) as response, archive.with_suffix('.part').open('wb') as target:
            while data:=response.read(1024*1024): target.write(data)
        archive.with_suffix('.part').replace(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError('OpenMVS archive checksum differs from the pinned release')
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            name=PurePosixPath(item.filename)
            if name.is_absolute() or '..' in name.parts or ':' in item.filename: raise ValueError('Unsafe archive member')
            if item.is_dir(): continue
            target=root.joinpath(*name.parts)
            if not target.resolve().is_relative_to(root.resolve()):
                raise ValueError('Archive member escapes the installation directory')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(source.read(item))
    provenance={'version':VERSION,'source':URL,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
                'license':'https://github.com/cdcseacave/openMVS/blob/v2.4.0/LICENSE'}
    (root/'SOURCE.json').write_text(json.dumps(provenance,indent=2))
    print(json.dumps(provenance,indent=2))
    print([str(p) for p in root.rglob('DensifyPointCloud.exe')])


if __name__=='__main__': install(Path(__file__).resolve().parents[1]/'.tools'/'openmvs')
