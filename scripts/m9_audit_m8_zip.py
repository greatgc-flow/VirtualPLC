"""Read-only M8 ZIP audit, preserving incorrect historical manifest as evidence.

Do not silently rewrite or bless the original manifest. Seven divergences require
exact GitHub blob verification against pinned PR HEAD; any other drift is FAIL.
No external network requests. Output creates an exclusively named local report.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

PREFIX = 'VirtualPLC_M8_20261020/'
PINNED = Path(__file__).resolve().parents[1] / 'docs/provenance/M9_PINNED_GITHUB_BLOBS.json'


def git_blob_sha(contents):
    header = ('blob ' + str(len(contents)) + '\0').encode('ascii')
    return hashlib.sha1(header + contents).hexdigest()


def audit(zip_path, *, pinned_path=PINNED):
    pins = json.loads(Path(pinned_path).read_text(encoding='utf-8'))
    with zipfile.ZipFile(zip_path) as archive:
        corrupt = archive.testzip()
        if corrupt is not None:
            raise ValueError('CRC error: ' + corrupt)
        files = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename
            parts = PurePosixPath(name).parts
            if not name.startswith(PREFIX) or '..' in parts or '\\' in name:
                raise ValueError('archive path rejected: ' + name)
            key = name[len(PREFIX):]
            if not key or key in files:
                raise ValueError('empty or duplicated entry')
            files[key] = archive.read(info)
        manifest_bytes = files['SHA256_MANIFEST.json']
        original = json.loads(manifest_bytes)
        if not isinstance(original.get('files'), list) or len(original['files']) != 125:
            raise ValueError('unexpected M8 manifest entries')
        expected = {e['path']: e for e in original['files']}
        if len(expected) != 125:
            raise ValueError('duplicate manifest paths')
        absent, mismatches = [], []
        for path, desc in expected.items():
            data = files.get(path)
            if data is None:
                absent.append(path)
                continue
            calc = hashlib.sha256(data).hexdigest()
            if calc != desc['sha256'] or len(data) != desc['size_bytes']:
                mismatches.append({'path': path, 'original_sha256': desc['sha256'],
                    'actual_sha256': calc, 'original_bytes': desc['size_bytes'],
                    'actual_bytes': len(data), 'git_blob_sha1': git_blob_sha(data)})
        if absent:
            raise ValueError('missing original entries: ' + repr(absent))
        expected_drift = pins['paths']
        if set(expected_drift) != {x['path'] for x in mismatches}:
            raise ValueError('manifest drift differs from checked 7 files: ' + repr(mismatches))
        for item in mismatches:
            if item['git_blob_sha1'] != expected_drift[item['path']]:
                raise ValueError('M8 ZIP file does not match pinned GitHub: ' + item['path'])
        out = {
            'status': 'PASS_RECONCILED_NOT_ORIGINAL_MANIFEST_PASS',
            'original_manifest_valid': False,
            'original_manifest_entries': len(expected),
            'original_manifest_entries_matched': len(expected)-len(mismatches),
            'original_manifest_entries_mismatched': len(mismatches),
            'github_pr_head': pins['head'],
            'm8_zip_sha256': hashlib.sha256(Path(zip_path).read_bytes()).hexdigest(),
            'm8_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'original_m8_zip_entries': len(files),
            'original_m8_zip_crc': 'PASS',
            'git_blob_matches': len(mismatches),
            'mismatches': sorted(mismatches, key=lambda x:x['path']),
            'full_actual_file_manifest': [{'path': k, 'size_bytes': len(v),
                'sha256':hashlib.sha256(v).hexdigest()} for k,v in sorted(files.items())],
            'integrity_statement': 'Original 125-file M8 SHA manifest FAILED for 7 files; '
                 'all 7 agree with GitHub PR HEAD; new inventory is not signed/attested.',
            'release': 'HOLD'
        }
        return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--zip', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args(argv)
    result = audit(args.zip)
    content = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as stream:
        stream.write(content)
    print(content, end='')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
