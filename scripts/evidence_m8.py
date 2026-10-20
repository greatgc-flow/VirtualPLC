"""Local SHA-256 report: fail-closed source integrity, exclusive creation.

This is NOT a digitally signed record, nor OS-level immutable storage.
For independent attestation, a verifier must archive/report with an external key.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path

_FILES = (
    'suite/catalog/test_cases.jsonl', 'suite/catalog/legacy_crosswalk.csv',
    'virtual_plc/server.py', 'virtual_plc/memory.py', 'virtual_plc/protocol.py',
    'virtual_plc/config.py', 'virtual_plc/telemetry.py', 'virtual_plc/__main__.py',
)


def _hash(contents):
    return hashlib.sha256(contents).hexdigest()


def _source_files(root):
    files = []
    for name in _FILES:
        file = root.joinpath(*name.split('/'))
        if not file.is_file() or file.is_symlink():
            raise ValueError('missing or symlinked manifest source: ' + name)
        content = file.read_bytes()
        files.append({'path': name, 'bytes': len(content), 'sha256': _hash(content)})
    return files


def _catalog_counts(root):
    rows = [json.loads(line) for line in (root / _FILES[0]).read_text(encoding='utf-8').splitlines() if line.strip()]
    total, p0 = len(rows), sum(row['phase'] == 'P0' for row in rows)
    if (total, p0) != (208, 199):
        raise ValueError('catalog invariant broken: expected 208 total, 199 P0')
    return total, p0


def _write_new(path, data):
    # O_EXCL is a best-effort local no-overwrite guard; not cryptographic signing.
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise


def create_report(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    files = _source_files(root)
    total, p0 = _catalog_counts(root)
    data = {'schema': 'virtualplc-m8-integrity-v1', 'suite_total': total,
            'suite_p0': p0, 'files': files,
            'note': 'local source integrity only; no client/CI/vendor attestation'}
    blob = (json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True)+'\n').encode()
    output.mkdir(parents=True, exist_ok=True)
    report = output / 'm8_integrity.json'
    digest = output / 'm8_integrity.sha256'
    if report.exists() or digest.exists():
        raise FileExistsError('refuse to replace existing evidence')
    _write_new(report, blob)
    _write_new(digest, (_hash(blob)+'  m8_integrity.json\n').encode('ascii'))
    return report, digest


def verify_report(root, report, digest):
    root, report, digest = Path(root).resolve(), Path(report), Path(digest)
    blob = report.read_bytes()
    expected = digest.read_text('ascii').strip().split()
    if len(expected) != 2 or expected[1] != 'm8_integrity.json' or expected[0] != _hash(blob):
        raise ValueError('report digest mismatch')
    data = json.loads(blob)
    if data.get('schema') != 'virtualplc-m8-integrity-v1':
        raise ValueError('unsupported report schema')
    actual = _source_files(root)
    if data.get('files') != actual:
        raise ValueError('source file SHA-256 mismatch')
    total, p0 = _catalog_counts(root)
    if (data.get('suite_total'), data.get('suite_p0')) != (total, p0):
        raise ValueError('catalog counts changed')
    return dict(data, status='PASS')


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(argv)
    report, digest = create_report(a.root, a.out)
    result = verify_report(a.root, report, digest)
    print(json.dumps({'status': result['status'], 'files': len(result['files']),
                      'suite_p0': result['suite_p0'], 'report': str(report)}, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
