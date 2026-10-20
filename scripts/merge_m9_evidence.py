"""Fail-closed merge of actually rerun M9 test phases; no attestation forgery.

Only exact JUnit CASE-ID testcase properties count as coverage; any extra/fail/duplicate
case stops the gate. All output is console-mirrored byte-for-byte to console.txt.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
from xml.etree import ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.gate_report import build

EXPECTED_PHASES = ('base','tcp43','fuzz','m9','archive')
CATALOG_SHA = '31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f'


def merge(evidence_dir, output_dir):
    evidence_dir, output_dir = Path(evidence_dir), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError('evidence directory already exists')
    combined=ET.Element('testsuites')
    inputs=[]
    for name in EXPECTED_PHASES:
        path=evidence_dir/(name+'.xml')
        raw=path.read_bytes()
        root=ET.fromstring(raw)
        tests=list(root.iter('testcase'))
        if not tests or any(any(test.find(tag) is not None for tag in
                        ('failure','error','skipped')) for test in tests):
            raise ValueError('missing or unsuccessful testcase in '+name)
        suites=list(root.findall('.//testsuite'))
        if not suites:
            raise ValueError('missing JUnit suites for '+name)
        for suite in suites:
            combined.append(suite)
        inputs.append({'phase':name,'tests':len(tests),'sha256':hashlib.sha256(raw).hexdigest()})
    output_dir.mkdir(parents=True,exist_ok=False)
    target=output_dir/'combined.xml'
    ET.ElementTree(combined).write(target, encoding='utf-8',xml_declaration=True)
    status=build(target)
    if (status['suite_catalog_sha256'] != CATALOG_SHA or
            not status['design_static'] or
            status['suite_p0_observed_pass_unattested'] != 181 or
            status['suite_p0_not_run'] != 18 or
            status['suite_p0_fail'] or status['suite_p0_skip'] or
            status['duplicate_junit_case_ids'] or status['unknown_junit_case_ids']):
        raise ValueError('M9 exact ID gate failure: '+repr(status))
    try:
        client=importlib.metadata.version('pymcprotocol')
    except importlib.metadata.PackageNotFoundError:
        client='NOT_INSTALLED'
    result={
        'result':'PASS_LOCAL_UNATTESTED', 'release':'HOLD',
        'p0_pass_observed':181,'p0_not_run':18,'p0_attested':0,
        'client_version':client,
        'real_pymcprotocol_compatibility':'NOT_RUN',
        'windows':'NOT_RUN','manufacturer_end_codes':'NOT_VERIFIED',
        'platform':platform.platform(), 'python':platform.python_version(),
        'catalog_sha256':CATALOG_SHA,
        'combined_junit_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'inputs':inputs, 'total_pytest_entries':sum(x['tests'] for x in inputs),
        'note':'Counts are unique exact CASE-ID local observations, not certification.'}
    (output_dir/'gate.json').write_text(json.dumps(status,indent=2,ensure_ascii=False)+'\n')
    text=json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+'\n'
    (output_dir/'summary.json').write_text(text)
    (output_dir/'console.txt').write_text(text)
    print(text,end='')
    return result


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--evidence-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(argv)
    merge(args.evidence_dir,args.out)

if __name__=='__main__':
    main()
