"""Fail-closed JUnit merge: exact CASE-ID, unchanged 208-catalog, no release claim.

Console JSON matches summary.json exactly. Original JUnit inputs remain immutable.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

from scripts.gate_report import build

PHASES = ('base','tcp_a','tcp_b','tcp_c','m9_additional','m10')
CATALOG_SHA = '31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f'


def merge(evidence_dir, out, expected=183):
    evidence_dir, out = Path(evidence_dir), Path(out)
    if out.exists():
        raise FileExistsError('refuse to overwrite an evidence output directory')
    combined = ET.Element('testsuites')
    inputs = []
    for phase in PHASES:
        path = evidence_dir / (phase + '.xml')
        raw = path.read_bytes()
        tree = ET.fromstring(raw)
        cases = list(tree.iter('testcase'))
        if not cases or any(case.find(x) is not None
                            for case in cases for x in ('failure','error','skipped')):
            raise ValueError('failed, skipped or missing tests in phase: '+phase)
        suites = list(tree.findall('.//testsuite'))
        if tree.tag == 'testsuite':
            suites = [tree]
        if not suites:
            raise ValueError('JUnit has no test suite: '+phase)
        for suite in suites:
            combined.append(suite)
        inputs.append({'phase':phase, 'tests':len(cases),
                       'sha256':hashlib.sha256(raw).hexdigest()})
    tmp_bytes = ET.tostring(combined, encoding='utf-8', xml_declaration=True)
    # gate_report takes a path; write only into a non-published scratch folder
    # under evidence_dir; no final output dir is touched on a failed gate.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='vplc_m10_gate_') as td:
        temp = Path(td) / 'combined.xml'
        temp.write_bytes(tmp_bytes)
        gate = build(temp)
    conditions = (gate['suite_catalog_sha256'] == CATALOG_SHA,
                  gate['design_static'],
                  gate['suite_p0_observed_pass_unattested'] == expected,
                  gate['suite_p0_not_run'] == 199-expected,
                  gate['suite_p0_fail'] == 0, gate['suite_p0_skip'] == 0,
                  not gate['duplicate_junit_case_ids'],
                  not gate['unknown_junit_case_ids'])
    if not all(conditions):
        raise ValueError('P0 CASE-ID gate failure: '+repr(gate))
    try:
        client_version=importlib.metadata.version('pymcprotocol')
    except importlib.metadata.PackageNotFoundError:
        client_version='NOT_INSTALLED'
    result={'phase':'M10', 'status':'PASS_LOCAL_UNATTESTED',
            'release':'HOLD', 'p0_total':199,
            'p0_observed_pass':expected, 'p0_not_run':199-expected,
            'p0_attested':0, 'catalog_sha256':CATALOG_SHA,
            'real_pymcprotocol':'NOT_RUN', 'pymcprotocol_installed':client_version,
            'manufacturer_end_codes':'NOT_VERIFIED',
            'windows_independent':'NOT_RUN',
            'platform':platform.platform(), 'python':platform.python_version(),
            'merged_junit_sha256':hashlib.sha256(tmp_bytes).hexdigest(),
            'input_tests_total':sum(x['tests'] for x in inputs),
            'inputs':inputs,
            'note':'Local observed pass; test count cannot be confused with independent release attestation.'}
    out.mkdir(parents=True, exist_ok=False)
    (out/'combined.xml').write_bytes(tmp_bytes)
    (out/'gate.json').write_text(json.dumps(gate,indent=2,ensure_ascii=False)+'\n')
    payload=json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+'\n'
    (out/'summary.json').write_text(payload)
    (out/'console.txt').write_text(payload)
    print(payload,end='')
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--evidence-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    merge(a.evidence_dir,a.out)

if __name__=='__main__':
    main()
