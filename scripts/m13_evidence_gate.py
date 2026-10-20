"""M13 external gate intake. Validate bytes without asserting independent attestation.

Only local files are read. This command never communicates with real PLCs,
modifies Git, runs downloaded code, or self-approves a release.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import stat
import sys
import zipfile
from xml.etree import ElementTree as ET

CATALOG_SHA = '31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f'
WHEEL_SHA = '614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6'
WHEEL_NAME = 'pymcprotocol-0.3.0-py3-none-any.whl'
CLIENT_IDS = frozenset(('CASE-0027','CASE-0028','CASE-0029','CASE-0109','CASE-0110','CASE-0111'))
OPEN_IDS = frozenset(('CASE-0018','CASE-0019','CASE-0020','CASE-0027',
    'CASE-0028','CASE-0029','CASE-0044','CASE-0055','CASE-0064',
    'CASE-0088','CASE-0090','CASE-0109','CASE-0110','CASE-0111',
    'CASE-0128','CASE-0147'))
ROOT = Path(__file__).resolve().parents[1]


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def verify_m12_archive(path):
    """Fail closed on untracked/duplicate/unsafe entries and any corrupted byte."""
    with zipfile.ZipFile(path, 'r') as archive:
        names = []
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            p = PurePosixPath(entry.filename)
            if (p.is_absolute() or '..' in p.parts or '\\' in entry.filename
                    or (entry.external_attr >> 16) & 0o170000 == stat.S_IFLNK):
                raise ValueError('unsafe ZIP entry')
            names.append(entry.filename)
        if len(names) != len(set(names)):
            raise ValueError('duplicate ZIP entry')
        bad = archive.testzip()
        if bad:
            raise ValueError('CRC mismatch: ' + bad)
        manifest_name = 'FILE_SHA256_MANIFEST.json'
        if manifest_name not in names:
            raise ValueError('manifest missing')
        manifest = json.loads(archive.read(manifest_name))
        if not isinstance(manifest, dict) or not isinstance(manifest.get('entries'), list):
            raise ValueError('bad manifest schema')
        descriptors = manifest['entries']
        listed = [d.get('path') for d in descriptors]
        if len(listed) != len(set(listed)) or set(listed) != set(names) - {manifest_name}:
            raise ValueError('missing/untracked/duplicate manifest entries')
        for d in descriptors:
            payload = archive.read(d['path'])
            if type(d.get('bytes')) is not int or len(payload) != d['bytes'] or sha256_bytes(payload) != d.get('sha256'):
                raise ValueError('file size/SHA-256 mismatch: ' + d['path'])
        return {'state':'INTEGRITY_ONLY_NOT_AUTHENTICITY',
                'sha256':sha256_bytes(Path(path).read_bytes()),
                'files_verified':len(descriptors), 'crc':'PASS'}


def verify_wheel(path):
    path = Path(path)
    if path.name != WHEEL_NAME or not path.is_file():
        raise ValueError('not the pinned PyPI wheel')
    digest = sha256_bytes(path.read_bytes())
    if digest != WHEEL_SHA:
        raise ValueError('official wheel SHA-256 mismatch')
    return digest


def verify_client_junit(path):
    """Checks test outcomes only; a JUnit file cannot attest actual execution."""
    root = ET.parse(path).getroot()
    if root.tag not in ('testsuite', 'testsuites'):
        raise ValueError('not pytest-style JUnit')
    found = []
    for case in root.iter('testcase'):
        if any(case.find(t) is not None for t in ('failure','error','skipped')):
            raise ValueError('JUnit contains failed, errored, or skipped testcase')
        ids = [x.attrib.get('value') for x in case.findall('./properties/property')
               if x.attrib.get('name') == 'case_id']
        if len(ids) != 1 or ids[0] not in CLIENT_IDS:
            raise ValueError('unmapped/ambiguous client testcase')
        found.append(ids[0])
    if len(found) != len(CLIENT_IDS) or set(found) != CLIENT_IDS:
        raise ValueError('client CASE-ID coverage is incomplete or duplicated')
    return {'case_ids':sorted(found), 'junit_sha256':sha256_bytes(Path(path).read_bytes()),
            'state':'SIX_LOCAL_TEST_RESULTS_PRESENT_UNATTESTED'}


def inspect(*, archive=None, wheel=None, client_junit=None, windows_junit=None,
            manufacturer_profile=None, claimed_head=None):
    if bool(wheel) != bool(client_junit):
        raise ValueError('wheel and client JUnit must be provided together')
    if claimed_head is not None and (len(claimed_head) != 40 or
            any(ch not in '0123456789abcdef' for ch in claimed_head)):
        raise ValueError('source HEAD claim must be a 40-character lowercase hex SHA')
    data = (ROOT/'suite/catalog/test_cases.jsonl').read_bytes()
    if sha256_bytes(data) != CATALOG_SHA:
        raise ValueError('catalogue SHA mismatch')
    catalogue = [json.loads(line) for line in data.splitlines() if line.strip()]
    p0 = {c['id'] for c in catalogue if c['phase'] == 'P0'}
    remaining = json.loads((ROOT/'M12_GATES.json').read_text(encoding='utf-8'))
    open_ids = {i for group in remaining['gates'].values() for i in group['cases']}
    if len(p0) != 199 or open_ids != OPEN_IDS or len(catalogue) != 208:
        raise ValueError('historic P0 baseline changed')
    evidence = {}
    if archive:
        evidence['m12_archive'] = verify_m12_archive(archive)
    if wheel:
        evidence['pymcprotocol_wheel_sha256'] = verify_wheel(wheel)
        evidence['pymcprotocol_client_junit'] = verify_client_junit(client_junit)
    if windows_junit:
        parsed = ET.parse(windows_junit).getroot()
        if parsed.tag not in ('testsuite','testsuites'):
            raise ValueError('not a JUnit document')
        evidence['windows_junit'] = {'state':'FILE_PARSED_OS_ORIGIN_NOT_ATTESTED',
           'sha256':sha256_bytes(Path(windows_junit).read_bytes())}
    if manufacturer_profile:
        profile = json.loads(Path(manufacturer_profile).read_text(encoding='utf-8'))
        if not isinstance(profile, dict) or not all(profile.get(k) for k in ('model','firmware','source_url')):
            raise ValueError('manufacturer model, firmware and source URL required')
        evidence['manufacturer_profile'] = {'state':'METADATA_ONLY_VENDOR_MAP_NOT_ATTESTED',
          'sha256':sha256_bytes(Path(manufacturer_profile).read_bytes())}
    return {'phase':'M13','decision':'HOLD', 'independent_release_approval':False,
       'local_observed_p0_prior':183, 'new_authoritatively_attested_p0':0,
       'p0_total':199,'p0_external_open':len(OPEN_IDS), 'external_case_ids':sorted(OPEN_IDS),
       'catalog_sha256':CATALOG_SHA, 'claimed_git_head_unverified':claimed_head,
       'runtime_os':platform.system(),'runtime_python':platform.python_version(),
       'evidence':evidence, 'meaning':'input integrity is not independent attestation'}


def run(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--m12-zip',type=Path)
    parser.add_argument('--wheel',type=Path)
    parser.add_argument('--client-junit',type=Path)
    parser.add_argument('--windows-junit',type=Path)
    parser.add_argument('--manufacturer-profile',type=Path)
    parser.add_argument('--claimed-head')
    parser.add_argument('--out-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.out_dir.exists():
        print('M13_GATE=BLOCKED: output already exists; refusing overwrite')
        return 2
    try:
        result=inspect(archive=args.m12_zip,wheel=args.wheel,client_junit=args.client_junit,
            windows_junit=args.windows_junit,manufacturer_profile=args.manufacturer_profile,
            claimed_head=args.claimed_head)
    except (OSError,ValueError,KeyError,json.JSONDecodeError,ET.ParseError,zipfile.BadZipFile) as e:
        print('M13_GATE=BLOCKED: '+str(e))
        return 2
    payload=(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf-8')
    args.out_dir.mkdir(parents=True,exist_ok=False)
    (args.out_dir/'result.json').write_bytes(payload)
    (args.out_dir/'console.txt').write_bytes(payload)
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()
    return 2 # HOLD is expected, not successful release

if __name__ == '__main__':
    raise SystemExit(run())
