"""Evidence validator mutation tests prevent false green releases."""
from pathlib import Path
import shutil
from xml.etree import ElementTree as ET

import pytest
from scripts.merge_m10_evidence import PHASES, merge

SOURCE = Path(__file__).resolve().parents[1] / 'evidence_m10'


def evidence_copy(tmp_path):
    root=tmp_path/'inputs'
    root.mkdir()
    for phase in PHASES:
        shutil.copyfile(SOURCE/(phase+'.xml'),root/(phase+'.xml'))
    return root


def test_complete_validated_suite(tmp_path):
    root=evidence_copy(tmp_path)
    result=merge(root,tmp_path/'out')
    assert result['p0_observed_pass']==183
    assert result['p0_not_run']==16
    assert (tmp_path/'out'/'summary.json').read_bytes() == (tmp_path/'out'/'console.txt').read_bytes()


def test_does_not_reuse_existing_outputs(tmp_path):
    root=evidence_copy(tmp_path)
    dst=tmp_path/'out';dst.mkdir();(dst/'canary').write_text('keep')
    with pytest.raises(FileExistsError):merge(root,dst)
    assert (dst/'canary').read_text()=='keep'


def test_missing_phase_rejected(tmp_path):
    root=evidence_copy(tmp_path)
    (root/'m10.xml').unlink()
    with pytest.raises(FileNotFoundError):merge(root,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_corrupted_junit_rejected(tmp_path):
    root=evidence_copy(tmp_path)
    path=root/'m10.xml'
    path.write_text('<broken xml',encoding='utf-8')
    with pytest.raises(ET.ParseError):merge(root,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_junit_failure_rejected(tmp_path):
    root=evidence_copy(tmp_path)
    path=root/'m10.xml'
    tree=ET.parse(path)
    node=next(tree.getroot().iter('testcase'))
    ET.SubElement(node,'failure',{'message':'injected regression'})
    tree.write(path)
    with pytest.raises(ValueError,match='failed, skipped or missing'):merge(root,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_duplicate_case_id_rejected(tmp_path):
    root=evidence_copy(tmp_path)
    path=root/'m10.xml'
    tree=ET.parse(path)
    tc=[e for e in tree.getroot().iter('testcase') if e.find('./properties/property[@name="case_id"]') is not None]
    assert len(tc)==2
    tc[1].find('./properties/property[@name="case_id"]').set('value',
       tc[0].find('./properties/property[@name="case_id"]').get('value'))
    tree.write(path)
    with pytest.raises(ValueError,match='CASE-ID'):merge(root,tmp_path/'out')
    assert not (tmp_path/'out').exists()
