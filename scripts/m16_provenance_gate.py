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
import unicodedata
import sys
import tempfile
import zipfile
from scripts.m14_windows_evidence import inspect_client_run, ROOT

MAX_FILES = 256
MAX_TOTAL_BYTES = 30 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000
MANIFEST = 'M14_EVIDENCE.json'

# Reject cross-platform path ambiguity before extracting archives on any OS.
_WINDOWS_RESERVED = frozenset({'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'} |
                              {'COM' + str(n) for n in range(1, 10)} |
                              {'LPT' + str(n) for n in range(1, 10)} |
                              {'COM' + c for c in ('¹', '²', '³')} |
                              {'LPT' + c for c in ('¹', '²', '³')})


def portable_member_name(name, *, directory=False):
    """Reject ZIP paths unsafe on Windows, even during a Linux review."""
    if not isinstance(name, str) or not name or chr(92) in name:
        raise ValueError('unsafe path or nonregular file in archive')
    raw = name[:-1] if directory and name.endswith('/') else name
    if not raw or raw.startswith('/') or raw.endswith('/'):
        raise ValueError('unsafe path or nonregular file in archive')
    # Win32-compatible evidence paths must have a single portable spelling.
    # Refuse NFD/decomposed names, bidi format controls, lone surrogates and
    # private-use characters before extracting even one member.
    if (unicodedata.normalize('NFC', raw) != raw or
            any(ord(c) < 32 or ord(c) == 127 or
                unicodedata.category(c) in ('Cf', 'Cs', 'Co') for c in raw)):
        raise ValueError('unsafe path or nonregular file in archive')
    for component in raw.split('/'):
        if (not component or component in ('.', '..') or ':' in component or
                component[-1] in ('.', ' ') or
                component.split('.', 1)[0].upper() in _WINDOWS_RESERVED):
            raise ValueError('unsafe path or nonregular file in archive')
    if PurePosixPath(raw).as_posix() != raw:
        raise ValueError('unsafe path or nonregular file in archive')
    return raw


def protected_intake_result(zip_path, result_path, *, source_root=ROOT):
    """Never write potentially private Windows evidence into a public checkout."""
    source = Path(source_root).resolve()
    destination = Path(result_path).resolve()
    archive = Path(zip_path).resolve()
    if (destination == source or source in destination.parents or
            destination == archive or Path(result_path).is_symlink()):
        raise ValueError('intake result path is unsafe or inside public repository')
    return destination



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
        # Windows resolves many distinct ZIP names to the same filesystem
        # object. Reject *before* any byte is written to the scratch directory.
        # Casefold is intentionally stricter than some NTFS locales.
        portable = [(portable_member_name(e.filename, directory=e.is_dir()),
                     e.is_dir()) for e in members]
        normalized = [name.casefold() for name, _ in portable]
        if len(normalized) != len(set(normalized)):
            raise ValueError('portable path alias collision in ZIP')
        files_lower = {name.casefold() for name, is_dir in portable if not is_dir}
        for name, _ in portable:
            parts = name.casefold().split('/')
            if any('/'.join(parts[:n]) in files_lower
                   for n in range(1, len(parts))):
                raise ValueError('file/directory prefix collision in ZIP')
        entries = [e for e in members if not e.is_dir()]
        names = [e.filename for e in entries]
        if not 1 < len(names) <= MAX_FILES or len(names) != len(set(names)):
            raise ValueError('missing files, duplicate entries, or excessive files')
        if MANIFEST not in names:
            raise ValueError('M14 evidence manifest missing')
        total = 0
        for e in members:
            name = e.filename
            portable_member_name(name, directory=e.is_dir())
            kind = (e.external_attr >> 16) & 0o170000
            if e.is_dir():
                if kind not in (0, stat.S_IFDIR):
                    raise ValueError('bad ZIP directory type')
                continue
            if kind not in (0, stat.S_IFREG):
                raise ValueError('unsafe path or nonregular file in archive')
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
        protected_intake_result(args.zip, args.result)
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
