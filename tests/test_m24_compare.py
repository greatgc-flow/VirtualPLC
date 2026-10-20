"""Comparison tests: no synthetic result can certify vendor, SLA or leak freedom."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
from scripts import m24_compare as c


@pytest.fixture
def pair(tmp_path):
    # Synthetic *test-only* M23-shaped object; never runtime or approved evidence.
    data={'schema':'m23-recovery-duration-v1', 'status':'MEASURED_NOT_CERTIFIED',
          'release':'HOLD','not_a_certification':True,'loopback_only':True,
          'source_unchanged':True,'p0_external_approvals':0,
          'platform':'TEST_ONLY','python_version':'3.11.synthetic',
          'source_sha256':{'synthetic/test_source.py':'0'*64},
          'duration_soak':{'resource_sample_status':'OBSERVED',
                           'rss_scope':'one_isolated_server_child_same_pid',
                           'p50_us':10,'p95_us':20,'p99_us':40,
                           'requests_ok':100,'requests_failed':0,'clients':4,
                           'duration_requested_seconds':2.0,'max_cycles':20,
                           'rss_initial_kib':100,'rss_final_kib':110,'rss_sample_count':4}}
    p,q=tmp_path/'base.json',tmp_path/'next.json'
    p.write_text(json.dumps(data),encoding='utf-8')
    cand=copy.deepcopy(data)
    cand['duration_soak']['p50_us']+=1
    cand['duration_soak']['p95_us']+=100
    cand['duration_soak']['p99_us']+=150
    cand['duration_soak']['rss_final_kib']+=24
    q.write_text(json.dumps(cand),encoding='utf-8')
    return p,q


def test_descriptive_comparison(pair):
    r=c.compare(*pair)
    assert r['status']=='COMPARABLE_DESCRIPTIVE'
    assert r['release']=='HOLD' and r['no_memory_leak_claim']
    assert r['latency_deltas']['p95_us']['absolute_change_us']==100
    assert r['rss_final_delta_kib']==24
    assert r['thresholds_explicit'] is None


def test_optional_limits_are_caller_owned(pair):
    r=c.compare(*pair,limits={'p95_growth_percent':0, 'rss_growth_kib':0})
    assert r['status']=='OPTIONAL_THRESHOLD_EXCEEDED'
    assert set(r['thresholds_exceeded'])=={'p95_growth_percent','rss_growth_kib'}
    assert r['release']=='HOLD'


def test_high_limits_are_not_vendor_sla(pair):
    r=c.compare(*pair,limits={'p95_growth_percent':9999})
    assert r['status']=='COMPARABLE_DESCRIPTIVE'
    assert r['interpretation']=='observed_only_no_SLA_or_leak_freedom'


@pytest.mark.parametrize('limits', [{}, {'other':1},{'p95_growth_percent':-1},
                                     {'p95_growth_percent':float('nan')},
                                     {'rss_growth_kib':True},[],2])
def test_bad_thresholds_rejected(pair,limits):
    with pytest.raises(ValueError):c.compare(*pair, limits=limits)


def test_identical_file_rejected(pair):
    with pytest.raises(ValueError,match='identical'):c.compare(pair[0],pair[0])


def test_identical_contents_rejected(pair):
    pair[1].write_bytes(pair[0].read_bytes())
    with pytest.raises(ValueError,match='identical'):c.compare(*pair)


@pytest.mark.parametrize('key,val',[('status','HOLD_EXECUTION_FAILED'),
                                    ('release','PASS'),('not_a_certification',False),
                                    ('loopback_only',False),('source_unchanged',False),
                                    ('p0_external_approvals',1)])
def test_forged_approval_and_bad_source_rejected(pair,key,val):
    f=json.loads(pair[1].read_text());f[key]=val
    pair[1].write_text(json.dumps(f),encoding='utf-8')
    with pytest.raises(ValueError):c.compare(*pair)


@pytest.mark.parametrize('key,val',[('p99_us',-1),('p50_us',float('nan')),
                                    ('p95_us',None),('requests_failed',1),
                                    ('rss_sample_count',0),('clients',False),
                                    ('p99_us',1)])
def test_inconsistent_metric_rejected(pair,key,val):
    x=json.loads(pair[1].read_text());x['duration_soak'][key]=val
    pair[1].write_text(json.dumps(x),encoding='utf-8')
    with pytest.raises(ValueError):c.compare(*pair)


def test_source_drift_requires_explicit_override(pair):
    x=json.loads(pair[1].read_text());x['source_sha256']['scripts/m23_recovery_soak.py']='1'*64
    pair[1].write_text(json.dumps(x),encoding='utf-8')
    assert c.compare(*pair)['status']=='INCOMPARABLE'
    r=c.compare(*pair,allow_source_drift=True)
    assert r['status']=='COMPARABLE_DESCRIPTIVE' and r['source_drift_allowed']


def test_different_workload_and_platform_incomparable(pair):
    x=json.loads(pair[1].read_text());x['duration_soak']['clients']=8;x['platform']='Windows'
    pair[1].write_text(json.dumps(x),encoding='utf-8')
    r=c.compare(*pair, limits={'p95_growth_percent':0})
    assert r['status']=='INCOMPARABLE' and len(r['issues'])==2
    assert r['thresholds_exceeded']==[]


def test_single_source_lineage_cannot_be_overwritten(pair,tmp_path):
    result=c.compare(*pair)
    out=tmp_path/'new'
    c.write_once(out,result)
    m=json.loads((out/'MANIFEST_SHA256.json').read_text(encoding='utf-8'))
    for file,v in m['files'].items():
        assert v['sha256']==hashlib.sha256((out/file).read_bytes()).hexdigest()
    with pytest.raises(ValueError):c.write_once(out,result)


def test_source_tree_write_rejected(pair):
    p=Path(__file__).parent/'_DO_NOT_CREATE_M24_COMPARE'
    with pytest.raises(ValueError):c.write_once(p,c.compare(*pair))
