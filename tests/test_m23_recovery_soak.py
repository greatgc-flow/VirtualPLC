"""M23 internal development suite (no external P0 CASE-ID attestation)."""
from __future__ import annotations
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from scripts import m23_recovery_soak as m


@pytest.mark.parametrize('clients', [1,2,4,8])
def test_valid_clients(clients):
    assert m.validate_options(clients,0.2,1)[0] == clients


@pytest.mark.parametrize('kwargs', [
    {'clients':None}, {'clients':True}, {'clients':0}, {'clients':9},
    {'clients':1.0}, {'clients':'4'}, {'duration':None},
    {'duration':float('nan')}, {'duration':float('inf')},
    {'duration':True}, {'duration':0.1}, {'duration':60.1},
    {'max_cycles':None}, {'max_cycles':True}, {'max_cycles':0},
    {'max_cycles':5001}, {'max_cycles':'3'}
])
def test_invalid_bounded_plan(kwargs):
    with pytest.raises(ValueError):m.validate_options(**kwargs)


@pytest.mark.parametrize('ms',[None, True,0,501,1.1,'30'])
def test_invalid_fault_delay(ms):
    with pytest.raises(ValueError):m.fault_recovery_cycle(ms)


def test_fault_cycle_is_real_loopback_and_write_unchanged():
    result=m.fault_recovery_cycle(20)
    assert result['observed_disconnects']==1
    assert result['reconnects_successful']==1
    assert result['write_before_disconnect_applied'] is False
    assert result['committed_writes_after_reconnect']==1
    assert result['verified_readback'] is True
    assert result['plan_consumed']==3
    assert result['delayed_read_latency_us']>=0


def test_duration_soak_one_process_multicycle():
    report=m.duration_soak(clients=2,duration=0.35,max_cycles=100)
    assert report['cycles']>=2
    assert report['requests_ok']==report['cycles']*2*4
    assert report['requests_failed']==0
    assert report['p50_us']<=report['p95_us']<=report['p99_us']
    assert report['rss_scope']=='one_isolated_server_child_same_pid'
    assert report['server_exited_during_test'] is False
    assert report['active_sessions_observed'] is None
    assert report['rss_interpretation'].startswith('descriptive')
    assert len(report['rss_series'])==report['cycles']
    assert all(r['requests_ok']==(i+1)*8 for i,r in enumerate(report['rss_series']))


def test_cycle_limit_separate_from_duration_limit():
    result=m.duration_soak(1,0.8,2)
    assert result['cycles']==2
    assert result['stopped_by']=='cycle_budget'
    assert result['requests_ok']==8


def test_evidence_files_and_no_release_claim(tmp_path, monkeypatch, capsys):
    # The source hash is cwd-relative; tests run from repository root.
    out=tmp_path/'evidence'
    result=m.run(out,1,0.35,100,10)
    assert result['release']=='HOLD'
    assert result['status'] in ('MEASURED_NOT_CERTIFIED','HOLD_RSS_UNAVAILABLE')
    assert result['p0_external_approvals']==0
    assert m.verify_evidence(out)==result
    assert capsys.readouterr().out==(out/'console.log').read_text(encoding='utf-8')
    assert ET.parse(out/'junit.xml').getroot().tag=='testsuite'
    with pytest.raises(FileExistsError):m.run(out,1,0.2,1,10)


@pytest.mark.parametrize('filename', ['report.json','console.log','junit.xml','MANIFEST_SHA256.json'])
def test_reject_file_modification(tmp_path,filename):
    out=tmp_path/'result'
    m.run(out,1,0.2,10,10)
    target=out/filename
    target.write_bytes(target.read_bytes()+b'JUNK')
    with pytest.raises((ValueError,json.JSONDecodeError)):
        m.verify_evidence(out)


def test_invalid_output_inside_source_tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):m.run(tmp_path/'inside',1,0.2,1,10)
    assert not (tmp_path/'inside').exists()


def test_preflight_no_directory_created_on_wrong_delay(tmp_path):
    p=tmp_path/'wrong'
    with pytest.raises(ValueError):m.run(p,1,0.2,1,501)
    assert not p.exists()


def test_failure_preserves_hold_evidence_without_error_secret(tmp_path, monkeypatch):
    def fail(*args):
        raise RuntimeError('SECRET-PAYLOAD')
    monkeypatch.setattr(m,'duration_soak',fail)
    out=tmp_path/'failure'
    result=m.run(out,1,0.2,2,10)
    assert result['status']=='HOLD_EXECUTION_FAILED'
    assert result['failure_type']=='RuntimeError'
    assert 'SECRET-PAYLOAD' not in (out/'report.json').read_text()
    assert m.verify_evidence(out)['release']=='HOLD'
    root=ET.parse(out/'junit.xml').getroot()
    assert root.attrib['failures']=='2'


def test_report_disallows_forged_release_even_if_hash_updated(tmp_path):
    out=tmp_path/'fresh'
    m.run(out,1,0.2,2,10)
    r=json.loads((out/'report.json').read_text())
    r['release']='APPROVED'
    (out/'report.json').write_bytes(m._json_bytes(r))
    meta=json.loads((out/'MANIFEST_SHA256.json').read_text())
    meta['entries']['report.json']['sha256']=m.base.sha(out/'report.json')
    meta['entries']['report.json']['bytes']=(out/'report.json').stat().st_size
    (out/'MANIFEST_SHA256.json').write_bytes(m._json_bytes(meta))
    with pytest.raises(ValueError,match='release approval'):m.verify_evidence(out)


def test_no_external_p0_proclaimed():
    assert m.MAX_CLIENTS<=8 and m.MAX_DURATION_SEC<=60
    assert 'CASE-' not in m.__doc__


def test_failed_fault_marks_unexecuted_scenarios_failed(tmp_path, monkeypatch):
    def dead(*_): raise RuntimeError('private diagnostic text')
    monkeypatch.setattr(m, 'fault_recovery_cycle', dead)
    out=tmp_path/'no_fault'
    result=m.run(out,1,0.2,2,10)
    assert result['status']=='HOLD_EXECUTION_FAILED'
    assert result['duration_soak'] is None
    root=ET.parse(out/'junit.xml').getroot()
    assert root.attrib['failures']=='3'
    assert len(list(root.iter('failure')))==3
    assert 'private diagnostic text' not in (out/'report.json').read_text()


def test_fails_closed_when_source_sha_changes_mid_run(tmp_path, monkeypatch):
    normal=m.base.sha
    changed={'phase':False}
    def fake_hash(file):
        result=normal(file)
        if changed['phase'] and str(file)=='virtual_plc/server.py':
            return '0'*64
        return result
    monkeypatch.setattr(m.base,'sha',fake_hash)
    monkeypatch.setattr(m,'fault_recovery_cycle',lambda *_: changed.update(phase=True) or {'ok':True})
    monkeypatch.setattr(m,'duration_soak',lambda *_: {'resource_sample_status':'OBSERVED'})
    out=tmp_path/'changed'
    result=m.run(out,1,0.2,2,10)
    assert result['status']=='HOLD_SOURCE_CHANGED'
    assert result['source_unchanged'] is False
    assert ET.parse(out/'junit.xml').getroot().attrib['failures']=='1'
