"""M21 roadmap delta cannot silently close an external P0 case."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_m21_delta_is_complete_and_nonpromoting():
    previous=json.loads((ROOT/'backlog/M20_BACKLOG.json').read_text())
    current=json.loads((ROOT/'backlog/M21_DELTA.json').read_text())
    actual={x for item in previous['external_dependencies'] for x in item['case_ids']}
    assert len(actual)==16
    assert actual==set(current['external_case_ids'])
    assert current['external_unverified_cases']==16
    assert current['release']=='HOLD'
    assert all(item['status'].startswith('BLOCKED_') for item in previous['external_dependencies'])


def test_m21_only_one_internal_completion():
    current=json.loads((ROOT/'backlog/M21_DELTA.json').read_text())
    rows={i['id']:i for i in current['items']}
    assert len(rows)==4
    assert rows['BL-INT-002']['status']=='IMPLEMENTED_LOCAL_M21'
    assert rows['BL-INT-002']['release_certification'] is False
    assert rows['BL-INT-003']['status']=='NEXT'
    assert rows['BL-INT-004']['status']=='BACKLOG'
