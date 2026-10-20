"""M21 local runner: unit + real-process evidence and adversarial cases.

These are INTERNAL tests, not proof of external P0 compatibility.
"""
from __future__ import annotations
import io
import json
import os
from pathlib import Path
import shutil
import sys
import textwrap
import xml.etree.ElementTree as ET

import pytest
from scripts import m21_local_evidence as m21


@pytest.fixture(scope='module')
def good_run(tmp_path_factory):
    path=tmp_path_factory.mktemp('m21')/'fresh'
    output=io.BytesIO()
    result=m21.run(path,mode='smoke',timeout_seconds=40,console=output)
    assert result['test_status']=='PASS'
    assert output.getvalue()==(path/'console.log').read_bytes()
    return path


def mutated(good_run,tmp_path):
    output=tmp_path/'copied'
    shutil.copytree(good_run,output)
    return output


def test_real_smoke_success_junit_capture(good_run):
    result=json.loads((good_run/'result.json').read_text())
    assert result['junit']['tests']>0 and result['junit']['skipped']==0
    assert m21.verify(good_run)['integrity']=='PASS'
    assert 'M21_LOCAL_TEST=PASS' in (good_run/'console.log').read_text()
    assert result['release']=='HOLD' and result['new_external_p0_approved']==0


def test_no_overwrite(good_run):
    with pytest.raises(ValueError,match='exists'):
        m21.run(good_run)
    assert m21.verify(good_run)['integrity']=='PASS'


@pytest.mark.parametrize('invalid', ['',None, 'some/relative', ' ', '.', 'subdir'])
def test_reject_missing_relative_and_null_output(invalid):
    with pytest.raises(ValueError):
        m21.safe_output(invalid)


def test_reject_output_under_checkout(tmp_path):
    with pytest.raises(ValueError,match='source checkout'):
        m21.safe_output(m21.ROOT/'subdir'/'private')


def test_reject_symlink_output(tmp_path):
    target=tmp_path/'existing'
    target.mkdir()
    link=tmp_path/'link'
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip('symlink not allowed on this platform')
    with pytest.raises(ValueError):
        m21.safe_output(link)


@pytest.mark.parametrize('seconds',[None, True, False, 0, -1, 1801, 1.1, '60'])
def test_timeout_invalid(seconds,tmp_path):
    with pytest.raises(ValueError, match='timeout-seconds'):
        m21.run(tmp_path/'fresh', timeout_seconds=seconds)


def test_unknown_mode(tmp_path):
    with pytest.raises(ValueError,match='suite'):
        m21.run(tmp_path/'fresh',mode='arbitrary command')


def test_tee_byte_match_with_limit():
    dst=io.BytesIO(); screen=io.BytesIO(); t=m21.Tee(dst,screen,maximum=3)
    t.write(b'\x00\xf0');t.write(b'\xff!')
    assert dst.getvalue()==screen.getvalue()==b'\x00\xf0\xff'
    assert t.overflow


@pytest.mark.parametrize(('body','problem'),[
    (b'<root/>','root'),
    (b'<testsuite/>','no test'),
    (b'<testsuite><testcase classname="x" name="a"><skipped/></testcase></testsuite>',None),
    (b'<testsuite><testcase classname="x" name="a"/><testcase classname="x" name="a"/></testsuite>','duplicate'),
    (b'<testsuite><testcase classname="x" /></testsuite>','duplicate'),
])
def test_junit_edge_cases(tmp_path,body,problem):
    path=tmp_path/'test.xml';path.write_bytes(body)
    if problem:
        with pytest.raises(ValueError,match=problem):m21.summarize_junit(path)
    else:
        assert m21.summarize_junit(path)['skipped']==1


def test_failed_junit_never_marked_passing(tmp_path):
    p=tmp_path/'pytest.xml';p.write_text('<testsuite><testcase classname="x" name="a"><failure/></testcase></testsuite>')
    assert m21.summarize_junit(p)['failures']==1


def test_verify_reject_missing_payload(good_run,tmp_path):
    dest=mutated(good_run,tmp_path)
    (dest/'console.log').unlink()
    with pytest.raises(ValueError):m21.verify(dest)


def test_verify_reject_appended_stdout(good_run,tmp_path):
    dest=mutated(good_run,tmp_path)
    with (dest/'console.log').open('ab') as f:f.write(b'altered')
    with pytest.raises(ValueError,match='changed'):m21.verify(dest)


def test_verify_reject_junit_change(good_run,tmp_path):
    dest=mutated(good_run,tmp_path)
    with (dest/'pytest.xml').open('ab') as f:f.write(b'<!-- tamper -->')
    with pytest.raises(ValueError,match='changed'):m21.verify(dest)


def test_verify_reject_unregistered_artifact(good_run,tmp_path):
    dest=mutated(good_run,tmp_path)
    (dest/'secret.txt').write_text('sensitive')
    with pytest.raises(ValueError,match='unregistered'):m21.verify(dest)


def test_verify_reject_forged_approval(good_run,tmp_path):
    dest=mutated(good_run,tmp_path)
    obj=json.loads((dest/'result.json').read_text())
    obj['new_external_p0_approved']=6
    (dest/'result.json').write_bytes(m21.json_bytes(obj))
    manifest=json.loads((dest/'manifest.json').read_text())
    blob=(dest/'result.json').read_bytes()
    manifest['payload']['result.json']={'bytes':len(blob),'sha256':m21.digest(blob)}
    (dest/'manifest.json').write_bytes(m21.json_bytes(manifest))
    with pytest.raises(ValueError,match='release/attestation'):m21.verify(dest)


def test_verify_reject_manifest_omission(good_run,tmp_path):
    dest=mutated(good_run,tmp_path)
    m=json.loads((dest/'manifest.json').read_text())
    del m['payload']['console.log']
    (dest/'manifest.json').write_bytes(m21.json_bytes(m))
    with pytest.raises(ValueError,match='mismatch'):m21.verify(dest)


def test_verify_reject_non_file(good_run,tmp_path):
    dest=mutated(good_run,tmp_path)
    (dest/'nested').mkdir()
    with pytest.raises(ValueError,match='unsafe'):m21.verify(dest)


def test_verify_reject_symlink(good_run,tmp_path):
    dest=mutated(good_run,tmp_path)
    (dest/'console.log').unlink()
    try:
        (dest/'console.log').symlink_to(good_run/'console.log')
    except OSError:
        pytest.skip('symlink not supported')
    with pytest.raises(ValueError,match='unsafe'):m21.verify(dest)


def test_verify_reject_truncated_manifest(good_run,tmp_path):
    dest=mutated(good_run,tmp_path)
    (dest/'manifest.json').write_text('[]')
    with pytest.raises((AttributeError,ValueError,TypeError)):
        m21.verify(dest)


def test_no_junit_fails_closed(tmp_path):
    # Run a child that exits successfully but deliberately does not run pytest.
    # The CLI cannot select an arbitrary executable; this injection is unit-only.
    script=tmp_path/'fake_exe'
    if os.name=='nt':
        pytest.skip('test uses a POSIX executable script fixture')
    script.write_text('#!'+sys.executable+'\nprint("no junit despite exit 0")\n')
    script.chmod(0o755)
    result=m21.run(tmp_path/'capture',executable=script,console=io.BytesIO())
    assert result['test_status']=='HOLD' and result['runner_error']
    assert m21.verify(tmp_path/'capture')['test_status']=='HOLD'


def test_timeout_kills_child_and_seals_hold(tmp_path,monkeypatch):
    root=tmp_path/'repo';tests=root/'tests';tests.mkdir(parents=True)
    (tests/'test_slow.py').write_text('import time\ndef test_sleep():\n    time.sleep(4)\n')
    monkeypatch.setitem(m21.SUITES,'smoke',('tests/test_slow.py',))
    monkeypatch.setattr(m21,'SOURCE_FILES',())
    r=m21.run(tmp_path/'timed',root=root,timeout_seconds=1,console=io.BytesIO())
    assert r['timeout'] is True and r['test_status']=='HOLD'
    assert m21.verify(tmp_path/'timed')['test_status']=='HOLD'


def test_not_a_release_claim(good_run):
    r=m21.verify(good_run)
    assert r['release']=='HOLD' and r['external_p0_attested']==0
