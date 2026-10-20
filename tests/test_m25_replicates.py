"""M25 synthetic fixtures only; never release or real vendor attestation."""
import copy
import hashlib
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from scripts import m25_replicates as m


def _write_bundle(root, n=1, changes=None):
    root.mkdir()
    report = {
        'schema':'m23-recovery-duration-v1','status':'MEASURED_NOT_CERTIFIED',
        'release':'HOLD','not_a_certification':True,'loopback_only':True,
        'source_unchanged':True,'p0_external_approvals':0,'platform':'SYNTHETIC_ONLY',
        'python_version':'3.11.mock','source_sha256':{'synthetic.py':'0'*64},
        'fault_recovery':{'verified_readback':True,'write_before_disconnect_applied':False,
                          'reconnects_successful':1,'committed_writes_after_reconnect':1,
                          'delay_requested_ms':35},
        'duration_soak':{'resource_sample_status':'OBSERVED',
            'rss_scope':'one_isolated_server_child_same_pid',
            'clients':1,'duration_requested_seconds':0.5,'max_cycles':1000,
            'cycles':3,'requests_ok':12,'requests_failed':0,
            'p50_us':10+n,'p95_us':20+n,'p99_us':40+n,
            'rss_initial_kib':100+n,'rss_final_kib':110+n,'rss_sample_count':3,
            'rss_slope_kib_per_minute':-1*n,
            'rss_series':[{'elapsed_s':(i+1)*0.1,'requests_ok':4*(i+1),
                           'server_rss_kib':100+n+i} for i in range(3)]}
    }
    if changes:
        for dotted,val in changes.items():
            parts=dotted.split('.')
            x=report
            for part in parts[:-1]:x=x[part]
            x[parts[-1]]=val
    (root/'report.json').write_text(json.dumps(report),encoding='utf-8')
    log=('M23 LOCAL FAULT/RECOVERY + SINGLE-PROCESS SOAK; NOT RELEASE CERTIFICATION\n'
         'FAULT: drop-before-write=verified, reconnect=verified, readback=verified\n'
         'SOAK: clients=1 cycles=3 requests=12 p95=20us samples=3\n'
         'STATUS=MEASURED_NOT_CERTIFIED RELEASE=HOLD\n')
    (root/'console.log').write_text(log,encoding='utf-8')
    suite=ET.Element('testsuite',name='m23_internal_descriptive',tests='3',failures='0')
    for name in m.EXPECTED_TESTS:ET.SubElement(suite,'testcase',name=name,classname='m23_internal')
    ET.ElementTree(suite).write(root/'junit.xml',encoding='utf-8',xml_declaration=True)
    _remake_manifest(root)
    return root


def _remake_manifest(root):
    d={'schema':'m23-local-evidence-v1','entries':{}}
    for name in m.FILES:
        b=(root/name).read_bytes()
        d['entries'][name]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
    (root/'MANIFEST_SHA256.json').write_text(json.dumps(d),encoding='utf-8')


@pytest.fixture
def runs(tmp_path):
    return [_write_bundle(tmp_path/f'r{i}',i) for i in range(1,4)]


def test_baseline_repeated_summary(runs):
    value=m.analyze(runs)
    assert value['status']=='REPEATED_OBSERVATIONS_ONLY'
    assert value['metrics']['p95_us']['median']==22
    assert value['metrics']['p95_us']['median_absolute_deviation']==1
    assert value['metrics']['rss_slope_kib_per_minute']['median']==-2
    assert value['release']=='HOLD' and not value['independent_approval']
    assert value['provenance']=='sha256_integrity_only_no_signed_origin'


@pytest.mark.parametrize('k,v', [('status','PASS'),('release','APPROVED'),
                                   ('not_a_certification',False),('p0_external_approvals',1),
                                   ('source_unchanged',False),('loopback_only',False),
                                   ('fault_recovery.verified_readback',False),
                                   ('fault_recovery.reconnects_successful',0),
                                   ('fault_recovery.write_before_disconnect_applied',True),
                                   ('duration_soak.requests_failed',1),
                                   ('duration_soak.p95_us',float('nan')),
                                   ('duration_soak.requests_ok',999),
                                   ('duration_soak.rss_sample_count',2),
                                   ('duration_soak.cycles',99),
                                   ('duration_soak.p99_us',0)])
def test_fake_success_rejected_even_with_valid_manifest(runs,k,v):
    f=runs[0]/'report.json'
    obj=json.loads(f.read_text())
    parts=k.split('.');x=obj
    for part in parts[:-1]:x=x[part]
    x[parts[-1]]=v
    f.write_text(json.dumps(obj))
    _remake_manifest(runs[0])
    with pytest.raises(ValueError):m.verify_run(runs[0])


@pytest.mark.parametrize('kind',['extra','missing','hash','symlink','junit_failure',
                                 'junit_skip','junit_duplicate','bad_console','xml_entity',
                                 'rss_nonmonotonic','rss_requests'])
def test_corrupted_bundle_rejected(runs,kind,tmp_path):
    p=runs[0]
    if kind=='extra':(p/'extra.txt').write_text('x')
    elif kind=='missing':(p/'report.json').unlink()
    elif kind=='hash':(p/'report.json').write_bytes(b'{}')
    elif kind=='symlink':
        (p/'console.log').unlink();(p/'console.log').symlink_to(tmp_path/'missing')
    elif kind in ('junit_failure','junit_skip','junit_duplicate'):
        f=p/'junit.xml';tree=ET.parse(f);root=tree.getroot()
        if kind=='junit_failure':ET.SubElement(list(root)[0],'failure',message='fail')
        elif kind=='junit_skip':ET.SubElement(list(root)[0],'skipped')
        else:ET.SubElement(root,'testcase',name='fault_cycle',classname='m23_internal')
        tree.write(f,encoding='utf-8');_remake_manifest(p)
    elif kind=='bad_console':
        (p/'console.log').write_text('PASS CERTIFIED!');_remake_manifest(p)
    elif kind=='xml_entity':
        (p/'junit.xml').write_bytes(b'<!DOCTYPE test [<!ENTITY x "evil">]><testsuite/>')
        _remake_manifest(p)
    else:
        f=p/'report.json';obj=json.loads(f.read_text())
        x=obj['duration_soak']['rss_series']
        if kind=='rss_nonmonotonic':x[1]['elapsed_s'] = x[0]['elapsed_s']
        else:x[1]['requests_ok'] = 999
        f.write_text(json.dumps(obj));_remake_manifest(p)
    with pytest.raises((ValueError,UnicodeError)):m.verify_run(p)


@pytest.mark.parametrize('field,value,issue',[
    ('platform','Windows','environment_mismatch'),
    ('source_sha256',{'changed.py':'f'*64},'source_mismatch'),
    ('duration_soak.clients',2,'workload_mismatch'),
    ('fault_recovery.delay_requested_ms',55,'fault_plan_mismatch'),
])
def test_incomparable_observations_remain_hold(runs,field,value,issue):
    p=runs[-1];f=p/'report.json';obj=json.loads(f.read_text());parts=field.split('.')
    x=obj
    for k in parts[:-1]:x=x[k]
    x[parts[-1]]=value
    if field=='duration_soak.clients':
        # satisfy local internal consistency while making workload incomparable
        obj['duration_soak']['requests_ok']=24
        for i,row in enumerate(obj['duration_soak']['rss_series']):row['requests_ok']=8*(i+1)
    f.write_text(json.dumps(obj));_remake_manifest(p)
    result=m.analyze(runs)
    assert result['status']=='INCOMPARABLE'
    assert issue in result['issues'] and result['release']=='HOLD'


def test_missing_duplicate_and_equal_content(runs,tmp_path):
    with pytest.raises(ValueError):m.analyze(runs[:2])
    with pytest.raises(ValueError):m.analyze([runs[0]]*3)
    f=runs[2]/'report.json';f.write_bytes((runs[0]/'report.json').read_bytes());_remake_manifest(runs[2])
    with pytest.raises(ValueError,match='identical report'):m.analyze(runs)


@pytest.mark.parametrize('count',[True,0,1,31,'3'])
def test_invalid_min_runs(runs,count):
    with pytest.raises(ValueError):m.analyze(runs,min_runs=count)


def test_write_once_and_stdout_evidence(runs,tmp_path,capsys):
    report=m.analyze(runs)
    out=tmp_path/'output'
    m.write_once(out,report)
    assert capsys.readouterr().out.encode('utf-8')==(out/'console.log').read_bytes()
    manifest=json.loads((out/'MANIFEST_SHA256.json').read_text())
    for name, info in manifest['entries'].items():
        assert info['sha256']==hashlib.sha256((out/name).read_bytes()).hexdigest()
    with pytest.raises(ValueError):m.write_once(out,report)


def test_source_tree_output_rejected(runs):
    with pytest.raises(ValueError):m.write_once(Path(__file__).parent/'NO_M25_OUTPUT',m.analyze(runs))


def test_run_bundle_symlink_rejected(runs,tmp_path):
    link=tmp_path/'linked'
    link.symlink_to(runs[0],target_is_directory=True)
    with pytest.raises(ValueError):m.verify_run(link)
