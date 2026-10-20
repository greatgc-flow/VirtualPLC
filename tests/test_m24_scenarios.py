"""M24 isolated tests; synthetic faults are never credited as external P0 evidence."""
from pathlib import Path
import json
import socket
import xml.etree.ElementTree as ET

import pytest

from scripts import m24_scenarios as s


@pytest.mark.parametrize('seed', [0, 1, 17, 42, 2**32-1])
def test_seed_reproducible_and_catalog_complete(seed):
    a=s.scenario_order(seed, 3)
    assert a==s.scenario_order(seed, 3)
    assert len(a)==9
    assert all(a.count(n)==3 for n in s.SCENARIOS)

@pytest.mark.parametrize('seed,repeats,delay',[(None,1,60),(-1,1,60),(2**32,1,60),
                                               (True,1,60),(1,0,60),(1,4,60),(1,False,60),
                                               (1,1,0),(1,1,201),(1,1,True),(1,1,float('nan'))])
def test_bad_options_rejected(seed,repeats,delay):
    with pytest.raises(ValueError):s.validate_plan(seed,repeats,delay)

@pytest.mark.parametrize('name',[*s.SCENARIOS])
def test_real_local_fault_scenario(name):
    r=s.run_one(name,60)
    assert r['scenario']==name
    assert r.get('memory_unchanged',r.get('dropped_write_uncommitted',r.get('readback_unchanged')))


def test_unknown_scenario_rejected():
    with pytest.raises(ValueError):s.run_one('packet_from_production',60)


def test_end_to_end_evidence(tmp_path):
    target=tmp_path/'fresh'
    r=s.run(target,17,1,60)
    assert r['status']=='OBSERVED_NONCERTIFYING'
    assert r['release']=='HOLD' and r['external_p0_promoted']==0
    assert r['source_unchanged'] and len(r['results'])==3
    assert set(x.name for x in target.iterdir())=={'console.log','report.json','junit.xml','MANIFEST_SHA256.json'}
    manifest=json.loads((target/'MANIFEST_SHA256.json').read_text(encoding='utf-8'))
    from scripts.m22_soak import sha
    for name,entry in manifest['files'].items():
        assert sha(target/name)==entry['sha256'] and (target/name).stat().st_size==entry['bytes']
    root=ET.parse(target/'junit.xml')
    assert root.getroot().get('tests')=='3' and root.getroot().get('failures')=='0'
    assert not root.findall('.//property[@name="case_id"]')
    with pytest.raises(ValueError):s.run(target,17,1,60)


def test_cannot_write_under_checkout(tmp_path):
    path=Path(__file__).resolve().parent / '_DO_NOT_CREATE_M24_'
    with pytest.raises(ValueError):s._safe_output(path)


def test_scenario_failure_is_hold(monkeypatch,tmp_path):
    real=s.run_one
    def fail(name, delay):
        if name=='delay_then_read':raise OSError('simulated failure secret')
        return real(name,delay)
    monkeypatch.setattr(s,'run_one',fail)
    out=tmp_path/'hold'
    rep=s.run(out,17,1,60)
    assert rep['status']=='HOLD_EXECUTION_FAILED'
    assert 'simulated failure secret' not in (out/'console.log').read_text()
    assert ET.parse(out/'junit.xml').getroot().get('failures')!='0'


def test_source_drift_is_hold(monkeypatch,tmp_path):
    actual=s.wire.sha
    ctr={'n':0}
    def changed(path):
        ctr['n']+=1
        return '0'*64 if ctr['n']>len(s.SOURCE_FILES) else actual(path)
    monkeypatch.setattr(s.wire,'sha',changed)
    r=s.run(tmp_path/'drift',17,1,60)
    assert r['status']=='HOLD_SOURCE_CHANGED'
