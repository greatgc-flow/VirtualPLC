"""M8 provenance gate: selected SHA-256 source and suite integrity, no overwrites."""
import hashlib
import json
from pathlib import Path
import pytest

from scripts.evidence_m8 import create_report, verify_report

ROOT = Path(__file__).resolve().parents[1]


def test_case_0146_verified_suite_source_manifest(tmp_path, record_property):
    record_property('case_id', 'CASE-0146')
    report, digest = create_report(ROOT, tmp_path)
    result = verify_report(ROOT, report, digest)
    assert result['status'] == 'PASS'
    assert result['suite_p0'] == 199
    assert result['suite_total'] == 208
    names = {v['path'] for v in result['files']}
    assert {'suite/catalog/test_cases.jsonl', 'virtual_plc/server.py',
            'virtual_plc/protocol.py', 'virtual_plc/memory.py',
            'virtual_plc/config.py', 'virtual_plc/telemetry.py'} <= names
    with pytest.raises(FileExistsError):
        create_report(ROOT, tmp_path)


def test_m8_tampered_report_rejected(tmp_path):
    report, digest = create_report(ROOT, tmp_path)
    record = json.loads(report.read_text())
    record['files'][0]['sha256'] = '0' * 64
    report.chmod(0o644)
    report.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        verify_report(ROOT, report, digest)


def test_m8_changed_source_rejected(tmp_path):
    copy = tmp_path / 'copy'
    for name in ['suite/catalog/test_cases.jsonl', 'virtual_plc/server.py',
                 'virtual_plc/memory.py', 'virtual_plc/protocol.py',
                 'virtual_plc/config.py', 'virtual_plc/telemetry.py',
                 'virtual_plc/__main__.py', 'suite/catalog/legacy_crosswalk.csv']:
        dst = copy / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((ROOT / name).read_bytes())
    report, digest = create_report(copy, tmp_path / 'results')
    assert verify_report(copy, report, digest)['status'] == 'PASS'
    (copy / 'virtual_plc/server.py').write_text('tampered')
    with pytest.raises(ValueError):
        verify_report(copy, report, digest)
