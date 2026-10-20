"""M17 preflight fail-closed TDD; all Windows and Git states are synthetic."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import pytest
from scripts import m17_preflight as p

HEAD='a'*40


def pretend_git(root, *, head=HEAD, dirty='', origin='https://github.com/greatgc-flow/VirtualPLC.git',top=None):
    def run(cmd,**kwargs):
        key=' '.join(cmd[3:])
        outputs={'rev-parse --show-toplevel':str(top or root), 'rev-parse HEAD':head,
                 'status --porcelain --untracked-files=normal':dirty,
                 'remote get-url origin':origin}
        return SimpleNamespace(returncode=0,stdout=outputs[key]+'\n',stderr='')
    return run


def ready(tmp_path, **kw):
    root=tmp_path/'clone';root.mkdir(exist_ok=True)
    default=dict(wheel='AUTO',output=tmp_path/'new-output',report=tmp_path/'preflight.json',
                 expected_head=HEAD, os_name='Windows',version_info=(3,12),
                 package_version=lambda n:'9.0.2',root=root,
                 git_runner=pretend_git(root))
    default.update(kw)
    return p.preflight(**default)


def test_ready_is_not_test_success_or_approval(tmp_path):
    state=ready(tmp_path)
    assert state['status']=='READY_FOR_LOCAL_TEST_COLLECTION_ONLY'
    assert state['new_p0_approved']==0 and state['release']=='HOLD'
    assert state['actual_client_tests_ran'] is False
    assert state['wheel_verified'] is False
    assert state['provenance']['independently_attested'] is False

@pytest.mark.parametrize('name', ['Linux','Darwin','FreeBSD'])
def test_non_windows_rejected(tmp_path,name):
    with pytest.raises(ValueError,match='Windows required'):ready(tmp_path,os_name=name)

@pytest.mark.parametrize('version', [(3,9),(3,10)])
def test_old_python_rejected(tmp_path,version):
    with pytest.raises(ValueError,match='Python 3.11'):ready(tmp_path,version_info=version)

@pytest.mark.parametrize('version', ['7.4.0','10.0.0','malformed'])
def test_unsupported_pytest_rejected(tmp_path,version):
    with pytest.raises(ValueError,match='pytest 8.x/9.x'):ready(tmp_path,package_version=lambda n:version)


def test_missing_pytest_rejected(tmp_path):
    import importlib.metadata
    def missing(n):raise importlib.metadata.PackageNotFoundError('pytest')
    with pytest.raises(ValueError,match='not installed'):ready(tmp_path,package_version=missing)


def test_bad_git_head_rejected(tmp_path):
    with pytest.raises(ValueError,match='expected-head'):ready(tmp_path,expected_head='123')


def test_mismatched_git_head_rejected(tmp_path):
    root=tmp_path/'clone';root.mkdir()
    with pytest.raises(ValueError,match='HEAD differs'):
        ready(tmp_path, git_runner=pretend_git(root,head='b'*40))


def test_dirty_git_rejected(tmp_path):
    root=tmp_path/'clone';root.mkdir()
    with pytest.raises(ValueError,match='changes'):
        ready(tmp_path, git_runner=pretend_git(root,dirty='?? unknown-file'))


def test_wrong_origin_rejected(tmp_path):
    root=tmp_path/'clone';root.mkdir()
    with pytest.raises(ValueError,match='origin'):
        ready(tmp_path,git_runner=pretend_git(root,origin='https://github.com/evil/VirtualPLC.git'))


def test_wrong_git_root_rejected(tmp_path):
    root=tmp_path/'clone';root.mkdir()
    with pytest.raises(ValueError,match='repository root'):
        ready(tmp_path,git_runner=pretend_git(root,top=tmp_path))


def test_accepts_known_ssh_origin(tmp_path):
    root=tmp_path/'clone';root.mkdir()
    result=ready(tmp_path,git_runner=pretend_git(root,origin='git@github.com:greatgc-flow/VirtualPLC.git'))
    assert result['provenance']['origin_repo']=='greatgc-flow/VirtualPLC'


def test_existing_output_rejected(tmp_path):
    (tmp_path/'new-output').mkdir()
    with pytest.raises(ValueError,match='already exists'):ready(tmp_path)


def test_existing_report_rejected(tmp_path):
    (tmp_path/'preflight.json').write_text('OLD')
    with pytest.raises(ValueError,match='already exists'):ready(tmp_path)


def test_report_inside_new_output_rejected(tmp_path):
    with pytest.raises(ValueError,match='outside the pending'):
        ready(tmp_path,report=tmp_path/'new-output'/'report.json')


def test_output_inside_checkout_rejected(tmp_path):
    with pytest.raises(ValueError,match='inside source checkout'):
        ready(tmp_path,output=tmp_path/'clone'/'output')


def test_report_inside_checkout_rejected(tmp_path):
    with pytest.raises(ValueError,match='inside public checkout'):
        ready(tmp_path,report=tmp_path/'clone'/'report')


def test_incorrect_offline_wheel_rejected_before_git(tmp_path):
    wheel=tmp_path/'pymcprotocol-0.3.0-py3-none-any.whl'
    wheel.write_bytes(b'FAKE')
    with pytest.raises(ValueError,match='wheel SHA-256 mismatch'):
        ready(tmp_path,wheel=wheel)


def test_origin_normalization():
    assert p.normalize_origin('https://github.com/greatgc-flow/VirtualPLC.git/') in p._ORIGINS


def test_main_linux_hold_console_same_bytes_as_report(tmp_path,monkeypatch,capsysbinary):
    monkeypatch.setattr(p.platform,'system',lambda:'Linux')
    report=tmp_path/'a.json'
    rc=p.main(['--wheel','AUTO','--output',str(tmp_path/'out'),
               '--expected-head',HEAD,'--report',str(report)])
    assert rc==2
    assert capsysbinary.readouterr().out==report.read_bytes()
    state=json.loads(report.read_text())
    assert state['status']=='HOLD' and state['new_p0_approved']==0


def test_main_report_cannot_be_overwritten(tmp_path,monkeypatch,capsysbinary):
    monkeypatch.setattr(p.platform,'system',lambda:'Linux')
    report=tmp_path/'a.json';report.write_bytes(b'IMMUTABLE')
    rc=p.main(['--wheel','AUTO','--output',str(tmp_path/'out'),
               '--expected-head',HEAD,'--report',str(report)])
    assert rc==2 and report.read_bytes()==b'IMMUTABLE'


def test_main_fail_never_writes_report_inside_checkout(tmp_path,monkeypatch,capsysbinary):
    from scripts.m14_windows_evidence import ROOT
    monkeypatch.setattr(p.platform,'system',lambda:'Linux')
    target=ROOT/'DO_NOT_WRITE_FAILED_PREFLIGHT.json'
    assert not target.exists()
    rc=p.main(['--wheel','AUTO','--output',str(tmp_path/'out'),
               '--expected-head',HEAD,'--report',str(target)])
    assert rc==2
    assert not target.exists()
    assert b'"status": "HOLD"' in capsysbinary.readouterr().out
