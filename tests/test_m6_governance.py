"""P0 policy contracts: these validate fail-closed mechanisms, NOT human approvals."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pytest
from scripts.governance import (incident_can_close,incident_reopened,verify_sources,
    requires_client_replay,valid_change,record_failure)
from scripts.release_gate import assess_release
from scripts.gate_report import build
ROOT=Path(__file__).resolve().parents[1]
CATALOG={c['id']:c for line in (ROOT/'suite/catalog/test_cases.jsonl').read_text().splitlines() if (c:=json.loads(line))}
IDS=['CASE-0058','CASE-0059','CASE-0060','CASE-0144',
     'CASE-0151','CASE-0155','CASE-0156','CASE-0157']
assert all(CATALOG[x]['phase']=='P0' and CATALOG[x]['runner']=='static_validator' for x in IDS)

@pytest.mark.parametrize('case_id',IDS,ids=IDS)
def test_governance(case_id,record_property,tmp_path):
    record_property('case_id',case_id)
    if case_id=='CASE-0058':
        status=build()
        assert status['suite_p0_attested_pass']==0 and status['release_claim']=='HOLD'
        assert assess_release({'p0_pass_count':199,'observed_failures':0,
            'unknown_or_duplicate_case_ids':False})['status']=='HOLD'
    elif case_id in ('CASE-0059','CASE-0155'):
        assert verify_sources([])
        assert verify_sources([{'url':'https://example.org','license':'MIT','revision':'abc123'}])
        for missing in ('url','license','revision'):
            bad={'url':'https://example.org','license':'MIT','revision':'abc123'}
            bad.pop(missing)
            assert not verify_sources([bad])
        assert 'UNLICENSED_UPSTREAM_SOURCE' in assess_release({
            'third_party_sources':[{'url':'https://example.org','revision':'abc123'}]})['errors']
    elif case_id=='CASE-0060':
        base={'id':'INC-1','trigger':'frame-error','requirement_id':'FR-1',
              'regression_case_id':'CASE-001','metric':'framing_error',
              'reviewer':'QA','regression_pass':True,'metric_checked':True,
              'review_signed':True}
        assert incident_can_close(base)
        for missing in ('trigger','requirement_id','regression_case_id','metric','reviewer'):
            altered=dict(base);altered.pop(missing)
            assert not incident_can_close(altered)
        bad=dict(base,review_signed=False)
        assert not incident_can_close(bad)
    elif case_id=='CASE-0144':
        data=b'PERSONAL_DEVICE_VALUE_0xBEEF'
        file=tmp_path/'failure.json'
        d=record_failure(file,run_id='run-01',seed=121,failing_frame=data,case_id='CASE-0144')
        disk=file.read_text()
        assert d['frame_sha256']==hashlib.sha256(data).hexdigest()
        assert d['run_id']=='run-01' and d['seed']==121
        assert 'PERSONAL_DEVICE_VALUE' not in disk and 'BEEF' not in disk
        with pytest.raises(ValueError):
            record_failure(file,run_id='a\nsecret',seed=121,failing_frame=data,case_id='CASE-0144')
    elif case_id=='CASE-0151':
        change={'id':'CHG-1','reason':'improve parser','owner':'dev',
                'requirements':['FR-1'],'tests':['CASE-0101'],
                'risk':'RISK-1','gate':'G3'}
        assert valid_change(change)
        for name in change:
            b=dict(change);b.pop(name)
            assert not valid_change(b)
        assert not valid_change(dict(change,tests=['CASE-0101','CASE-0101']))
    elif case_id=='CASE-0156':
        closed={'status':'CLOSED','review_signed':True,'regression_pass':True}
        reopened=incident_reopened(closed,{'regression_failed':True,'evidence_hash':'deadbeef'})
        assert reopened['status']=='OPEN' and not reopened['review_signed']
        assert reopened['new_reproduction']=='deadbeef'
        assert closed['status']=='CLOSED'
        assert incident_reopened(closed,{'regression_failed':False})==closed
    elif case_id=='CASE-0157':
        assert requires_client_replay('0.3.0','0.4.0')
        assert requires_client_replay('0.3.0','1.0.0')
        assert not requires_client_replay('0.3.0','0.3.1')
        with pytest.raises(ValueError):requires_client_replay('bad','0.3.0')
    else:raise AssertionError('unimplemented case')
