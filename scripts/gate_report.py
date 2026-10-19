"""Fail-closed CASE-ID-only JUnit reader; report never promotes release status.

JUnit test names do NOT supply identity. A testcase must have an exact `case_id`
property matching the P0 catalogue. Duplicate, unknown, or inconsistent identities
are discarded rather than treated as green. Even valid observed passes are not
release attestation until independently signed run/CI/profile/oracle gates exist.
"""
from __future__ import annotations
import argparse,datetime,json,platform,sys,hashlib
from pathlib import Path
from xml.etree import ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.validate_suite import audit,readcases
ROOT=Path(__file__).resolve().parents[1]

def parse_junit(path,case_ids):
    """Return exact per-case statuses, duplicate IDs, and rejected anonymous testcase count."""
    seen={};dup=set();unknown=[];anonymous=0;case_ids=set(case_ids)
    root=ET.parse(path).getroot()
    for tc in root.iter('testcase'):
        values=[prop.attrib.get('value','') for prop in tc.findall('./properties/property') if prop.attrib.get('name')=='case_id']
        if len(values)!=1:
            anonymous+=1
            continue
        case_id=values[0]
        if case_id not in case_ids:
            unknown.append(case_id)
            continue
        if case_id in seen:
            dup.add(case_id)
            continue
        status='FAIL' if tc.find('failure') is not None or tc.find('error') is not None else ('SKIP' if tc.find('skipped') is not None else 'PASS')
        seen[case_id]=status
    for id in dup:seen.pop(id,None)
    return seen,sorted(dup),sorted(set(unknown)),anonymous

def build(junit=None):
    cases=readcases();audit_status=audit();p0=[c for c in cases if c['phase']=='P0']
    seen={};duplicates=[];unknown=[];anonymous=0
    if junit:
        seen,duplicates,unknown,anonymous=parse_junit(junit,(c['id'] for c in p0))
    count=lambda status:sum(seen.get(c['id'])==status for c in p0)
    passed,failed,skipped=count('PASS'),count('FAIL'),count('SKIP')
    unrun=len(p0)-passed-failed-skipped
    return {
        'generated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'python':platform.python_version(),'os':platform.platform(),
        'suite_catalog_sha256':hashlib.sha256((ROOT/'suite/catalog/test_cases.jsonl').read_bytes()).hexdigest(),
        'design_static':audit_status['static_pass'],
        'suite_p0_total':len(p0),'suite_p0_observed_pass_unattested':passed,
        'suite_p0_fail':failed,'suite_p0_skip':skipped,'suite_p0_not_run':unrun,
        'suite_p0_attested_pass':0,
        'duplicate_junit_case_ids':duplicates,'unknown_junit_case_ids':unknown,
        'anonymous_junit_tests_not_counted':anonymous,
        'junit_identity_policy':'exact testcase/property[@name=case_id]/@value; duplicates rejected',
        'catalog_gates':['G0-E','G0-C','G1','G2','G3','G4'],
        'all_gates_closed':False,'release_claim':'HOLD',
        'reason':'No independently verified official end-code/profile + signed complete P0 evidence; observed passes alone insufficient.',
        'junit_used':str(junit) if junit else None}

def main():
    p=argparse.ArgumentParser();p.add_argument('--junit',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    data=build(a.junit)
    if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    else:print(json.dumps(data,ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
