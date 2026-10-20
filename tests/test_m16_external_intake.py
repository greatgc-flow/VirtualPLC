"""M16 synthetic archive mutation suite; ALL fixtures are FAKE and UNATTESTED."""
import hashlib
import json
from pathlib import Path
import stat
import struct
from types import SimpleNamespace
import zipfile
from xml.etree import ElementTree as ET

import pytest
from scripts import m16_provenance_gate as gate
from scripts import m16_windows_one_shot as shot
from scripts.m15_wire_evidence import CLIENT_CASES, write_capture, verify_capture_dir
from scripts.m10_wheel_gate import EXPECTED


def packet(kind, write):
    cmd=0x1401 if write else 0x0401
    sub=0 if kind=='D' else 1
    address,dev,count=(100,0xA8,3) if kind=='D' else (10,0x90,5)
    body=struct.pack('<HH',cmd,sub)+address.to_bytes(3,'little')+bytes([dev])+struct.pack('<H',count)
    if write:
        body+=struct.pack('<3H',0x1995,0x1202,0x1130) if kind=='D' else b'\x10\x10\x10'
    return b'\x50\x00\x00\xff\xff\x03\x00'+struct.pack('<HH',len(body)+2,4)+body


def fake_evidence(tmp_path):
    from scripts.m14_windows_evidence import inspect_client_run, sha256
    folder=tmp_path/'payload'
    root=folder/'client_run'
    root.mkdir(parents=True)
    raw=root/'raw_capture'
    raw.mkdir()
    for case_id,kind in CLIENT_CASES.items():
        write_capture(raw/(case_id+'.json'),case_id,[packet(kind,True),packet(kind,False)])
    raw_meta=verify_capture_dir(raw)
    testsuite=ET.Element('testsuite',tests='6')
    for case_id in sorted(CLIENT_CASES):
        testcase=ET.SubElement(testsuite,'testcase',name=case_id)
        prop=ET.SubElement(testcase,'properties')
        ET.SubElement(prop,'property',name='case_id',value=case_id)
    (root/'pymc_junit.xml').write_bytes(ET.tostring(testsuite,encoding='utf-8',xml_declaration=True))
    (root/'console.log').write_bytes(b'FAKE SYNTHETIC TEST ONLY\n')
    result={'status':'PASS_LOCAL_UNATTESTED','tests_authoritative':False,
            'wheel_sha256':EXPECTED,'stdout_sha256':sha256(root/'console.log'),
            'raw_requests':raw_meta,'windows_runner_observed':True}
    (root/'result.json').write_text(json.dumps(result,sort_keys=True),encoding='utf-8')
    (folder/'runner_stdout.bin').write_bytes(b'FAKE SYNTHETIC TEST ONLY\n')
    client=inspect_client_run(root)
    manifest={'schema':'virtualplc.m14.client-evidence.v1',
              'conclusion':'LOCAL_CLIENT_PASS_INDEPENDENT_ATTESTATION_PENDING',
              'release':'HOLD','p0_new_independently_attested':0,
              'observed_os':'Windows','wheel_sha256':EXPECTED,
              'client':client,'files':{}}
    for p in folder.rglob('*'):
        if p.is_file():
            rel=p.relative_to(folder).as_posix()
            manifest['files'][rel]={'bytes':p.stat().st_size,'sha256':sha256(p)}
    (folder/'M14_EVIDENCE.json').write_text(json.dumps(manifest,sort_keys=True),encoding='utf-8')
    archive=tmp_path/'fake.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(folder).as_posix())
    return archive


def modify_zip(original, dest, transform=None, extra=None):
    with zipfile.ZipFile(original) as z:
        data={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
    if transform:
        transform(data)
    if extra:data.update(extra)
    with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for n,content in data.items():z.writestr(n,content)


def test_synthetic_fixture_self_consistent_but_never_attests(tmp_path):
    result=gate.inspect_archive(fake_evidence(tmp_path))
    assert len(result['case_ids'])==6
    assert result['release']=='HOLD'
    assert result['new_p0_approved']==0
    assert result['independent_windows_attestation'] is False


def test_missing_m14_manifest_fails(tmp_path):
    p=fake_evidence(tmp_path)
    target=tmp_path/'bad.zip'
    modify_zip(p,target,lambda d:d.pop('M14_EVIDENCE.json'))
    with pytest.raises(ValueError,match='manifest missing'):gate.inspect_archive(target)


def test_untracked_file_fails(tmp_path):
    p=fake_evidence(tmp_path)
    target=tmp_path/'bad.zip'
    modify_zip(p,target,extra={'untracked.txt':b'hello'})
    with pytest.raises(ValueError,match='exactly all'):gate.inspect_archive(target)


def test_modified_capture_file_fails(tmp_path):
    p=fake_evidence(tmp_path)
    target=tmp_path/'bad.zip'
    modify_zip(p,target,lambda d:d.__setitem__('client_run/raw_capture/CASE-0027.json',b'{}'))
    with pytest.raises(ValueError,match='SHA-256'):gate.inspect_archive(target)


def test_forged_release_claim_fails(tmp_path):
    p=fake_evidence(tmp_path)
    target=tmp_path/'bad.zip'
    def change(d):
        x=json.loads(d['M14_EVIDENCE.json']);x['release']='APPROVED'
        d['M14_EVIDENCE.json']=json.dumps(x).encode()
    modify_zip(p,target,change)
    with pytest.raises(ValueError,match='independent approval'):gate.inspect_archive(target)


def test_forged_windows_claim_fails(tmp_path):
    p=fake_evidence(tmp_path)
    target=tmp_path/'bad.zip'
    def change(d):
        x=json.loads(d['M14_EVIDENCE.json']);x['observed_os']='Linux'
        d['M14_EVIDENCE.json']=json.dumps(x).encode()
    modify_zip(p,target,change)
    with pytest.raises(ValueError,match='Windows platform'):gate.inspect_archive(target)


@pytest.mark.parametrize('name', ['../escape.txt','/root/escape.txt','client_run\\escape.txt'])
def test_zip_path_escape_fails(tmp_path,name):
    p=fake_evidence(tmp_path)
    target=tmp_path/'bad.zip'
    modify_zip(p,target,extra={name:b'bad'})
    with pytest.raises(ValueError,match='unsafe path'):gate.inspect_archive(target)


def test_duplicate_member_fails(tmp_path):
    p=fake_evidence(tmp_path)
    target=tmp_path/'bad.zip'
    with zipfile.ZipFile(p) as src,zipfile.ZipFile(target,'w') as dest:
        for name in src.namelist():dest.writestr(name,src.read(name))
        dest.writestr('runner_stdout.bin',b'duplicate')
    with pytest.raises(ValueError,match='duplicate entries'):gate.inspect_archive(target)


def test_symlink_member_fails(tmp_path):
    p=fake_evidence(tmp_path)
    target=tmp_path/'bad.zip'
    with zipfile.ZipFile(p) as src,zipfile.ZipFile(target,'w') as dest:
        for name in src.namelist():dest.writestr(name,src.read(name))
        info=zipfile.ZipInfo('link')
        info.external_attr=((stat.S_IFLNK|0o777)<<16)
        dest.writestr(info,b'/etc/passwd')
    with pytest.raises(ValueError,match='nonregular file'):gate.inspect_archive(target)


def test_intake_refuses_overwrite(tmp_path):
    p=fake_evidence(tmp_path)
    out=tmp_path/'report.json'
    assert gate.main(['--zip',str(p),'--result',str(out)])==0
    original=out.read_bytes()
    assert gate.main(['--zip',str(p),'--result',str(out)])==2
    assert out.read_bytes()==original


def test_linux_one_shot_does_not_touch_output(tmp_path):
    with pytest.raises(ValueError,match='Windows execution required'):
        shot.run(wheel='AUTO',output=tmp_path/'anything',expected_head='a'*40,os_name='Linux')
    assert not (tmp_path/'anything').exists()


def test_invalid_git_head_rejected_before_output(tmp_path):
    with pytest.raises(ValueError,match='expected-head'):
        shot.run(wheel='AUTO',output=tmp_path/'anything',expected_head='wrong',os_name='Windows')
    assert not (tmp_path/'anything').exists()


def test_existing_directory_does_not_download(tmp_path):
    output=tmp_path/'exists';output.mkdir()
    with pytest.raises(ValueError,match='refusing overwrite'):
        shot.run(wheel='AUTO',output=output,expected_head='a'*40,os_name='Windows')


def test_auto_download_validates_pinned_wheel_before_execution(tmp_path,monkeypatch):
    calls=[]
    def simulate_pip(cmd):
        calls.append(cmd)
        Path(cmd[cmd.index('--dest')+1],'pymcprotocol-0.3.0-py3-none-any.whl').write_bytes(b'fake wheel')
        return SimpleNamespace(returncode=0,stdout=b'FAKE PIP TEST\n')
    def reject(fake):
        raise ValueError('wheel SHA-256 mismatch')
    monkeypatch.setattr(shot,'verify_wheel',reject)
    out=tmp_path/'auto'
    with pytest.raises(ValueError,match='wheel SHA-256 mismatch'):
        shot.run(wheel='AUTO',output=out,expected_head='a'*40,os_name='Windows',invoke=simulate_pip)
    assert len(calls)==1
    assert '--no-deps' in calls[0]
    assert '--only-binary=:all:' in calls[0]
    assert '--index-url' in calls[0]
    assert (out/'wheel_download_stdout.bin').read_bytes()==b'FAKE PIP TEST\n'


def test_auto_download_failure_keeps_stdout_and_fails(tmp_path):
    out=tmp_path/'auto'
    with pytest.raises(ValueError,match='download failed'):
        shot.run(wheel='AUTO',output=out,expected_head='a'*40,os_name='Windows',
                 invoke=lambda cmd:SimpleNamespace(returncode=1,stdout=b'FAKE FAILURE'))
    assert (out/'wheel_download_stdout.bin').read_bytes()==b'FAKE FAILURE'


def test_oneshot_success_is_not_release_and_stdout_is_reconstructible(tmp_path,monkeypatch):
    output=tmp_path/'evidence'
    monkeypatch.setattr(shot,'verify_wheel',lambda p:{'wheel_sha256':EXPECTED})
    def simulate_package(wheel, folder, expected_head, **opts):
        folder.mkdir()
        (folder/'runner_stdout.bin').write_bytes(b'SYNTHETIC RUNNER\n')
        return {'wheel_sha256':EXPECTED}
    monkeypatch.setattr(shot,'package_run',simulate_package)
    result=shot.run(wheel=tmp_path/'pinned.whl',output=output,expected_head='a'*40,os_name='Windows')
    assert result['release']=='HOLD'
    assert result['approved_new_p0']==0
    assert (output/'M16_CONSOLE.bin').read_bytes()==(
        b'SYNTHETIC RUNNER\nM16_WINDOWS=LOCAL_CLIENT_RUN_INDEPENDENT_ATTESTATION_REQUIRED\n')


def test_oneshot_refuses_to_write_inside_repository(tmp_path):
    from scripts.m14_windows_evidence import ROOT
    candidate=ROOT/'do_not_create_m16_test_evidence'
    assert not candidate.exists()
    with pytest.raises(ValueError,match='outside the public'):
        shot.run(wheel='AUTO',output=candidate,expected_head='a'*40,os_name='Windows')
    assert not candidate.exists()


def test_synthetic_fixture_print_matches_evidence_file(tmp_path,capsysbinary):
    p=fake_evidence(tmp_path)
    out=tmp_path/'record.json'
    assert gate.main(['--zip',str(p),'--result',str(out)])==0
    stdout=capsysbinary.readouterr().out
    assert stdout==out.read_bytes()


def test_oneshot_download_failure_console_reconstructed(tmp_path,monkeypatch,capsysbinary):
    monkeypatch.setattr(shot.platform,'system',lambda:'Windows')
    def broken_pip(cmd):
        return SimpleNamespace(returncode=23,stdout=b'FAKE ERROR OUTPUT\n')
    # main() uses the real subprocess runner; replace only the run dependency
    # with an injected call, never touch public internet during tests.
    original=shot.run
    monkeypatch.setattr(shot,'run',lambda **kwargs:original(**kwargs,invoke=broken_pip))
    out=tmp_path/'download-error'
    rc=shot.main(['--wheel','AUTO','--output',str(out),'--expected-head','a'*40])
    assert rc==2
    assert capsysbinary.readouterr().out == (out/'M16_CONSOLE.bin').read_bytes()
    assert b'M16_WINDOWS=HOLD:' in (out/'M16_CONSOLE.bin').read_bytes()
