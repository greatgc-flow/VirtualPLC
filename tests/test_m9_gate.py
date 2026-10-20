"""Mutation guards for M9 merger; proof of rejection, not P0 closure."""
from pathlib import Path
import pytest
from scripts.merge_m9_evidence import merge


def test_merger_rejects_absent_phases(tmp_path):
    with pytest.raises(FileNotFoundError):
        merge(tmp_path / 'empty', tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_merger_rejects_existing_output(tmp_path):
    folder = tmp_path / 'out'
    folder.mkdir()
    with pytest.raises(FileExistsError):
        merge(tmp_path / 'empty', folder)


def test_merger_rejects_failing_junit(tmp_path):
    (tmp_path / 'base.xml').write_text('<testsuite><testcase><failure/></testcase></testsuite>')
    with pytest.raises(ValueError):
        merge(tmp_path, tmp_path / 'out')
