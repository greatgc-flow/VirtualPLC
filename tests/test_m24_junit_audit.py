"""Ownership & fail-closed gate tests for the collected original JUnit."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
from scripts import m24_junit_audit as a

ROOT=Path(__file__).resolve().parents[1]


def _catalog(tmp_path):
    catalog=tmp_path/'catalog.jsonl'
    catalog.write_text('\n'.join(json.dumps({'id':'CASE-%04d'%i, 'phase':'P0'}) for i in range(1,18)),encoding='utf-8')
    backlog=tmp_path/'backlog.json'
    backlog.write_text(json.dumps({'external_dependencies':[{'case_ids':['CASE-%04d'%i for i in range(2,18)]}]}),encoding='utf-8')
    return catalog,backlog


def _junit(p,case='CASE-0001',name='one',outcome=None):
    root=ET.Element('testsuite',tests='1')
    test=ET.SubElement(root,'testcase',classname='x',name=name)
    props=ET.SubElement(test,'properties')
    ET.SubElement(props,'property',name='case_id',value=case)
    if outcome:ET.SubElement(test,outcome)
    ET.ElementTree(root).write(p,encoding='utf-8')


def test_valid_unique_evidence(tmp_path):
    cat,backlog=_catalog(tmp_path);f=tmp_path/'one.xml';_junit(f)
    r=a.audit([f],cat,backlog)
    assert r['locally_observed']==1 and r['external_hold_count']==16 and r['release']=='HOLD'


def test_duplicate_owner_rejected(tmp_path):
    cat,backlog=_catalog(tmp_path);a1=tmp_path/'one.xml';a2=tmp_path/'two.xml'
    _junit(a1);_junit(a2,name='other')
    with pytest.raises(ValueError,match='duplicate CASE-ID'):a.audit([a1,a2],cat,backlog)


@pytest.mark.parametrize('outcome',['failure','error','skipped'])
def test_failed_test_rejected(tmp_path,outcome):
    cat,backlog=_catalog(tmp_path);f=tmp_path/'one.xml';_junit(f,outcome=outcome)
    with pytest.raises(ValueError,match='nonpassing'):a.audit([f],cat,backlog)


def test_no_backlog_swap(tmp_path):
    cat,backlog=_catalog(tmp_path);f=tmp_path/'one.xml';_junit(f)
    info=json.loads(backlog.read_text());info['external_dependencies'][0]['case_ids'][0]='CASE-0001'
    backlog.write_text(json.dumps(info))
    with pytest.raises(ValueError):a.audit([f],cat,backlog)


def test_old_m4_owner_is_deprecated():
    legacy=(ROOT/'tests/test_m4_p0_case_ids.py').read_text()
    updated=(ROOT/'tests/test_m4_p0_case_ids_v2.py').read_text()
    assert "record_property('legacy_case_id',case_id)" in legacy
    assert "record_property('case_id',case_id)" in updated
