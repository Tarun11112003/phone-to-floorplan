"""Content hashes for immutable input and reconstruction evidence."""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()
