"""Mutation/negative tests for evidence regression audit. No P0 status promotion."""
from __future__ import annotations
import subprocess
import sys
import xml.etree.ElementTree as ET
import pytest
from scripts.m12_audit import analyze_junit


def fixture_junit(tmp_path, extra=None, n=51):
    root=ET.Element('testsuite')
    for i in range(n):
        item=ET.SubElement(root,'testcase',{'classname':'tests.test_m12_fault_matrix',
                                           'name':'test_fault_%03d'%i})
        if i==0 and extra:
            ET.SubElement(item,extra)
    path=tmp_path/'junit.xml'
    ET.ElementTree(root).write(path,encoding='utf-8')
    return path


def test_valid_independent_evidence_matrix(tmp_path):
    assert analyze_junit(fixture_junit(tmp_path))['m12_fault_matrix_cases']==51

@pytest.mark.parametrize('status',['failure','error','skipped'])
def test_rejects_nonpass_junit(tmp_path,status):
    with pytest.raises(ValueError,match='failed/errored/skipped'):
        analyze_junit(fixture_junit(tmp_path,status))

@pytest.mark.parametrize('count',[0,50,52])
def test_rejects_missing_or_inflated_matrix(tmp_path,count):
    with pytest.raises(ValueError):
        analyze_junit(fixture_junit(tmp_path,n=count))


def test_rejects_duplicate_test_identity(tmp_path):
    file=fixture_junit(tmp_path)
    root=ET.parse(file).getroot()
    root.append(ET.fromstring(ET.tostring(root[0])))
    ET.ElementTree(root).write(file,encoding='utf-8')
    with pytest.raises(ValueError,match='duplicate'):
        analyze_junit(file)


def test_cli_does_not_overwrite_existing_evidence(tmp_path):
    target=tmp_path/'old'
    target.mkdir()
    p=subprocess.run([sys.executable,'-m','scripts.m12_audit',
                     '--junit',str(fixture_junit(tmp_path)),'--out',str(target)],
                     text=True,capture_output=True,timeout=10)
    assert p.returncode!=0
    assert 'overwrite' in p.stderr


def test_cli_console_and_file_identical_and_release_hold(tmp_path):
    target=tmp_path/'new'
    p=subprocess.run([sys.executable,'-m','scripts.m12_audit',
                     '--junit',str(fixture_junit(tmp_path)),'--out',str(target)],
                     capture_output=True,timeout=10)
    assert p.returncode==0
    assert p.stdout==(target/'console.txt').read_bytes()==(target/'result.json').read_bytes()
    assert b'"p0_remaining": 16' in p.stdout
    assert b'"release": "HOLD"' in p.stdout
