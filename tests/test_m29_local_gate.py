"""M29 isolated synthetic and actual subprocess safety tests; not Windows attestation."""
import hashlib
import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from scripts import m29_local_gate as m29


@pytest.fixture
def checkout(tmp_path):
    root=tmp_path/'checkout'
    for name in ('scripts','tests','suite/catalog','backlog'):
        (root/name).mkdir(parents=True,exist_ok=True)
    for n in range(1,5):
        (root/'tests'/('test_%02d.py'%n)).write_text(
            'def test_generated_%02d(): assert True\n'%n,encoding='utf-8')
    (root/'scripts'/'core.py').write_text('VALUE=1\n',encoding='utf-8')
    catalog=[{'id':'CASE-0001','phase':'P0'},{'id':'CASE-0002','phase':'P0'}]
    (root/'suite/catalog/test_cases.jsonl').write_text(
        ''.join(json.dumps(row)+'\n' for row in catalog),encoding='utf-8')
    (root/'backlog/M20_BACKLOG.json').write_text(
        json.dumps({'external_dependencies':[{'case_ids':['CASE-0002']}]}),encoding='utf-8')
    return root


def fake_runner(outcome='FINISHED',code=0,skip=False,change=None):
    attempts=[]
    def run(command,root,timeout):
        n=len(attempts)+1
        attempts.append(n)
        if change:
            change(command,root,n)
        xml=Path(next(s.split('=',1)[1] for s in command if s.startswith('--junitxml=')))
        suite=ET.Element('testsuite',tests='1',failures='0',errors='0',skipped='1' if skip else '0')
        case=ET.SubElement(suite,'testcase',classname='fake',name='test_%02d'%n)
        if n==1:
            props=ET.SubElement(case,'properties')
            ET.SubElement(props,'property',name='case_id',value='CASE-0001')
        if skip:
            ET.SubElement(case,'skipped')
        ET.ElementTree(suite).write(xml,encoding='utf-8',xml_declaration=True)
        return outcome,code,b'FAKE_ONLY\n'
    return run,attempts


def test_mocked_pass_and_exact_evidence(checkout,tmp_path):
    runner,calls=fake_runner()
    chunks=[]
    out=tmp_path/'output'
    result=m29.run(checkout,out,groups=2,runner=runner,emit=chunks.append)
    assert result['status']=='LOCAL_REGRESSION_OBSERVED_NOT_CERTIFIED'
    assert result['case_audit']['status']=='MATCHED_EXTERNAL_BACKLOG'
    assert result['case_audit']['observed_pass']==1
    assert len(calls)==2 and len(result['groups'])==2
    assert (out/'console.log').read_bytes()==b''.join(chunks)
    assert m29.verify_output(out)>0
    manifest=json.loads((out/'MANIFEST_SHA256.json').read_text())
    for entry in manifest['files']:
        assert hashlib.sha256((out/entry['path']).read_bytes()).hexdigest()==entry['sha256']


def test_actual_pytest_subprocess_keeps_p0_hold(checkout,tmp_path):
    out=tmp_path/'actual'
    result=m29.run(checkout,out,groups=2,timeout=30,emit=lambda x:None)
    assert result['status']=='HOLD_P0_COVERAGE'
    assert len(result['groups'])==2
    assert sum(entry['counts']['pass'] for entry in result['groups'])==4
    assert m29.verify_output(out)>0
    assert ET.parse(out/'junit.xml').findall('.//failure')


@pytest.mark.parametrize('mode,rc',['TIMEOUT -9'.split(),['FINISHED','1'],['OVERSIZE','-9']])
def test_non_success_child_never_passes(checkout,tmp_path,mode,rc):
    def failed(cmd,root,t):
        return mode,int(rc),b'FAILED\n'
    r=m29.run(checkout,tmp_path/'new',runner=failed,emit=lambda x:None)
    assert r['status']=='HOLD_INCOMPLETE_GROUPS'
    assert r['groups'][0]['status'].startswith('HOLD_')


def test_skip_never_counts_as_pass(checkout,tmp_path):
    runner,calls=fake_runner(skip=True)
    r=m29.run(checkout,tmp_path/'new',runner=runner,emit=lambda x:None)
    assert len(calls)==1
    assert r['status']=='HOLD_INCOMPLETE_GROUPS'
    assert r['groups'][0]['status']=='HOLD_UNPASSED_OR_DUPLICATE'


def test_missing_junit_never_passes(checkout,tmp_path):
    r=m29.run(checkout,tmp_path/'new',runner=lambda cmd,root,t:('FINISHED',0,b'no XML'),
              emit=lambda x:None)
    assert r['status']=='HOLD_INCOMPLETE_GROUPS'


def test_source_drift_holds_and_preserves_artifacts(checkout,tmp_path):
    def change(command,root,n):
        (root/'scripts/core.py').write_text('VALUE=3\n',encoding='utf-8')
    runner,_=fake_runner(change=change)
    out=tmp_path/'new'
    r=m29.run(checkout,out,runner=runner,emit=lambda x:None)
    assert r['status']=='HOLD_SOURCE_DRIFT'
    assert not r['source_unchanged']
    assert m29.verify_output(out)>0


def test_duplicate_case_annotation_rejected():
    root=ET.Element('testsuite',tests='2',failures='0',errors='0',skipped='0')
    for n in range(2):
        case=ET.SubElement(root,'testcase',classname='x',name='test_%d'%n)
        props=ET.SubElement(case,'properties')
        ET.SubElement(props,'property',name='case_id',value='CASE-0001')
    with pytest.raises(ValueError,match='duplicate canonical'):
        m29.parse_junit(ET.tostring(root))


@pytest.mark.parametrize('sample',[
    b'<testsuite/>',b'<none/>',b'bad',
    b'<!DOCTYPE root [<!ENTITY x "z">]><testsuite/>',
    b'<testsuite tests="5" failures="0" errors="0" skipped="0"><testcase classname="c" name="x"/></testsuite>'
])
def test_unsafe_xml_fails(sample):
    with pytest.raises(ValueError):
        m29.parse_junit(sample)


@pytest.mark.parametrize('groups',[None,False,0,13,3.5])
def test_invalid_partition(checkout,groups):
    with pytest.raises(ValueError):
        m29.group_files(m29.find_tests(checkout),groups)


def test_symlink_test_rejected(checkout):
    p=checkout/'tests/test_01.py'
    p.unlink()
    p.symlink_to(checkout/'scripts/core.py')
    with pytest.raises(ValueError):
        m29.find_tests(checkout)


def test_existing_destination_rejected(checkout,tmp_path):
    with pytest.raises(ValueError):
        m29.run(checkout,tmp_path,runner=fake_runner()[0],emit=lambda x:None)


def test_timeout_and_oversize_real_subprocess(checkout):
    result,_,_=m29.execute([sys.executable,'-c','import time;time.sleep(30)'],checkout,0.2)
    assert result=='TIMEOUT'
    result,_,raw=m29.execute([sys.executable,'-c',"print('x'*3000000)"],checkout,10)
    assert result=='OVERSIZE'
    assert len(raw)==m29.MAX_OUTPUT


def test_manifest_tamper_detected(checkout,tmp_path):
    out=tmp_path/'fresh'
    m29.run(checkout,out,groups=2,runner=fake_runner()[0],emit=lambda x:None)
    (out/'report.json').write_text('changed')
    with pytest.raises(ValueError,match='hash'):
        m29.verify_output(out)
