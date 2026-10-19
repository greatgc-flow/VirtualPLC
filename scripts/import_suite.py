"""Import byte-exact v1.2 TDD suite from the M1 handoff ZIP.
Local operation only; never downloads from internet. Check-only by default.
Simulator source and GitHub regression tests are never overwritten.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

CATALOG_SHA256 = '31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f'
MANIFEST_SHA256 = '919b364233892eb25f7f4b6db5e45692ee35d92d4422dccebba64879e539df49'
ALLOWED_SCRIPTS = frozenset({'scripts/__init__.py', 'scripts/coverage_report.py',
    'scripts/gate_report.py', 'scripts/validate_suite.py', 'scripts/verify_manifest.py'})

def examine_archive(source: Path):
    with zipfile.ZipFile(source) as z:
        bad = z.testzip()
        if bad is not None:
            raise ValueError('ZIP CRC failed: ' + bad)
        items = {}
        for info in z.infolist():
            if info.is_dir():
                continue
            path = PurePosixPath(info.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in info.filename:
                raise ValueError('unsafe archive path: ' + info.filename)
            if (info.external_attr >> 16) & 0o170000 == stat.S_IFLNK:
                raise ValueError('archive contains symlink')
            parts = path.parts
            if len(parts) < 2:
                continue
            inner = '/'.join(parts[1:])
            if inner in items:
                raise ValueError('duplicate archive path: ' + inner)
            items[inner] = info
        raw_manifest = z.read(items['FILE_SHA256_MANIFEST.json'])
        if hashlib.sha256(raw_manifest).hexdigest() != MANIFEST_SHA256:
            raise ValueError('untrusted handoff manifest SHA-256')
        manifest = json.loads(raw_manifest)
        expected = {entry['path']: entry for entry in manifest['files']}
        unexpected = set(items) - set(expected) - {'FILE_SHA256_MANIFEST.json'}
        if unexpected:
            raise ValueError('unaudited archive entries: ' + sorted(unexpected)[0])
        for rel, desc in expected.items():
            if rel not in items:
                raise ValueError('missing manifest file: ' + rel)
            payload = z.read(items[rel])
            if len(payload) != desc['bytes'] or hashlib.sha256(payload).hexdigest() != desc['sha256']:
                raise ValueError('integrity mismatch: ' + rel)
        catalog = z.read(items['suite/catalog/test_cases.jsonl'])
        if hashlib.sha256(catalog).hexdigest() != CATALOG_SHA256:
            raise ValueError('unrecognized catalogue SHA-256')
        cases = [json.loads(line) for line in catalog.splitlines() if line.strip()]
        if len(cases) != 208 or sum(c['phase'] == 'P0' for c in cases) != 199:
            raise ValueError('case counts differ from 208 total / P0 199')
        selected = {}
        for rel, info in items.items():
            if rel in expected and (rel.startswith(('suite/', 'baseline_v1.1/')) or rel in ALLOWED_SCRIPTS):
                selected[rel] = z.read(info)
        return selected

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('zip_file', type=Path)
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--apply', action='store_true', help='write only after verification')
    a = p.parse_args(argv)
    selected = examine_archive(a.zip_file)
    root = a.root.resolve()
    clashes = []
    for rel, payload in selected.items():
        target = root.joinpath(*PurePosixPath(rel).parts)
        if target.is_symlink() or any(x.is_symlink() for x in target.parents if x != root.parent):
            raise ValueError('destination symlink refused: ' + str(target))
        if target.exists() and target.read_bytes() != payload:
            clashes.append(rel)
    if clashes:
        raise ValueError(f'{len(clashes)} conflicting paths, resolve explicitly; first: {clashes[0]}')
    if a.apply:
        for rel, payload in selected.items():
            target = root.joinpath(*PurePosixPath(rel).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(payload)
    print(json.dumps({'status': 'PASS', 'apply': a.apply,
        'files_verified': len(selected), 'catalog_cases': 208, 'P0': 199,
        'catalog_sha256': CATALOG_SHA256}, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
