"""M26 orchestrator tests: strict caps, safe output, evidence failure modes."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

import pytest
from scripts import m26_multi_run as m26


@pytest.mark.parametrize('value',[0,1,2,31,True,False,3.0,None,'3',-1])
def test_bad_run_count(value):
    with pytest.raises(ValueError):m26.validate_options(runs=value)


@pytest.mark.parametrize('field,value',[
    ('clients',0),('clients',9),('clients',True),
    ('duration',0.1),('duration',61),('duration',float('nan')),('duration',float('inf')),
    ('max_cycles',0),('max_cycles',5001),('max_cycles',False),
    ('timeout',4.9),('timeout',241),('timeout',float('nan')),('timeout',True),
    ('delay_ms',0),('delay_ms',501),('delay_ms',True),
])
def test_bad_workload(field,value):
    with pytest.raises(ValueError):m26.validate_options(**{field:value})


def test_run_count_edges():
    assert m26.validate_options(runs=3)['runs']==3
    assert m26.validate_options(runs=30)['runs']==30


def test_output_refuses_existing_folder(tmp_path):
    with pytest.raises(FileExistsError):m26.fresh_destination(tmp_path)


def test_output_refuses_source_folder():
    with pytest.raises(ValueError):m26.fresh_destination(m26.ROOT/'inside')


def test_output_refuses_symlink_parent(tmp_path):
    target=tmp_path/'dest'; target.mkdir()
    link=tmp_path/'alias'; link.symlink_to(target,target_is_directory=True)
    with pytest.raises(ValueError):m26.fresh_destination(link/'new')


def test_preflight_missing_source_fails_before_creating_output(tmp_path,monkeypatch):
    dest=tmp_path/'new'
    def fail():raise ValueError('broken source')
    monkeypatch.setattr(m26,'source_fingerprint',fail)
    with pytest.raises(ValueError):m26.run(dest)
    assert not dest.exists()


def _fake_factory(status='EXECUTED'):
    counter={'value':0}
    def runner(target,opts):
        counter['value']+=1
        if status=='EXECUTED':
            target.mkdir()
            (target/'dummy.txt').write_text(str(counter['value']),encoding='utf-8')
        return {'status':status,'return_code':0 if status=='EXECUTED' else 1,
                'elapsed_s':0.01,'stdout':b'FAKE local test output\n'}
    return runner


def _run_mocked(tmp_path,monkeypatch,status='EXECUTED',summary='REPEATED_OBSERVATIONS_ONLY',**kw):
    monkeypatch.setattr(m26.m25,'verify_run',lambda path:{'verified':True})
    monkeypatch.setattr(m26.m25,'analyze',lambda paths:{'status':summary})
    chunks=[]
    dest=tmp_path/'evidence'
    report=m26.run(dest,child_runner=_fake_factory(status),emit_bytes=chunks.append,**kw)
    return dest,report,b''.join(chunks)


def test_mocked_success_evidence_and_exact_screen(tmp_path,monkeypatch):
    dest,r,console=_run_mocked(tmp_path,monkeypatch)
    assert r['status']=='OBSERVED_NOT_CERTIFIED' and r['attempted']==3
    assert all(x['status']=='VERIFIED' for x in r['runs'])
    assert r['independent_approval'] is False and r['external_p0_remaining']==16
    assert (dest/'console.log').read_bytes()==console
    assert [x.get('name') for x in ET.parse(dest/'junit.xml').iter('testcase')] == ['repeat_01','repeat_02','repeat_03','aggregate']
    assert m26.verify_output(dest)>5
    assert [x.read_bytes() for x in sorted((dest/'run_stdout').iterdir())]==[b'FAKE local test output\n']*3


@pytest.mark.parametrize('failed', ['CHILD_FAILED','TIMEOUT','SPAWN_FAILED','OVERSIZE_LOG'])
def test_fail_closed_child_status(tmp_path,monkeypatch,failed):
    dest,r,console=_run_mocked(tmp_path,monkeypatch,status=failed)
    assert r['status']=='HOLD_RUN_NOT_VERIFIED' and r['attempted']==1
    assert r['descriptive_summary'] is None
    assert ET.parse(dest/'junit.xml').findall('.//failure')
    assert m26.verify_output(dest) > 0
    assert (dest/'console.log').read_bytes()==console


def test_verify_run_rejection_preserves_run_files(tmp_path,monkeypatch):
    def bad(path):raise ValueError('invalid evidence')
    monkeypatch.setattr(m26.m25,'verify_run',bad)
    dest=tmp_path/'new'
    report=m26.run(dest,child_runner=_fake_factory(),emit_bytes=lambda b:None)
    assert report['status']=='HOLD_RUN_NOT_VERIFIED'
    assert report['runs'][0]['verification_error']=='ValueError'
    assert (dest/'runs'/'01'/'dummy.txt').exists()


def test_incomparable_returns_hold_and_keeps_runs(tmp_path,monkeypatch):
    dest,r,_=_run_mocked(tmp_path,monkeypatch,summary='INCOMPARABLE')
    assert r['status']=='HOLD_INCOMPARABLE_OBSERVATIONS'
    assert r['attempted']==3
    assert ET.parse(dest/'junit.xml').findall('.//failure')


def test_source_change_between_runs_stops_future_runs(tmp_path,monkeypatch):
    original=m26.source_fingerprint()
    n={'value':0}
    def changing():
        n['value']+=1
        return original if n['value']<3 else {'changed':'a'*64}
    monkeypatch.setattr(m26,'source_fingerprint',changing)
    monkeypatch.setattr(m26.m25,'verify_run',lambda path:{})
    report=m26.run(tmp_path/'new',child_runner=_fake_factory(),emit_bytes=lambda b:None)
    assert report['status']=='HOLD_SOURCE_CHANGED'
    assert report['attempted']==1
    assert report['source_unchanged'] is False


def test_internal_exception_written_as_hold(tmp_path,monkeypatch):
    def runner(*args):raise RuntimeError('simulated')
    r=m26.run(tmp_path/'new',child_runner=runner,emit_bytes=lambda b:None)
    assert r['status']=='HOLD_INTERNAL_ERROR'
    assert r['reason']=='RuntimeError'
    assert (tmp_path/'new'/'junit.xml').is_file()
    assert m26.verify_output(tmp_path/'new')>0


def test_keyboard_interrupt_written_as_hold(tmp_path):
    def runner(*args):raise KeyboardInterrupt()
    r=m26.run(tmp_path/'new',child_runner=runner,emit_bytes=lambda b:None)
    assert r['status']=='HOLD_INTERRUPTED'
    assert ET.parse(tmp_path/'new'/'junit.xml').findall('.//failure')


@pytest.mark.parametrize('relative',['console.log','report.json','junit.xml','run_stdout/01.log','runs/01/dummy.txt'])
def test_tampered_file_rejected(tmp_path,monkeypatch,relative):
    dest,_,_=_run_mocked(tmp_path,monkeypatch)
    file=dest/relative
    file.write_bytes(file.read_bytes()+b'EDITED')
    with pytest.raises(ValueError):m26.verify_output(dest)


def test_unregistered_file_rejected(tmp_path,monkeypatch):
    dest,_,_=_run_mocked(tmp_path,monkeypatch)
    (dest/'unregistered.txt').write_text('x')
    with pytest.raises(ValueError):m26.verify_output(dest)


def test_manifest_entry_removed_rejected(tmp_path,monkeypatch):
    dest,_,_=_run_mocked(tmp_path,monkeypatch)
    p=dest/'MANIFEST_SHA256.json'
    m=json.loads(p.read_text()); m['files'].pop()
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError):m26.verify_output(dest)


def test_repeat_output_refuses_clobber(tmp_path,monkeypatch):
    dest,_,_=_run_mocked(tmp_path,monkeypatch)
    with pytest.raises(FileExistsError):m26.run(dest,child_runner=_fake_factory(),emit_bytes=lambda b:None)


def test_bounded_output_rejects_oversize_child(tmp_path):
    def runner(*a):return {'status':'EXECUTED','return_code':0,'stdout':b'x'*(m26.MAX_LOG_BYTES+1),'elapsed_s':0.2}
    r=m26.run(tmp_path/'new',child_runner=runner,emit_bytes=lambda b:None)
    assert r['status']=='HOLD_INTERNAL_ERROR'


def test_real_three_run_local(tmp_path):
    """Real M23 subprocesses, genuine M25 verification and JUnit; no mocks."""
    out=tmp_path/'actual'
    r=m26.run(out,runs=3,clients=1,duration=0.3,max_cycles=20,delay_ms=5,
              timeout=20,emit_bytes=lambda b:None)
    assert r['status']=='OBSERVED_NOT_CERTIFIED',r
    assert r['descriptive_summary']['runs']==3
    assert m26.verify_output(out)>0
    assert all((out/'runs'/f'{i:02}'/'junit.xml').exists() for i in range(1,4))


def test_child_interrupt_reaps_process(tmp_path, monkeypatch):
    """An interrupted parent must kill the process group and descendants."""
    import subprocess
    class InterruptingProcess:
        def __init__(self, *args, **kwargs):
            self.pid=12345
            self.returncode=None
        def communicate(self, timeout=None):
            raise KeyboardInterrupt()
        def poll(self):return None
    monkeypatch.setattr(m26.subprocess,'Popen',InterruptingProcess)
    calls=[]
    monkeypatch.setattr(m26,'kill_process_group',lambda proc:calls.append(proc.pid))
    with pytest.raises(KeyboardInterrupt):
        m26.run_child(tmp_path/'no-create',m26.validate_options())
    assert calls==[12345]
