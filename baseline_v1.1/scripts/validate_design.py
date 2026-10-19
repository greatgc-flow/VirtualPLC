#!/usr/bin/env python3
"""OFFLINE STATIC DESIGN CONTRACT AUDIT. Not a PLC runtime or protocol integration test.
Exit 0 only when machine-readable design references and fixture structural checks pass.
May be run after design.zip extraction: python scripts/validate_design.py
"""
import csv, json, hashlib, collections, sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]; M=P/'machine'
problems=[]; stats={}
def fail(msg): problems.append(msg)
def read_csv(name):
    with (M/name).open(newline='',encoding='utf-8') as f: return list(csv.DictReader(f))
def read_json(path): return json.loads((P/path).read_text(encoding='utf-8'))
def uniq(items,domain):
    vals=[i['id'] for i in items]; dup=[x for x,c in collections.Counter(vals).items() if c>1];
    if dup: fail(domain+' duplicate IDs '+str(dup))
    return set(vals)

def checks():
    reqs=read_csv('requirements.csv');tests=read_csv('test_matrix.csv');risks=read_csv('risks.csv'); sources=read_json('machine/sources.json');gates=read_json('machine/gates.json');comps=read_json('machine/components.json'); vectors=read_json('fixtures/wire_vectors.json'); feedback_schema=read_json('machine/change_event.schema.json')
    reqids=uniq(reqs,'requirements');testids=uniq(tests,'tests');riskids=uniq(risks,'risks');srcids=uniq(sources,'sources');gateids=uniq(gates,'gates');vecids=uniq(vectors,'vectors')
    
    expected_loop={'issue_id','trigger','category','severity','evidence_sha256','scope','linked_requirements','linked_tests','root_cause','change_decision','gate','owner_role','validation','observed_metrics','closure_state','closure_reason'}
    if not expected_loop.issubset(set(feedback_schema.get('required',[]))):fail('change event schema lacks required closure fields')
    if feedback_schema.get('additionalProperties') is not False:fail('change event schema allows undefined fields')
    if not {'OPEN','HOLD','CLOSED','REOPENED'}.issubset(set(feedback_schema.get('properties',{}).get('closure_state',{}).get('enum',[]))):fail('feedback loop lacks reopening state')
    stats.update({'requirements':len(reqs),'test_specs':len(tests),'risks':len(risks),'sources':len(sources),'gates':len(gates),'fixtures':len(vectors)})
    if set(r['phase'] for r in reqs)!={'P0','P1','P2'}: fail('phase partition inconsistent')
    if set(g['status'] for g in gates)-{'PASS_STATIC','PASS_DESK','OPEN','NOT_RUN'}: fail('unrecognized gate status')
    if len([g for g in gates if g['status']=='NOT_RUN'])==0: fail('TDD not-run gate missing')
    for r in reqs:
        if any(not r.get(k) for k in ('id','category','phase','priority','statement','acceptance','component','gate','source_ids','risk_ids')):fail('req missing fields '+r['id'])
        if r['category'] not in ('FR','NFR','SEC','OPS','GOV'):fail('bad category '+r['id'])
        if r['phase'] not in ('P0','P1','P2'):fail('bad phase '+r['id'])
        if r['component'] not in comps:fail('unknown component '+r['id'])
        if r['gate'] not in gateids:fail('unknown gate '+r['id'])
        for src in r['source_ids'].split(';'):
            if src not in srcids:fail('missing source '+r['id']+' '+src)
        for risk in r['risk_ids'].split(';'):
            if risk not in riskids:fail('missing risk '+r['id']+' '+risk)
    tc_count=collections.Counter()
    for t in tests:
        if any(not t.get(k) for k in ('id','req_ids','phase','layer','scenario','oracle','gate','status','evidence')):fail('test missing fields '+t['id'])
        if t['gate'] not in gateids:fail('unknown test gate '+t['id'])
        if t['status']!='SPECIFIED_NOT_RUN' or t['evidence']!='NONE': fail('pretend TDD evidence '+t['id'])
        refs=t['req_ids'].split(';')
        for rid in refs:
            if rid not in reqids:fail('orphan testcase '+t['id']+' '+rid)
            else:
                tc_count[rid]+=1
                if next(r['phase'] for r in reqs if r['id']==rid)!=t['phase']:fail('phase mismatch '+t['id'])
    for r in reqs:
        if r['phase']=='P0' and tc_count[r['id']]<1:fail('uncovered P0 req '+r['id'])
        if r['phase'] in ('P1','P2') and tc_count[r['id']] and r['priority']=='MUST':fail('extension MUST/phase contradiction '+r['id'])
    for risk in risks:
        if risk['primary_req'] not in reqids:fail('orphan risk '+risk['id'])
        if risk['gate'] not in gateids:fail('orphan risk gate '+risk['id'])
        if risk['severity'] not in ('LOW','MEDIUM','HIGH','CRITICAL'):fail('bad risk level '+risk['id'])
    for v in vectors:
        name=v['id'];srcs=v['source_ids']
        if not srcs or any(src not in srcids for src in srcs):fail('vector without valid sources '+name)
        if v['source_grade'] not in ('OFFICIAL','DERIVED','OFFICIAL_PAYLOAD_DERIVED_FRAME','OFFICIAL_PACKING_DERIVED_FRAME','CLIENT_CAPTURE'):fail('bad grade '+name)
        try:req=bytes.fromhex(v['request_hex']);resp=bytes.fromhex(v['response_hex'])
        except ValueError:fail('bad hex '+name);continue
        if len(req)<21 or req[:2]!=b'\x50\x00' or len(req)!=9+int.from_bytes(req[7:9],'little'):fail('bad request header or length '+name)
        if len(resp)<11 or resp[:2]!=b'\xd0\x00' or len(resp)!=9+int.from_bytes(resp[7:9],'little'):fail('bad response header or length '+name)
        if req[2:7]!=resp[2:7]:fail('route mismatch '+name)
        command=int.from_bytes(req[11:13],'little');sub=int.from_bytes(req[13:15],'little');points=int.from_bytes(req[19:21],'little');payload=req[21:]
        if command not in (0x0401,0x1401) or sub not in (0,1):fail('unsupported op in MVP vectors '+name)
        if req[18]!=({0:0xA8,1:0x90}[sub]):fail('device unit mismatch '+name)
        if points<1:fail('zero point '+name)
        expected=points*2 if sub==0 else (points+1)//2
        if command==0x0401 and payload:fail('read has trailing payload '+name)
        if command==0x1401 and len(payload)!=expected:fail('write value length mismatch '+name)
        if command==0x1401 and resp[9:11]!=b'\x00\x00':fail('write response nonzero '+name)
        if command==0x0401 and len(resp[11:])!=expected:fail('read response value count mismatch '+name)
        if sub==1:
            for b in (payload if command==0x1401 else resp[11:]):
                if (b>>4)>1 or (b&15)>1:fail('bad bit nibble '+name)
            bits=(payload if command==0x1401 else resp[11:])
            if points%2 and bits and bits[-1]&0x0f:fail('odd bit tail nonzero '+name)
        if v['source_grade']=='CLIENT_CAPTURE':fail('client captures falsely claimed '+name)
    if len(set(v['request_hex'].replace(' ','').lower() for v in vectors))!=len(vectors):fail('duplicate requests in fixture registry')
    refs=list(P.rglob('*.md'))
    if not refs or not (P/'docs/12_NEXT_CHAT_TDD_PROMPT.md').exists():fail('essential documents missing')
    # Verify file manifest if present; generated with filelist excludes itself.
    mp=P/'SHA256_MANIFEST.json'
    if mp.exists():
        man=read_json('SHA256_MANIFEST.json'); listed=man['files']
        actual={str(p.relative_to(P)):p for p in P.rglob('*') if p.is_file() and p!=mp}
        if set(listed)!=set(actual): fail('file manifest path set mismatches '+str(sorted(set(listed)^set(actual))))
        for path,fp in actual.items():
            data=fp.read_bytes()
            if listed[path]['size']!=len(data) or listed[path]['sha256']!=hashlib.sha256(data).hexdigest():fail('sha mismatch '+path)
        stats['manifest_entries']=len(listed)
    stats['P0_requirement_coverage']=sum(1 for r in reqs if r['phase']=='P0' and tc_count[r['id']]>0)
    stats['P0_requirements']=sum(r['phase']=='P0' for r in reqs)

checks()
result={'verdict':'PASS_STATIC' if not problems else 'FAIL_STATIC', 'checked':'Offline design SSOT foreign keys and wire fixture structure; DOES NOT run server/TDD/client capture', 'metrics':stats,'problems':problems}
print(json.dumps(result,ensure_ascii=False,indent=2))
sys.exit(1 if problems else 0)
