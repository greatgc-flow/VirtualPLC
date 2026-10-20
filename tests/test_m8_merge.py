"""Standalone mutation regression tests; do not depend on saved run artifacts."""
from xml.etree import ElementTree as ET
from pathlib import Path
import pytest
from scripts.merge_m8_evidence import combine, EXPECTED_PHASES
from scripts.gate_report import parse_junit


def small_junit(directory):
    directory.mkdir()
    for phase in EXPECTED_PHASES:
        suites = ET.Element('testsuites')
        suite = ET.SubElement(suites, 'testsuite', name=phase)
        ET.SubElement(suite, 'testcase', name='synthetic '+phase)
        ET.ElementTree(suites).write(directory/(phase+'.xml'), encoding='utf-8')
    return directory


def test_m8_rejects_missing_phase(tmp_path):
    d=small_junit(tmp_path/'phases')
    (d/'tcp.xml').unlink()
    with pytest.raises((FileNotFoundError, ValueError)):
        combine(d, tmp_path/'out')


def test_m8_rejects_failure(tmp_path):
    d=small_junit(tmp_path/'phases')
    path=d/'m7m8.xml'
    tree=ET.parse(path)
    ET.SubElement(next(tree.getroot().iter('testcase')), 'failure', message='mutation')
    tree.write(path, encoding='utf-8')
    with pytest.raises(ValueError, match='non-pass'):
        combine(d, tmp_path/'out')


def test_m8_rejects_duplicate_case_id(tmp_path):
    suites=ET.Element('testsuites'); suite=ET.SubElement(suites, 'testsuite')
    for i in range(2):
        tc=ET.SubElement(suite,'testcase',name=f'synthetic-{i}')
        ET.SubElement(ET.SubElement(tc,'properties'),'property',name='case_id',value='CASE-0121')
    path=tmp_path/'duplicated.xml'
    ET.ElementTree(suites).write(path,encoding='utf-8')
    seen, duplicate, unknown, anonymous=parse_junit(path, {'CASE-0121'})
    assert duplicate==['CASE-0121'] and not seen and not unknown and anonymous==0
