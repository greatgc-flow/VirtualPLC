"""Recheck four already completed phase JUnits; fail closed on identities and failures.

Never infer P0 cases from testcase names, never sign or attest production release.
A fresh output directory is required so results cannot overwrite prior evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
from xml.etree import ElementTree as ET
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.gate_report import build

CATALOG_SHA = '31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f'
EXPECTED_PHASES = ('baseline', 'tcp', 'fuzz', 'm7m8')


def combine(input_dir, output_dir):
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError('refuse to overwrite existing M8 evidence directory')
    if len(list(input_dir.glob('*.xml'))) < 4:
        raise ValueError('all four independent phase JUnits required')
    all_suites = ET.Element('testsuites')
    records = []
    for phase in EXPECTED_PHASES:
        source = input_dir / (phase + '.xml')
        if not source.is_file():
            raise FileNotFoundError(source)
        raw = source.read_bytes()
        root = ET.fromstring(raw)
        suites = root.findall('.//testsuite')
        tests = list(root.iter('testcase'))
        if not suites or not tests:
            raise ValueError('empty JUnit phase ' + phase)
        for test in tests:
            if any(test.find(element) is not None for element in ('failure', 'error', 'skipped')):
                raise ValueError('non-pass test in phase ' + phase)
        for suite in suites:
            all_suites.append(suite)
        records.append({'phase': phase, 'testcases': len(tests),
                        'junit_sha256': hashlib.sha256(raw).hexdigest()})
    if sum(x['testcases'] for x in records) != 286:
        raise ValueError('expected 286 passing pytest entries')
    output_dir.mkdir(parents=True, exist_ok=False)
    target = output_dir / 'combined.xml'
    ET.ElementTree(all_suites).write(target, encoding='utf-8', xml_declaration=True)
    gate = build(target)
    if (gate['suite_catalog_sha256'] != CATALOG_SHA or not gate['design_static'] or
            gate['suite_p0_observed_pass_unattested'] != 178 or
            gate['suite_p0_not_run'] != 21 or
            gate['suite_p0_fail'] or gate['suite_p0_skip'] or
            gate['duplicate_junit_case_ids'] or gate['unknown_junit_case_ids']):
        raise ValueError('M8 gate contract mismatch: ' + repr(gate))
    try:
        client_version = importlib.metadata.version('pymcprotocol')
    except importlib.metadata.PackageNotFoundError:
        client_version = 'NOT_INSTALLED'
    evidence = {'result': 'PASS_LOCAL_UNATTESTED', 'release': 'HOLD',
                'platform': platform.platform(), 'python': platform.python_version(),
                'pymcprotocol': client_version, 'pymc_client_gate': 'NOT_RUN',
                'observed_p0': 178, 'p0_not_run': 21, 'p0_attested': 0,
                'catalog_sha256': CATALOG_SHA,
                'merged_junit_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                'phases': records}
    (output_dir/'gate.json').write_text(json.dumps(gate, indent=2, sort_keys=True)+'\n')
    record = json.dumps(evidence, indent=2, sort_keys=True)+'\n'
    (output_dir/'console.txt').write_text(record)
    print(record, end='')
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--junit-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    combine(args.junit_dir, args.out)

if __name__ == '__main__':
    main()
