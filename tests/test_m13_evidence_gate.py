"""M13 oracle-inversion and tamper-detection tests, deliberately no CASE-ID promotions."""
from __future__ import annotations
import json
import hashlib
import zipfile
import pytest
from xml.etree.ElementTree import Element, SubElement, tostring
from scripts.m13_evidence_gate import (verify_wheel, verify_client_junit,
    verify_m12_archive, inspect, CLIENT_IDS, WHEEL_NAME)


def fake_junit(ids, failed=None, skipped=None, duplicate=None):
    root=Element('testsuite',{'tests':str(len(ids))})
    for i,cid in enumerate(ids):
        case=SubElement(root,'testcase',{'name':'test_external','classname':'test_client'})
        props=SubElement(case,'properties')
        SubElement(props,'property',{'name':'case_id','value':cid})
        if failed==i:
            SubElement(case,'failure')
        if skipped==i:
            SubElement(case,'skipped')
        if duplicate is not None and duplicate==i:
            SubElement(props,'property',{'name':'case_id','value':cid})
    return tostring(root)


def make_zip(path, *, replace_payload=False, add_untracked=False, duplicate=False, no_manifest=False):
    payload=b'safe fixture'
    entry={'path':'example.dat','bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
    manifest={'entries':[entry]}
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('example.dat',b'modified fixture' if replace_payload else payload)
        if duplicate:
            z.writestr('example.dat',payload)
        if add_untracked:
            z.writestr('untracked.dat',b'x')
        if not no_manifest:
            z.writestr('FILE_SHA256_MANIFEST.json',json.dumps(manifest))


def test_baseline_gate_stays_hold():
    result=inspect()
    assert result['decision']=='HOLD'
    assert result['new_authoritatively_attested_p0']==0
    assert len(result['external_case_ids'])==16
    assert result['independent_release_approval'] is False

@pytest.mark.parametrize('missing', ['wheel','client'])
def test_incomplete_client_evidence_pair_rejected(missing,tmp_path):
    with pytest.raises(ValueError,match='together'):
        if missing=='wheel':inspect(client_junit=tmp_path/'c.xml')
        else:inspect(wheel=tmp_path/WHEEL_NAME)

@pytest.mark.parametrize('bad', ['uppercase','short','not_hex'])
def test_forged_head_cannot_be_supplied(bad):
    value={'uppercase':'A'*40,'short':'a'*39,'not_hex':'z'*40}[bad]
    with pytest.raises(ValueError,match='source HEAD'):
        inspect(claimed_head=value)

@pytest.mark.parametrize('kind', ['missing','badname','forgedbytes'])
def test_pypi_wheel_fails_closed(kind,tmp_path):
    wheel=tmp_path/(WHEEL_NAME if kind!='badname' else 'other.whl')
    if kind!='missing':wheel.write_bytes(b'faked package')
    with pytest.raises(ValueError):verify_wheel(wheel)

@pytest.mark.parametrize('fault', ['failure','skip','duplicate','missing','foreign','dup_property','empty'])
def test_six_client_case_coverage_cannot_be_forged_by_junit_shape(fault,tmp_path):
    ids=sorted(CLIENT_IDS)
    if fault=='missing':ids=ids[:-1]
    if fault=='foreign':ids[-1]='CASE-9999'
    if fault=='duplicate':ids[-1]=ids[0]
    if fault=='empty':ids=[]
    raw=fake_junit(ids,failed=0 if fault=='failure' else None,
                   skipped=0 if fault=='skip' else None,
                   duplicate=0 if fault=='dup_property' else None)
    path=tmp_path/'cases.xml';path.write_bytes(raw)
    with pytest.raises(ValueError):verify_client_junit(path)


def test_six_shaped_local_client_results_are_only_unattested(tmp_path):
    p=tmp_path/'suite.xml';p.write_bytes(fake_junit(sorted(CLIENT_IDS)))
    result=verify_client_junit(p)
    assert result['state']=='SIX_LOCAL_TEST_RESULTS_PRESENT_UNATTESTED'

@pytest.mark.parametrize('fault', ['bad_sha','extra','duplicate','missing_manifest'])
def test_archive_integrity_mutations_fail(fault,tmp_path):
    p=tmp_path/'bundle.zip'
    make_zip(p,replace_payload=fault=='bad_sha',add_untracked=fault=='extra',
             duplicate=fault=='duplicate',no_manifest=fault=='missing_manifest')
    with pytest.raises(ValueError):verify_m12_archive(p)


def test_synthetic_archive_integrity_only(tmp_path):
    p=tmp_path/'bundle.zip';make_zip(p)
    outcome=verify_m12_archive(p)
    assert outcome['files_verified']==1
    assert outcome['state']=='INTEGRITY_ONLY_NOT_AUTHENTICITY'


def test_output_already_exists_never_overwrites(tmp_path):
    from scripts.m13_evidence_gate import run
    target=tmp_path/'evidence';target.mkdir();marker=target/'original';marker.write_text('keep')
    assert run(['--out-dir',str(target)])==2
    assert marker.read_text()=='keep'


def test_untrusted_wheel_creates_no_artifacts(tmp_path):
    from scripts.m13_evidence_gate import run
    wheel=tmp_path/WHEEL_NAME;wheel.write_bytes(b'evil')
    junit=tmp_path/'fake.xml';junit.write_bytes(fake_junit(sorted(CLIENT_IDS)))
    out=tmp_path/'output'
    assert run(['--wheel',str(wheel),'--client-junit',str(junit),'--out-dir',str(out)])==2
    assert not out.exists()


def test_stdout_identical_to_output_files(tmp_path, capsysbinary):
    from scripts.m13_evidence_gate import run
    out=tmp_path/'check'
    assert run(['--out-dir',str(out)])==2 # external gates still HOLD
    observed=capsysbinary.readouterr().out
    assert observed== (out/'result.json').read_bytes() == (out/'console.txt').read_bytes()
