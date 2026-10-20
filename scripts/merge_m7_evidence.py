"""Merge previously completed, immutable per-phase JUnit runs with CASE-ID audit.

Necessary for environments where a single long pytest invocation times out.
Reject missing inputs, duplicate testcase identities, XML failures and stale
catalog; never manufacture PASS, reclassify NOT_RUN, or attest a release.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from scripts.gate_report import build, parse_junit
from scripts.validate_suite import readcases

ROOT=Path(__file__).resolve().parents[1]
EXPECTED_CATALOG='31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f'

def merge(inputs,out):
    actual=hashlib.sha256((ROOT/'suite/catalog/test_cases.jsonl').read_bytes()).hexdigest()
    if actual!=EXPECTED_CATALOG:raise ValueError('test catalogue changed')
    if len(inputs)!=4 or len(set(map(str,inputs)))!=4:
        raise ValueError('four distinct existing phase JUnits are required')
    all_tests=ET.Element('testsuites')
    evidence=[]
    for name,path in zip(('baseline','tcp_standard','tcp_fuzz','m7_new'),inputs):
        if not path.is_file():raise FileNotFoundError(path)
        xml=ET.parse(path).getroot(); suites=list(xml.findall('.//testsuite'))
        if not suites:raise ValueError('empty JUnit phase: '+name)
        actual_testcases=list(xml.iter('testcase'))
        if not actual_testcases:raise ValueError('no tests in '+name)
        for case in actual_testcases:
            if case.find('failure') is not None or case.find('error') is not None or case.find('skipped') is not None:
                raise ValueError('non-PASS testcase in '+name)
        for suite in suites:all_tests.append(suite)
        evidence.append({'phase':name,'junit_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                         'testcase_count':len(actual_testcases)})
    merged=out/'combined.xml';ET.ElementTree(all_tests).write(merged,encoding='utf-8',xml_declaration=True)
    gate=build(merged)
    if (gate['suite_p0_observed_pass_unattested']!=176 or gate['suite_p0_not_run']!=23 or
            gate['suite_p0_fail'] or gate['suite_p0_skip'] or gate['duplicate_junit_case_ids'] or
            gate['unknown_junit_case_ids']):
        raise ValueError('exact CASE-ID contract mismatch: '+repr(gate))
    (out/'gate.json').write_text(json.dumps(gate,indent=2)+'\n')
    summary={'status':'PASS_LOCAL_ONLY','release':'HOLD','p0_observed_pass':176,'p0_not_run':23,
             'p0_attested_pass':0,'catalog_sha256':actual,'phases':evidence,
             'merged_junit_sha256':hashlib.sha256(merged.read_bytes()).hexdigest()}
    printable=json.dumps(summary,indent=2)+'\n'
    (out/'console.txt').write_text(printable)
    print(printable,end='')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--tcp-standard',type=Path,required=True)
    p.add_argument('--tcp-fuzz',type=Path,required=True)
    p.add_argument('--m7-new',type=Path,required=True)
    p.add_argument('--out',type=Path,default=Path('evidence/m7_verified'))
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    merge([a.baseline,a.tcp_standard,a.tcp_fuzz,a.m7_new],a.out)

if __name__=='__main__':main()
