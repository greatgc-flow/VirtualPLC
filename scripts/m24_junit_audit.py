"""Strict M24 JUnit audit; exactly one authoritative runtime CASE-ID per P0.

Read-only inputs. No release approval. Never rewrite historical JUnit. Missing,
repeated or failed CASE-ID causes an error; supports an explicit verified ledger.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

CASE = re.compile(r'^CASE-[0-9]{4}$')


def audit(junit_paths, catalog_path, backlog_path):
    paths = [Path(x).resolve(strict=True) for x in junit_paths]
    if not paths or len(set(paths)) != len(paths):
        raise ValueError('nonempty unique JUnit files required')
    catalog={}
    for line in Path(catalog_path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            entry=json.loads(line)
            cid=entry['id']
            if cid in catalog:raise ValueError('duplicate catalog id')
            catalog[cid]=entry
    expected={k for k,v in catalog.items() if v.get('phase')=='P0'}
    backlog=json.loads(Path(backlog_path).read_text(encoding='utf-8'))
    waiting=[]
    for gate in backlog['external_dependencies']:
        waiting.extend(gate['case_ids'])
    if (len(waiting)!=16 or len(set(waiting))!=16 or not set(waiting)<=expected):
        raise ValueError('external P0 backlog corrupted')
    seen={};owner={};checks=[]
    for path in paths:
        raw=path.read_bytes()
        if len(raw)>4_000_000:raise ValueError('JUnit unexpectedly large')
        if b'<!DOCTYPE' in raw or b'<!ENTITY' in raw:raise ValueError('XML entities prohibited')
        root=ET.fromstring(raw)
        if root.tag not in ('testsuites','testsuite'):raise ValueError('JUnit root invalid')
        tests=list(root.iter('testcase'))
        for t in tests:
            key=(t.get('classname'),t.get('name'))
            if not all(type(x) is str and x for x in key) or key in seen:
                raise ValueError('missing or duplicate test node')
            seen[key]=path.name
            if any(t.find(tag) is not None for tag in ('error','failure','skipped')):
                raise ValueError('nonpassing test: '+str(key))
            case_ids=[p.get('value') for p in t.findall('./properties/property')
                      if p.get('name')=='case_id']
            if len(case_ids)>1:raise ValueError('multiple CASE-ID properties')
            if case_ids:
                cid=case_ids[0]
                if cid not in expected or CASE.fullmatch(cid) is None:
                    raise ValueError('unregistered/non-P0 CASE-ID')
                if cid in owner:raise ValueError('duplicate CASE-ID owner: '+cid)
                owner[cid]={'junit':path.name,'test':str(key)}
        checks.append({'file':path.name,'sha256':hashlib.sha256(raw).hexdigest(),'passed_tests':len(tests)})
    covered=set(owner)
    missing=expected-covered
    if missing != set(waiting):
        raise ValueError('P0 missing set differs from external backlog')
    return {'schema':'m24-junit-audit-v1','release':'HOLD','locally_observed':len(covered),
            'total_p0':len(expected),'external_hold_count':len(waiting),
            'unique_tests':len(seen),'duplicate_case_ids':0,
            'unobserved_external_cases':sorted(missing),
            'junit_files':checks,'non_certifying':True}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--junit',nargs='+',required=True)
    p.add_argument('--catalog',default='suite/catalog/test_cases.jsonl')
    p.add_argument('--backlog',default='backlog/M20_BACKLOG.json')
    args=p.parse_args(argv)
    result=audit(args.junit,args.catalog,args.backlog)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
