"""Standalone stdlib audit of test suite SSOT (not a virtual PLC implementation)."""
from __future__ import annotations
from pathlib import Path
from collections import Counter,defaultdict
import csv,json,hashlib,zipfile,sys,argparse

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'baseline_v1.1'

def readjson(p):return json.loads(p.read_text(encoding='utf-8'))
def readcases():return [json.loads(s) for s in (ROOT/'suite/catalog/test_cases.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
def readcsv(p):
    with p.open(newline='',encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))

def audit(cases=None,inject=None):
    errors=[];cases=readcases() if cases is None else cases
    reqs=readcsv(BASE/'machine/requirements.csv');origs=readcsv(BASE/'machine/test_matrix.csv')
    risks=readcsv(BASE/'machine/risks.csv');gates=readjson(BASE/'machine/gates.json')
    valid_reqs={r['id']:r for r in reqs}; valid_legacy={t['id'] for t in origs}
    valid_risks={r['id'] for r in risks};valid_gates={x['id'] for x in gates}
    policy=readjson(ROOT/'suite/catalog/partition_policy.json')
    valid_domains=set(policy['primary_domain_values']);valid_outcomes=set(policy['secondary_independent_axes']['outcome'])
    valid_phases={'P0','P1','P2'}
    valid_runners={'static_validator','runtime_adapter','manual_gate','live_executable','deferred'}
    cid=Counter(c.get('id') for c in cases)
    for id,n in cid.items():
        if n!=1:errors.append(f'DUPLICATE_CASE:{id}')
    legacy=defaultdict(list)
    coverage=defaultdict(list);riskcoverage=defaultdict(list)
    live=[];runner=Counter()
    for c in cases:
        id=c.get('id','<missing>')
        required=['id','req_ids','phase','primary_domain','partition','outcome','title','oracle','gate','runner','risk_ids','evidence','source_grade','actions']
        for f in required:
            if f not in c or c[f] is None or (isinstance(c[f],str) and not c[f].strip()):errors.append(f'MISSING_FIELD:{id}:{f}')
        if c.get('phase') not in valid_phases:errors.append(f'PHASE:{id}')
        if c.get('primary_domain') not in valid_domains:errors.append(f'DOMAIN:{id}')
        if c.get('outcome') not in valid_outcomes:errors.append(f'OUTCOME:{id}')
        if c.get('runner') not in valid_runners:errors.append(f'RUNNER:{id}')
        if c.get('gate') not in valid_gates:errors.append(f'GATE:{id}')
        if c.get('evidence') != 'NOT_RUN':errors.append(f'FALSE_EXECUTION_EVIDENCE:{id}')
        if c.get('phase')!='P0' and c.get('runner')!='deferred':errors.append(f'SCOPE_LEAK:{id}')
        if c.get('phase')=='P0' and c.get('runner')=='deferred':errors.append(f'SCOPE_LEAK:{id}')
        if c.get('runner')=='live_executable':
            live.append(c)
            if c.get('actions',{}).get('behavior') not in {'word_roundtrip','bit_roundtrip','framing','fatal_frame','error_reply','multi_client_visibility','fifo_write_read','overlap_concurrent','fuzz_fatal_prefix','fuzz_invalid_command'}:
                errors.append(f'LIVE_ACTION_UNKNOWN:{id}')
        for req in c.get('req_ids',[]):
            if req not in valid_reqs:errors.append(f'ORPHAN_REQ:{id}:{req}')
            else:
                coverage[req].append(id)
                if valid_reqs[req]['phase']!=c['phase']:errors.append(f'REQUIREMENT_PHASE_LEAK:{id}:{req}')
        for risk in c.get('risk_ids',[]):
            if risk not in valid_risks:errors.append(f'ORPHAN_RISK:{id}:{risk}')
            else:riskcoverage[risk].append(id)
        if c.get('legacy_id'):
            legacy[c['legacy_id']].append(id)
            if c['legacy_id'] not in valid_legacy:errors.append(f'ORPHAN_LEGACY:{id}:{c["legacy_id"]}')
        runner[c.get('runner')]+=1
    for r in reqs:
        if r['phase']=='P0' and len(coverage[r['id']])<2:errors.append(f'P0_INSUFFICIENT_CASES:{r["id"]}:{len(coverage[r["id"]])}')
        if r['phase']!='P0' and not coverage[r['id']]:errors.append(f'DEFERRED_NO_PLACEHOLDER:{r["id"]}')
    for id in valid_legacy:
        if len(legacy[id])!=1:errors.append(f'LEGACY_UNMAPPED_OR_DUPLICATE:{id}:{len(legacy[id])}')
    for risk in valid_risks:
        if not riskcoverage[risk]:errors.append(f'RISK_UNTESTED:{risk}')
    # Every declared P0 domain either has an executable integration case or a documented adapter case.
    for dom in valid_domains:
        if not any(c['primary_domain']==dom and (dom=='scenario' or c['phase']=='P0') for c in cases):errors.append(f'AXIS_NOT_REPRESENTED:{dom}')
    fixtures=readjson(ROOT/'suite/fixtures/wire_vectors_baseline.json')
    for v in fixtures:
        rq=bytes.fromhex(v['request_hex']);rp=bytes.fromhex(v['response_hex'])
        if rq[:2]!=b'\x50\x00' or len(rq)!=9+int.from_bytes(rq[7:9],'little'):
            errors.append(f'REQUEST_FIXTURE_FORMAT:{v["id"]}')
        if rp[:2]!=b'\xd0\x00' or len(rp)!=9+int.from_bytes(rp[7:9],'little'):
            errors.append(f'RESPONSE_FIXTURE_FORMAT:{v["id"]}')
    # Expect minimum 40 executable P0 wire/network tests; no fake positive error code maps.
    if len(live)<40:errors.append('INSUFFICIENT_LIVE_EXECUTABLES')
    code=readjson(ROOT/'suite/fixtures/error_codes_TEMPLATE.json')
    if code['status']!='BLOCKED_UNTIL_G0_E' or code['vendor_end_codes']:
        errors.append('UNVERIFIED_ERROR_CODES_FILLED')
    stats={'cases':len(cases),'by_phase':dict(Counter(c['phase'] for c in cases)),
           'by_primary_domain':dict(Counter(c['primary_domain'] for c in cases)),
           'by_runner':dict(runner),'p0_requirements':sum(r['phase']=='P0' for r in reqs),
           'p0_requirements_linked':sum(r['phase']=='P0' and bool(coverage[r['id']]) for r in reqs),
           'legacy_tests':len(valid_legacy),'legacy_linked':sum(bool(legacy[id]) for id in valid_legacy),
           'risks':len(valid_risks),'risks_linked':sum(bool(riskcoverage[r]) for r in valid_risks),
           'live_executable_spec_count':len(live),
           'errors':errors,'static_pass':not errors,
           'actual_server_test_pass':False,'actual_protocol_compatibility_verified':False}
    return stats

def run_mutation_probes():
    raw=readcases(); checks={}
    def must_fail(label,change):
        cases=json.loads(json.dumps(raw));change(cases)
        checks[label]=bool(audit(cases)['errors'])
    must_fail('duplicate_id',lambda a:a[1].update(id=a[0]['id']))
    must_fail('unknown_requirement',lambda a:a[1].update(req_ids=['FR-999']))
    must_fail('unknown_risk',lambda a:a[1].update(risk_ids=['RK-999']))
    must_fail('wrong_phase',lambda a:a[1].update(phase='P2'))
    must_fail('orphan_legacy',lambda a:a[0].update(legacy_id='TC-999'))
    must_fail('false_green',lambda a:a[1].update(evidence='PASS'))
    must_fail('scope_promotion',lambda a:a[0].update(runner='deferred'))
    must_fail('live_behavior_drift',lambda a:next(c for c in a if c['runner']=='live_executable')['actions'].update(behavior='unbound'))
    return checks

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--json',action='store_true');p.add_argument('--mutation',action='store_true');a=p.parse_args()
    st=audit()
    if a.mutation:
        probes=run_mutation_probes();st['validator_mutation_probes']=probes
        if not all(probes.values()):st['errors'].append('VALIDATOR_MUTATION_SELFTEST_FAIL');st['static_pass']=False
    print(json.dumps(st,ensure_ascii=False,indent=2) if a.json else
          f"suite static {'PASS' if st['static_pass'] else 'FAIL'}; cases={st['cases']}; original={st['legacy_linked']}/{st['legacy_tests']}; live-ready={st['live_executable_spec_count']}; errors={st['errors']}")
    sys.exit(0 if st['static_pass'] else 1)
if __name__=='__main__':main()
