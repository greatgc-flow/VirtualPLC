"""Generated reverse trace matrices and bounded coverage interpretation. Stdlib only."""
from __future__ import annotations
import json,csv,sys
from collections import Counter,defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.validate_suite import readcases,readcsv,audit
ROOT=Path(__file__).resolve().parents[1]

def main():
 cases=readcases();reqs=readcsv(ROOT/'baseline_v1.1/machine/requirements.csv');risks=readcsv(ROOT/'baseline_v1.1/machine/risks.csv')
 tables=[]
 tables+=['# Requirements ↔ Cases — generated reverse crosswalk','','SSOT: `suite/catalog/test_cases.jsonl`. 상태: **설계 연결 관계만 검증**, 실제 서버 TDD 미실행.','']
 tables+=['| Requirement | Phase | Component | Linked cases | Live wired | Outcome classes |','|---|---|---|---:|---:|---|']
 for req in reqs:
  found=[c for c in cases if req['id'] in c['req_ids']]
  tables.append(f"| {req['id']} | {req['phase']} | {req['component']} | {len(found)} | {sum(c['runner']=='live_executable' for c in found)} | {', '.join(sorted({c['outcome'] for c in found}))} |")
 tables+=['','## Risks → test cases','','| Risk | Severity | CASE count | Trace examples |','|---|---|---:|---|']
 for risk in risks:
  found=[c['id'] for c in cases if risk['id'] in c['risk_ids']]
  tables.append(f"| {risk['id']} | {risk['severity']} | {len(found)} | {', '.join(found[:7])} |")
 tables+=['','## Primary domain → outcome distribution','','| Domain | Success | Decoded reject | Frame close | Deferred |','|---|---:|---:|---:|---:|']
 for dom in sorted(set(c['primary_domain'] for c in cases)):
  cnt=Counter(c['outcome'] for c in cases if c['primary_domain']==dom)
  tables.append(f"| {dom} | {cnt['success']} | {cnt['reject_no_mutation']} | {cnt['close_no_mutation']} | {cnt['future_only']} |")
 (ROOT/'suite/reports').mkdir(exist_ok=True)
 (ROOT/'suite/reports/REVERSE_TRACE_MATRIX.md').write_text('\n'.join(tables)+'\n',encoding='utf-8')
 s=audit()
 report={'source':'catalog/test_cases.jsonl','coverage_not_runtime_success':True,
         'count':len(cases),'p0':s['by_phase']['P0'],'deferred':len(cases)-s['by_phase']['P0'],
         'by_primary_domain':s['by_primary_domain'],'by_runner':s['by_runner'],
         'by_outcome':dict(Counter(c['outcome'] for c in cases)),
         'explicit_gaps':['G0-E model-specific numeric end code','G0-C raw client-captured packet','server implementation absent','130 spec-only runtime adapter bindings','Windows/Linux execution','full security/fuzz/property/stress evidence'],
         'runtime_release_gate':'HOLD'}
 (ROOT/'suite/reports/COVERAGE_SNAPSHOT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(f"trace rows {len(reqs)} req + {len(risks)} risk; {len(cases)} cases; output suite/reports")
if __name__=='__main__':main()
