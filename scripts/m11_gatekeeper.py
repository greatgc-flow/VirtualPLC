"""M11 external-dependency readiness gate; never certifies vendor/client fidelity.

Design: normal stdout is a byte-for-byte match with console.txt; all evidence
is append-by-new-directory (existing directory is refused). No arbitrary code,
network calls, PLC access, or wheel installation. Standard library only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
CATALOG_SHA = '31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f'
WHEEL_SHA = '614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6'
WHEEL_NAME = 'pymcprotocol-0.3.0-py3-none-any.whl'
EXPECTED_REMAINING_SHA = None  # per-case set is pinned to the M10 baseline below
M10_REMAINING = frozenset(('CASE-0018', 'CASE-0019', 'CASE-0020', 'CASE-0027',
    'CASE-0028', 'CASE-0029', 'CASE-0044', 'CASE-0055', 'CASE-0064',
    'CASE-0088', 'CASE-0090', 'CASE-0109', 'CASE-0110', 'CASE-0111',
    'CASE-0128', 'CASE-0147'))


def get_readiness(*, wheel=None, windows_junit=None, model_profile=None, source_head=None):
    """Only checks artifacts. It must never promote an unexecuted test case."""
    catalogue_path = ROOT / 'suite/catalog/test_cases.jsonl'
    digest = hashlib.sha256(catalogue_path.read_bytes()).hexdigest()
    if digest != CATALOG_SHA:
        raise ValueError('catalogue modified; fail closed')
    cases = [json.loads(line) for line in catalogue_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    p0 = {item['id'] for item in cases if item['phase'] == 'P0'}
    if len(p0) != 199 or not M10_REMAINING <= p0:
        raise ValueError('M10 P0 baseline changed or is incomplete')
    remaining_path = ROOT / 'M10_REMAINING_P0.json'
    remaining = json.loads(remaining_path.read_text(encoding='utf-8'))
    actual = [item['id'] for item in remaining['remaining_cases']]
    if len(actual) != 16 or set(actual) != M10_REMAINING:
        raise ValueError('M10 remaining cases mutated: do not reclassify silently')
    state = {'real_client': 'NO_WHEEL', 'manufacturer': 'NO_VERIFIED_PROFILE',
             'windows': 'NO_INDEPENDENT_EVIDENCE'}
    inputs = {}
    if wheel is not None:
        path = Path(wheel)
        if path.name != WHEEL_NAME or not path.is_file():
            raise ValueError('wheel name / location invalid')
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        if observed != WHEEL_SHA:
            raise ValueError('wheel hash mismatch: rejecting payload')
        inputs['wheel_sha256'] = observed
        state['real_client'] = 'WHEEL_HASH_VERIFIED_TEST_NOT_RUN'
    if windows_junit is not None:
        # A user-provided report is *not* independent Windows proof.
        from xml.etree import ElementTree as ET
        path = Path(windows_junit)
        data = path.read_bytes()
        ET.fromstring(data)
        inputs['windows_junit_sha256'] = hashlib.sha256(data).hexdigest()
        state['windows'] = 'UNATTESTED_JUNIT_REQUIRES_PLATFORM_REVIEW'
    if model_profile is not None:
        path = Path(model_profile)
        raw = path.read_bytes()
        profile = json.loads(raw)
        if not isinstance(profile, dict) or not all(x in profile for x in ('model', 'firmware', 'source_url')):
            raise ValueError('model profile missing required fields')
        # Even a declared profile cannot certify end-code numbers or protocol conformance.
        inputs['model_profile_sha256'] = hashlib.sha256(raw).hexdigest()
        state['manufacturer'] = 'MODEL_DECLARED_VENDOR_ERROR_MAP_UNATTESTED'
    if source_head is not None:
        if len(source_head) != 40 or any(c not in '0123456789abcdef' for c in source_head):
            raise ValueError('invalid 40-character git commit SHA')
        inputs['claimed_commit_sha'] = source_head
    return {'schema_version': 1, 'phase': 'M11', 'status': 'BLOCKED_EXTERNAL_GATES',
            'release': 'HOLD', 'baseline_p0_observed_unattested': 183,
            'new_p0_verified': 0, 'p0_total': 199, 'p0_not_run_or_unattested': 16,
            'm10_remaining_case_ids': sorted(M10_REMAINING),
            'catalog_sha256': digest, 'p0_attested': 0,
            'external_gate_status': state, 'input_hashes': inputs,
            'python': platform.python_version(), 'os': platform.platform(),
            'note': 'Provided bytes and local assertions cannot replace verified vendor end codes, a tested genuine client, independent Windows verification or release approval.'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wheel', type=Path)
    p.add_argument('--windows-junit', type=Path)
    p.add_argument('--model-profile', type=Path)
    p.add_argument('--source-head')
    p.add_argument('--out', type=Path, required=True,
                   help='new evidence directory; never overwrite an existing directory')
    a = p.parse_args(argv)
    if a.out.exists():
        raise SystemExit('HOLD: evidence output already exists; refusing overwrite')
    try:
        result = get_readiness(wheel=a.wheel, windows_junit=a.windows_junit,
            model_profile=a.model_profile, source_head=a.source_head)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print('M11_GATE=BLOCKED: ' + str(exc))
        return 2
    payload = (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    a.out.mkdir(parents=True, exist_ok=False)
    (a.out / 'result.json').write_bytes(payload)
    (a.out / 'console.txt').write_bytes(payload)
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()
    return 2  # all external release gates are still open by definition


if __name__ == '__main__':
    raise SystemExit(main())
