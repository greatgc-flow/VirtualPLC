"""M27 synthetic/mocked TDD; never hardware or signed-origin evidence."""
import hashlib
import json
import xml.etree.ElementTree as ET

import pytest

from scripts import m23_recovery_soak as m23
from scripts import m25_replicates as m25
from scripts import m26_multi_run as m26
from scripts import m27_compare as m27


@pytest.fixture
def evidence(tmp_path,monkeypatch):
    sha=m26.source_fingerprint()
    deviations={}
    def verify(path):
        number=int(path.name)
        n=number*10
        return {'report':{
            'platform':deviations.get(number,'TEST_ONLY'),
            'python_version':'3.11.mock',
            'source_sha256':{k:sha[k] for k in m23.SOURCE_FILES},
            'fault_recovery':{'delay_requested_ms':20,
                              'verified_readback':True,'reconnects_successful':1},
            'duration_soak':{'clients':2,'duration_requested_seconds':0.5,
                             'max_cycles':30,'p50_us':n,'p95_us':n+10,'p99_us':n+20,
                             'rss_initial_kib':100,'rss_final_kib':100+number*5,
                             'rss_slope_kib_per_minute':0.0,'requests_ok':12}}}
    monkeypatch.setattr(m25,'verify_run',verify)
    def summary(paths):
        return {'status':'INCOMPARABLE' if deviations else 'REPEATED_OBSERVATIONS_ONLY',
                'issues':['environment_mismatch'] if deviations else []}
    monkeypatch.setattr(m25,'analyze',summary)
    def child(target,options):
        target.mkdir()
        (target/'synthetic.txt').write_text(target.name)
        return {'status':'EXECUTED','return_code':0,'elapsed_s':0.01,
                'stdout':b'TEST_ONLY\n'}
    root=tmp_path/'m26'
    result=m26.run(root,child_runner=child,emit_bytes=lambda raw:None)
    assert result['status']=='OBSERVED_NOT_CERTIFIED'
    assert m26.verify_output(root)
    return root,deviations


def test_success_is_comparable_but_not_certified(evidence):
    root,_=evidence
    result=m27.analyze(root)
    assert result['status']=='COMPARABLE_DESCRIPTIVE'
    assert result['release']=='HOLD' and result['independent_approval'] is False
    assert result['external_p0_hold']==16
    assert result['statistics']['p95_us']['median']==30
    assert result['statistics']['p95_us']['median_absolute_deviation']==10
    assert result['no_default_thresholds'] is True
    assert len(result['runs'])==3


def test_opt_in_anomalies_are_not_an_sla(evidence):
    root,_=evidence
    x=m27.analyze(root,{'p95_growth_percent':20,'rss_growth_kib':2})
    assert x['status']=='OPTIONAL_THRESHOLD_EXCEEDED'
    assert x['threshold_exceedances']
    assert x['release']=='HOLD'
    assert any('OPTIONAL_THRESHOLD_' in t for row in x['runs'] for t in row['anomalies'])


@pytest.mark.parametrize('bad',[{}, {'unknown':1},
                               {'p95_growth_percent':-1},
                               {'p99_growth_percent':float('nan')},
                               {'rss_growth_kib':True}, [], 1])
def test_bad_thresholds(evidence,bad):
    with pytest.raises(ValueError):
        m27.analyze(evidence[0],bad)


def test_environment_mismatch_never_threshold_checks(evidence):
    root,deviations=evidence
    deviations[3]='DIFFERENT_PLATFORM'
    x=m27.analyze(root,{'p95_growth_percent':0})
    assert x['status']=='INCOMPARABLE'
    assert 'platform' in x['mismatch_reasons']
    assert x['statistics']=={} and x['threshold_exceedances']==[]


def test_mutated_file_rejected(evidence):
    root,_=evidence
    (root/'run_stdout'/'02.log').write_bytes(b'altered')
    with pytest.raises(ValueError):
        m27.analyze(root)


def test_unregistered_file_rejected(evidence):
    root,_=evidence
    (root/'unexpected').write_text('extra')
    with pytest.raises(ValueError):
        m27.analyze(root)


def test_missing_file_rejected(evidence):
    root,_=evidence
    (root/'runs'/'02'/'synthetic.txt').unlink()
    with pytest.raises(ValueError):
        m27.analyze(root)


def test_symlink_root_and_member_rejected(evidence,tmp_path):
    root,_=evidence
    link=tmp_path/'alias'
    link.symlink_to(root,target_is_directory=True)
    with pytest.raises(ValueError,match='symlink'):
        m27.analyze(link)
    (root/'unknown').symlink_to(root/'console.log')
    with pytest.raises(ValueError,match='symlink'):
        m27.analyze(root)


def test_forged_success_rejected_even_if_manifest_rehashed(evidence):
    root,_=evidence
    p=root/'report.json'
    data=json.loads(p.read_text())
    data['runs'][0]['return_code']=1
    p.write_text(json.dumps(data))
    mp=root/'MANIFEST_SHA256.json'
    manifest=json.loads(mp.read_text())
    for x in manifest['files']:
        if x['path']=='report.json':
            raw=p.read_bytes()
            x['sha256']=hashlib.sha256(raw).hexdigest()
            x['bytes']=len(raw)
    mp.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='false M26 completion'):
        m27.analyze(root)


def test_junit_conflict_rejected_even_if_manifest_rehashed(evidence):
    root,_=evidence
    p=root/'junit.xml'
    xml=ET.parse(p)
    ET.SubElement(list(xml.getroot())[0],'skipped')
    xml.write(p,encoding='utf-8',xml_declaration=True)
    mp=root/'MANIFEST_SHA256.json'
    manifest=json.loads(mp.read_text())
    for x in manifest['files']:
        if x['path']=='junit.xml':
            raw=p.read_bytes()
            x['sha256']=hashlib.sha256(raw).hexdigest()
            x['bytes']=len(raw)
    mp.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='JUnit outcome'):
        m27.analyze(root)


def test_output_exact_stdout_and_sha(evidence,tmp_path):
    root,_=evidence
    out=tmp_path/'m27'
    recorded=[]
    m27.write_once(out,m27.analyze(root),input_folder=root,emit_bytes=recorded.append)
    assert (out/'console.log').read_bytes()==b''.join(recorded)
    inventory=json.loads((out/'MANIFEST_SHA256.json').read_text())
    assert set(inventory['entries'])=={'console.log','junit.xml','analysis.json'}
    for name,entry in inventory['entries'].items():
        raw=(out/name).read_bytes()
        assert entry['sha256']==hashlib.sha256(raw).hexdigest()
        assert entry['bytes']==len(raw)
    with pytest.raises(FileExistsError):
        m27.write_once(out,m27.analyze(root),input_folder=root,emit_bytes=recorded.append)


def test_output_inside_source_refused(evidence):
    root,_=evidence
    with pytest.raises(ValueError):
        m27.write_once(root/'M27',m27.analyze(root),input_folder=root,
                       emit_bytes=lambda raw:None)


def test_partial_timeout_keeps_hold_without_cherrypicking(tmp_path,monkeypatch):
    def timeout(path,options):
        return {'status':'TIMEOUT','return_code':1,'elapsed_s':30,
                'stdout':b'TIMEOUT\n'}
    dest=tmp_path/'partial'
    prior=m26.run(dest,child_runner=timeout,emit_bytes=lambda raw:None)
    assert prior['status'].startswith('HOLD_')
    result=m27.analyze(dest)
    assert result['status']=='HOLD_INCOMPLETE_RUNS'
    assert result['statistics']=={} and result['comparable'] is False


def test_invalid_input_emits_failing_junit(evidence,tmp_path):
    root,_=evidence
    (root/'console.log').write_text('tampered')
    output=tmp_path/'invalid'
    assert m27.main(['--input',str(root),'--out',str(output)])==1
    assert json.loads((output/'analysis.json').read_text())['status']=='HOLD_INVALID_INPUT'
    assert ET.parse(output/'junit.xml').findall('.//failure')
