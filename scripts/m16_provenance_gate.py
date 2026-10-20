"""M16 fail-closed independent integrity intake for M14 Windows evidence ZIPs.

This proves captured *bytes* and internal consistency only. It NEVER authenticates
who ran the tool, the OS, the real wheel installation, or manufacturer firmware.
Only read from the archive after checking every name/size/type/CRC/manifest entry.
No network, production PLC, Git mutation, subprocesses, or approval side effects.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import tempfile
import zipfile
from scripts.m14_windows_evidence import inspect_client_run

MAX_FILES = 256
MAX_TOTAL_BYTES = 30 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000
MANIFEST = 'M14_EVIDENCE.json'


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def inspect_archive(path):
    """Validate every archive member, and the *six* real-client evidence claims.

    Archive integrity cannot independently attest provenance or authorize release.
    """
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError('archive is missing or a symlink')
    if path.stat().st_size > MAX_TOTAL_BYTES:
        raise ValueError('archive too large')
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        # Inspect directories too: a malicious ZIP can hide traversal in names
        # not extracted by this reader, but accepting it would taint the archive.
        all_names = [e.filename for e in members]
        if len(all_names) != len(set(all_names)):
            raise ValueError('duplicate entries in ZIP')
        entries = [e for e in members if not e.is_dir()]
        names = [e.filename for e in entries]
        if not 1 < len(names) <= MAX_FILES or len(names) != len(set(names)):
            raise ValueError('missing files, duplicate entries, or excessive files')
        if MANIFEST not in names:
            raise ValueError('M14 evidence manifest missing')
        total = 0
        for e in members:
            name = e.filename
            parts = PurePosixPath(name)
            kind = (e.external_attr >> 16) & 0o170000
            if (not name or '\\' in name or '\x00' in name or parts.is_absolute()
                    or '..' in parts.parts or '.' in parts.parts or name.startswith('/')
                    or kind not in (0, stat.S_IFREG)):
                raise ValueError('unsafe path or nonregular file in archive')
            if e.is_dir():
                if kind not in (0, stat.S_IFDIR):
                    raise ValueError('bad ZIP directory type')
                continue
            if e.file_size > MAX_FILE_BYTES or e.file_size < 0:
                raise ValueError('file size out of bounds')
            if e.file_size > 0 and e.file_size > max(1, e.compress_size) * MAX_COMPRESSION_RATIO:
                raise ValueError('excessive compression ratio')
            total += e.file_size
        if total > MAX_TOTAL_BYTES or archive.testzip() is not None:
            raise ValueError('archive capacity or CRC verification failed')
        manifest = json.loads(archive.read(MANIFEST))
        if manifest.get('schema') != 'virtualplc.m14.client-evidence.v1':
            raise ValueError('unsupported M14 evidence manifest')
        if (manifest.get('conclusion') != 'LOCAL_CLIENT_PASS_INDEPENDENT_ATTESTATION_PENDING'
                or manifest.get('release') != 'HOLD'
                or manifest.get('p0_new_independently_attested') != 0):
            raise ValueError('archive claims unsupported independent approval')
        files = manifest.get('files')
        if not isinstance(files, dict) or set(files) != set(names) - {MANIFEST}:
            raise ValueError('manifest does not cover exactly all payload files')
        if manifest.get('observed_os') != 'Windows':
            raise ValueError('runner did not claim Windows platform')
        for name, digest in files.items():
            data = archive.read(name)
            if (not isinstance(digest, dict) or type(digest.get('bytes')) is not int
                    or digest['bytes'] != len(data)
                    or digest.get('sha256') != sha256_bytes(data)):
                raise ValueError('file size or SHA-256 mismatch: ' + name)
        required = {'client_run/result.json','client_run/console.log',
                    'client_run/pymc_junit.xml','runner_stdout.bin'}
        if not required.issubset(files):
            raise ValueError('required native run artifacts missing')
        # After validating archive paths, hashes and capacities, only extract
        # named artifacts that the pre-existing M14 validator can consume.
        with tempfile.TemporaryDirectory(prefix='vplc-m16-intake-') as scratch:
            root = Path(scratch)
            for name in sorted(required):
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(name))
            for name in sorted(files):
                if name.startswith('client_run/raw_capture/'):
                    dest = root / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(archive.read(name))
            verified = inspect_client_run(root / 'client_run')
        client = manifest.get('client')
        if client != verified:
            raise ValueError('M14 manifest assertions disagree with independently decoded evidence')
        if not verified['claimed_windows_runner']:
            raise ValueError('client subprocess did not report Windows platform')
        return {
            'verdict':'LOCAL_WINDOWS_EVIDENCE_INTACT_NOT_INDEPENDENTLY_ATTESTED',
            'release':'HOLD', 'new_p0_approved':0,
            'case_ids':verified['client_case_ids'],
            'archive_sha256':sha256_bytes(path.read_bytes()),
            'registered_files':len(files),
            'independent_windows_attestation':False,
            'independent_manufacturer_certification':False,
        }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zip', type=Path, required=True)
    p.add_argument('--result', type=Path, required=True)
    args = p.parse_args(argv)
    if args.result.exists():
        print('M16_INTAKE=HOLD: refusing to overwrite result')
        return 2
    try:
        report = inspect_archive(args.zip)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile,
            json.JSONDecodeError) as exc:
        print('M16_INTAKE=HOLD: ' + str(exc))
        return 2
    blob = (json.dumps(report, indent=2, sort_keys=True)+'\n').encode('utf-8')
    args.result.parent.mkdir(parents=True, exist_ok=True)
    with args.result.open('xb') as result:
        result.write(blob)
    # Persist precisely the bytes shown in stdout, not a divergent summary.
    sys.stdout.buffer.write(blob)
    sys.stdout.buffer.flush()
    return 0 # Valid file intake, not release approval


if __name__ == '__main__':
    raise SystemExit(main())
