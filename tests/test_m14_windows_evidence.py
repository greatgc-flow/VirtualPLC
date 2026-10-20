"""M14 fail-closed evidence-contract tests; NOT actual pymcprotocol execution."""
import hashlib
import json
import subprocess
import types
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
import pytest
from scripts import m14_windows_evidence as m14
from scripts.m13_evidence_gate import CLIENT_IDS
from scripts.m15_wire_evidence import write_capture, verify_capture_dir
import struct

PIN = '614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6'


def fake_client_run(folder, status='PASS_LOCAL_UNATTESTED', broken=None):
    folder.mkdir(parents=True)
    log = b'actual runner test console\n'
    (folder/'console.log').write_bytes(log)
    report = {'status': status, 'tests_authoritative': False,
              'wheel_sha256': PIN, 'windows_runner_observed': True,
              'stdout_sha256': hashlib.sha256(log).hexdigest()}
    if broken == 'console':report['stdout_sha256'] = '0' * 64
    if broken == 'wheel':report['wheel_sha256'] = '0' * 64
    if broken == 'claims_approval':report['tests_authoritative'] = True
    root = Element('testsuite')
    ids=sorted(CLIENT_IDS)
    if broken == 'missing_case': ids.pop()
    for case_id in ids:
        case = SubElement(root,'testcase',name='test_client')
        props=SubElement(case,'properties')
        SubElement(props,'property',name='case_id',value=case_id)
        if broken == 'skipped' and case_id == ids[0]: SubElement(case,'skipped')
    (folder/'pymc_junit.xml').write_bytes(tostring(root))
    cap=folder/'raw_capture';cap.mkdir()
    for cid in sorted(CLIENT_IDS):
        is_d=cid in ('CASE-0027','CASE-0029','CASE-0109')
        dev,addr,sub,n=(0xA8,100,0,3) if is_d else (0x90,10,1,5)
        wire_payload=(struct.pack('<3H',0x1995,0x1202,0x1130) if is_d else b'\x10\x10\x10')
        def frame(cmd,payload):
            body=(struct.pack('<HHH',16,cmd,sub)+addr.to_bytes(3,'little')
                +bytes([dev])+struct.pack('<H',n)+payload)
            return b'\x50\x00'+bytes.fromhex('00 ff ff 03 00')+struct.pack('<H',len(body))+body
        write_capture(cap/(cid+'.json'),cid,[frame(0x1401,wire_payload),frame(0x0401,b'')])
    report['raw_requests']=verify_capture_dir(cap)
    (folder/'result.json').write_text(json.dumps(report))
    return folder


def test_shaped_local_run_remains_unattested(tmp_path):
    outcome=m14.inspect_client_run(fake_client_run(tmp_path/'s'))
    assert len(outcome['client_case_ids']) == 6
    assert not outcome['independent_windows_attestation']


@pytest.mark.parametrize('problem', [
    'console','wheel','claims_approval','missing_case','skipped',
    'failed_status', 'missing_junit','missing_report', 'missing_console'])
def test_bad_client_evidence_fails_closed(tmp_path, problem):
    folder=fake_client_run(tmp_path/'s',
        status='NOT_RUN' if problem=='failed_status' else 'PASS_LOCAL_UNATTESTED',
        broken=problem)
    if problem.startswith('missing_') and problem in ('missing_junit','missing_report','missing_console'):
        (folder / problem.replace('missing_', '').replace('junit','pymc_junit.xml').replace('report','result.json').replace('console','console.log')).unlink()
    with pytest.raises((OSError,ValueError)):
        m14.inspect_client_run(folder)


@pytest.mark.parametrize('claimed', ['', 'f'*39, 'A'*40, 'z'*40])
def test_invalid_expected_head(claimed, tmp_path):
    with pytest.raises(ValueError):m14.local_git_provenance(tmp_path,claimed)


def test_head_mismatch_or_dirty_checkout(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess,'run',lambda *a,**kw: types.SimpleNamespace(stdout='a'*40+'\n'))
    with pytest.raises(ValueError,match='does not equal'):
        m14.local_git_provenance(tmp_path,'b'*40)
    n=[0]
    def mock_run(*args,**kwargs):
        n[0]+=1
        return types.SimpleNamespace(stdout='a'*40+'\n' if n[0]==1 else ' M fake.txt\n')
    monkeypatch.setattr(subprocess,'run',mock_run)
    with pytest.raises(ValueError,match='dirty'):
        m14.local_git_provenance(tmp_path,'a'*40)


def test_windows_guard_precedes_wheel_and_output(tmp_path):
    if m14.platform.system() == 'Windows':pytest.skip('Linux-only negative guard test')
    output=tmp_path/'run'
    with pytest.raises(ValueError,match='Windows'):
        m14.package_run(tmp_path/'missing.whl',output,'a'*40)
    assert not output.exists()


def test_existing_output_rejected(monkeypatch,tmp_path):
    monkeypatch.setattr(m14.platform,'system',lambda:'Windows')
    output=tmp_path/'run';output.mkdir()
    with pytest.raises(ValueError,match='exists'):
        m14.package_run(tmp_path/'missing.whl',output,'a'*40)


def test_public_repo_output_refused(monkeypatch,tmp_path):
    monkeypatch.setattr(m14.platform,'system',lambda:'Windows')
    monkeypatch.setattr(m14,'verify_wheel',lambda p:{'wheel_sha256':PIN})
    with pytest.raises(ValueError,match='OUTSIDE'):
        m14.package_run(tmp_path/'fake.whl',m14.ROOT/'_forbidden_evidence','a'*40)


def test_cannot_forge_signed_release_from_junit(tmp_path):
    o=m14.inspect_client_run(fake_client_run(tmp_path/'s'))
    assert o['client_state']=='SIX_LOCAL_RESULTS_INTACT_NOT_ATTESTED'
    assert o['independent_windows_attestation'] is False
