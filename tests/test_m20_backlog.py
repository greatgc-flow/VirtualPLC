"""Fail-closed governance: external dependencies never become false PASSes."""
import json
from pathlib import Path

from virtual_plc.faults import FaultPlan, MAX_STEPS, MAX_DELAY_MS
from virtual_plc.server import Server

ROOT = Path(__file__).resolve().parents[1]


def ledger():
    return json.loads((ROOT / 'backlog/M20_BACKLOG.json').read_text(encoding='utf-8'))


def test_all_unverified_p0_ids_are_accounted_once():
    backlog = ledger()
    older = json.loads((ROOT / 'M19_GATES.json').read_text(encoding='utf-8'))
    listed = [cid for group in backlog['external_dependencies'] for cid in group['case_ids']]
    expected = [cid for gate in older['gates'].values() for cid in gate['case_ids']]
    assert len(listed) == len(set(listed)) == 16
    assert set(listed) == set(expected)
    assert backlog['external_unverified_total'] == len(listed)
    assert backlog['p0_total'] - backlog['p0_historic_local_observed_unattested'] == 16


def test_every_external_work_item_remains_blocked_and_explained():
    for item in ledger()['external_dependencies']:
        assert item['id'].startswith('BL-EXT-')
        assert item['status'].startswith('BLOCKED_')
        assert item['priority'] == 'P0'
        for field in ('blocked_by','resume_when','owner_role','next_action'):
            assert len(item[field]) > 15
        assert len(item['acceptance']) >= 2
    assert ledger()['release'] == 'HOLD'


def test_backlog_gate_partition_mece():
    groups = ledger()['external_dependencies']
    assert {g['gate'] for g in groups} == {'G0-C','G0-E','G3','G4'}
    assert sorted(len(g['case_ids']) for g in groups) == [2,2,6,6]


def test_internal_roadmap_has_unique_next_actions():
    items = ledger()['internal_roadmap']
    assert len({i['id'] for i in items}) == len(items)
    assert items[0]['status'] == 'IMPLEMENTED_AND_LOCAL_REGRESSION_PASS_M20'
    assert items[1]['status'] == 'NEXT'


def test_injection_is_not_exported_in_external_toml_configuration():
    from virtual_plc.config import DEFAULTS
    assert 'fault_plan' not in DEFAULTS
    assert FaultPlan([]).snapshot()['remaining'] == 0


def test_fault_plan_has_finite_upper_bounds():
    assert MAX_STEPS <= 256
    assert MAX_DELAY_MS <= 500


def test_server_fault_plan_is_opt_in():
    with Server(('127.0.0.1', 0)) as server:
        assert server.fault_plan is None
