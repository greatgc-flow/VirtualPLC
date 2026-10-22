"""M28 synthetic cross-bundle unit suite; no origin/Windows attestation."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from scripts import m28_cross_bundle as m28


def _fake_analysis(folder):
    p=Path(folder)
    manifest=json.loads((p/'report.json').read_text())
    rows=[]
    for i in range(1,manifest['attempted']+1):
        if (p/f'runs/{i:02d}/report.json').exists():
            child=json.loads((p/f'runs/{i:02d}/report.json').read_text())
            rows.append({'run':i,'status':'VERIFIED','anomalies':[],'metrics':child['metrics']})
        else:
            rows.append({'run':i,'status':'HOLD','anomalies':['FAILED_OR_INCOMPLETE_RUN'],'metrics':None})
    status='COMPARABLE_DESCRIPTIVE' if len(rows)==manifest['requested'] and all(x['status']=='VERIFIED' for x in rows) else 'HOLD_INCOMPLETE_RUNS'
    stats={}
    if status=='COMPARABLE_DESCRIPTIVE':
        for key in m28.METRICS:
            values=[x['metrics'][key] for x in rows]
            stats[key]={'median':sorted(values)[len(values)//2],'status':'DESCRIPTIVE_ONLY'}
    return {'status':status,'requested':manifest['requested'], 'attempted':manifest['attempted'],'runs':rows,'statistics':stats}


def _make_bundle(tmp_path,index,*,runs=3,p95=100,platform='TEST_ONLY',python='3.11.mock',clients=2,source='a',drop=False):
    root=tmp_path/f'bundle_{index}'
    root.mkdir()
    options={'runs':runs,'clients':clients,'duration':0.5,'max_cycles':30,'delay_ms':20,'timeout':30}
    parent={'synthetic_unique_index':index,'requested':runs,'attempted':runs-1 if drop else runs,
            'options':options,'source_sha256':{'file.py':source*64}}
    (root/'report.json').write_text(json.dumps(parent))
    (root/'MANIFEST_SHA256.json').write_text(json.dumps({'mock_index':index}))
    for i in range(1,parent['attempted']+1):
        path=root/f'runs/{i:02d}'
        path.mkdir(parents=True)
        metrics={'p50_us':p95-15+i,'p95_us':p95+i,'p99_us':p95+20+i,
                 'rss_initial_kib':1000,'rss_final_kib':1100+i,
                 'rss_slope_kib_per_minute':1.0,'rss_within_run_delta_kib':100+i,
                 'requests_ok':100}
        child={'platform':platform,'python_version':python,'metrics':metrics,
               'mock_unique':index*50+i}
        (path/'report.json').write_text(json.dumps(child))
    return root


@pytest.fixture
def pair(tmp_path, monkeypatch):
    # The fixture deliberately is NOT an actual signed/provenanced M26 artifact.
    # Patch only upstream M26/M27 validators; exercise all M28 comparison logic.
    monkeypatch.setattr(m28.m27,'analyze',_fake_analysis)
    monkeypatch.setattr(m28.m26,'verify_output',lambda root: True)
    return [_make_bundle(tmp_path,1,p95=100), _make_bundle(tmp_path,2,p95=120)]


def test_two_bundles_descriptive_only(pair):
    r=m28.analyze(pair)
    assert r['status']=='DESCRIPTIVE_CROSS_BUNDLE'
    assert r['release']=='HOLD' and not r['independent_approval']
    assert r['bundle_count']==2 and r['external_p0_hold']==16
    assert r['comparisons'][0]['median_deltas']['p95_us']['delta']==20
    assert r['thresholds_explicit'] is None
    assert not r['bundle_details'][0]['environment']['origin_attested']


def test_three_bundles_ordered(pair, tmp_path):
    third=_make_bundle(tmp_path,3,p95=130)
    r=m28.analyze(pair+[third])
    assert [x['label'] for x in r['bundle_details']]==['bundle_01','bundle_02','bundle_03']
    assert len(r['comparisons'])==2


def test_optin_threshold_exceedance_not_release(pair):
    r=m28.analyze(pair,{'p95_growth_percent':10,'rss_growth_kib':0})
    assert r['status']=='OPTIONAL_THRESHOLD_EXCEEDED'
    assert {e['metric'] for e in r['threshold_exceedances']}=={'p95_growth_percent'}
    assert r['release']=='HOLD'


@pytest.mark.parametrize('limits',[{},[],{'unexpected':1},{'rss_growth_kib':-1},
                                   {'p99_growth_percent':float('nan')},{'rss_growth_kib':True}])
def test_limits_rejected(pair,limits):
    with pytest.raises(ValueError):m28.analyze(pair,limits)


@pytest.mark.parametrize('changes,reason',[
    (('platform','Windows'),'platform_or_python_mismatch'),
    (('python_version','3.14'),'platform_or_python_mismatch'),
    (('source_sha256',{'file.py':'b'*64}),'source_mismatch'),
    (('options.clients',3),'workload_mismatch')])
def test_incomparability(pair,changes,reason):
    path=pair[1]
    key,val=changes
    if key in ('platform','python_version'):
        for p in (path/'runs').glob('*/report.json'):
            j=json.loads(p.read_text());j[key]=val;p.write_text(json.dumps(j))
    else:
        p=path/'report.json';j=json.loads(p.read_text())
        if key.startswith('options.'):
            j['options'][key.split('.')[1]]=val
        else:j[key]=val
        p.write_text(json.dumps(j))
    r=m28.analyze(pair,{'p95_growth_percent':0})
    assert r['status']=='INCOMPARABLE'
    assert reason in r['comparison_blockers']['bundle_02']
    assert r['threshold_exceedances']==[] and r['comparisons']==[]


def test_different_run_count_needs_explicit_optin(pair,tmp_path):
    third=_make_bundle(tmp_path,5,runs=4,p95=125)
    r=m28.analyze([pair[0],third])
    assert r['status']=='INCOMPARABLE'
    assert 'run_count_mismatch' in r['comparison_blockers']['bundle_02']
    allowed=m28.analyze([pair[0],third],allow_unequal_runs=True)
    assert allowed['status']=='DESCRIPTIVE_CROSS_BUNDLE'
    assert allowed['run_count_difference_explicitly_allowed'] is True
    assert allowed['sampling_plan_differences']==['bundle_02']


def test_invalid_boolean_override(pair):
    with pytest.raises(ValueError):m28.analyze(pair,allow_unequal_runs=1)


def test_duplicate_folder_rejected(pair):
    with pytest.raises(ValueError,match='duplicate input folder'):m28.analyze([pair[0],pair[0]])


def test_replayed_original_rejected(pair,tmp_path):
    cloned=tmp_path/'copied'
    cloned.mkdir()
    cloned.joinpath('report.json').write_bytes((pair[0]/'report.json').read_bytes())
    cloned.joinpath('MANIFEST_SHA256.json').write_bytes((pair[0]/'MANIFEST_SHA256.json').read_bytes())
    for i in range(1,4):
        child=cloned/f'runs/{i:02d}';child.mkdir(parents=True)
        child.joinpath('report.json').write_bytes((pair[0]/f'runs/{i:02d}/report.json').read_bytes())
    with pytest.raises(ValueError,match='duplicate M26 report'):m28.analyze([pair[0],cloned])


def test_reused_child_rejected(pair):
    # Parent digest differs; copier reuses ONE observed child report.
    p=pair[1]/'runs/02/report.json'
    p.write_bytes((pair[0]/'runs/02/report.json').read_bytes())
    with pytest.raises(ValueError,match='reused M23 child'):m28.analyze(pair)


def test_partial_bundle_not_cherry_picked(pair,tmp_path):
    partial=_make_bundle(tmp_path,3,drop=True)
    r=m28.analyze([pair[0],partial])
    assert r['status']=='HOLD_INPUT_NOT_COMPARABLE'
    assert r['ineligible_bundles']==['bundle_02']
    assert r['comparisons']==[]


@pytest.mark.parametrize('count',[None,[],[1],list(range(13))])
def test_invalid_batch_size(count):
    with pytest.raises(ValueError):m28.analyze(count)


def test_symlink_refused(pair,tmp_path):
    link=tmp_path/'alias'
    link.symlink_to(pair[0],target_is_directory=True)
    with pytest.raises(ValueError,match='symlink'):m28.analyze([link,pair[1]])


def test_fresh_output_and_byte_exact_log(pair,tmp_path):
    report=m28.analyze(pair)
    out=tmp_path/'fresh'
    displayed=[]
    m28.write_once(out,report,pair,emit_bytes=displayed.append)
    assert (out/'console.log').read_bytes()==b''.join(displayed)
    assert m28.verify_output(out)
    assert not ET.parse(out/'junit.xml').findall('.//failure')
    with pytest.raises(FileExistsError):m28.write_once(out,report,pair,emit_bytes=displayed.append)


def test_output_tamper_fail(pair,tmp_path):
    out=tmp_path/'fresh'
    m28.write_once(out,m28.analyze(pair),pair,emit_bytes=lambda b:None)
    (out/'analysis.json').write_text('changed')
    with pytest.raises(ValueError,match='digest'):m28.verify_output(out)


def test_output_refuses_inside_inputs(pair):
    with pytest.raises(ValueError):m28.write_once(pair[0]/'result',m28.analyze(pair),pair,emit_bytes=lambda b:None)


def test_invalid_input_cli_has_failing_junit(pair,tmp_path):
    dest=tmp_path/'invalid'
    assert m28.main(['--inputs',str(pair[0]),'--out',str(dest)])==1
    assert json.loads((dest/'analysis.json').read_text())['status']=='HOLD_INVALID_INPUT'
    assert ET.parse(dest/'junit.xml').findall('.//failure')
