"""Official iQ-R CPU built-in Ethernet remote RUN/STOP opening method preflight.

Mitsubishi SH-082488ENG-E: design precautions printed p.3;
Appendix 8 pp.684-685 identifies the built-in Ethernet Opening Method
parameter group A031H. OFFLINE REFERENCE ONLY: not a runnable CPU
profile, not RJ71EN71, no physical PLC network access.
"""
import importlib
import json
import socket

import pytest

from virtual_plc import Server
from virtual_plc.__main__ import build_parser
from virtual_plc.ethernet import EthernetSettings, model_catalog, reference_catalog
from virtual_plc.guide import data


@pytest.fixture
def inspect():
    # Dynamic retrieval preserves observed TDD RED without import-time collection errors.
    return getattr(importlib.import_module("virtual_plc.ethernet"),
                   "inspect_reference_rncpu_remote_opening")


def test_missing_opening_method_stays_unknown(inspect):
    result = inspect()
    assert result["model"] == "rncpu_builtin"
    assert result["opening_method"] is None
    assert result["reconnect_risk_status"] == "UNKNOWN"
    assert result["recommended_opening_method"] == "do_not_open_by_program"
    assert result["factory_default"] is None
    assert result["physical_hardware_certified"] is False
    assert result["simulator_network_affected"] is False
    assert result["status"] == "OFFICIAL_MANUAL_REFERENCE_ONLY"
    assert json.loads(json.dumps(result)) == result


def test_open_by_program_is_documented_remote_run_reconnect_risk(inspect):
    report = inspect("open_by_program")
    assert report["reconnect_risk_status"] == "DOCUMENTED_REMOTE_RUN_RECONNECT_FAILURE"
    assert report["opening_method"] == "open_by_program"
    assert report["remote_run_after_stop_guaranteed"] is False
    assert "close" in report["explanation"].lower()
    assert "remote RUN" in report["explanation"]


def test_do_not_open_by_program_removes_specific_risk_not_all_risks(inspect):
    report = inspect("do_not_open_by_program")
    assert report["reconnect_risk_status"] == "NO_SPECIFIC_OPENING_METHOD_RISK_DOCUMENTED"
    assert report["remote_run_after_stop_guaranteed"] is False
    assert report["physical_hardware_certified"] is False
    assert report["simulator_network_affected"] is False
    assert report["opening_method"] == "do_not_open_by_program"


@pytest.mark.parametrize("invalid", [
    "", "OPEN_BY_PROGRAM", "Open by Program", "do_not_open_by_program ",
    "open_by_prog", "automatic", "open", "unknown", "rj71en71",
    0, 1, True, False, 1.0, [], {}, ["open_by_program"],
])
def test_invalid_opening_method_rejected_without_guessing(inspect, invalid):
    with pytest.raises(ValueError):
        inspect(invalid)


def test_manual_provenance_ssot_and_exact_cpu_parameter_scope(inspect):
    cat = reference_catalog()
    entry = cat["rncpu_builtin"]["remote_opening_reference"]
    assert entry["recommended_opening_method"] == "do_not_open_by_program"
    assert entry["parameter_id"] == "A031H"
    assert entry["factory_default"] is None
    assert entry["source"]["manual"] == "SH-082488ENG-E"
    assert entry["source"]["page"] == "3, 684-685"
    assert entry["source"]["url"].endswith("/sh082488enge.pdf")
    assert entry["gxworks3_path"][-1] == "Opening Method"
    assert inspect("open_by_program")["source"] == entry["source"]
    assert "remote_opening_reference" not in cat["fx5_cpu_builtin"]
    assert "remote_opening_reference" not in cat["fx5_enet"]
    assert "rncpu_builtin" not in model_catalog()
    assert set(model_catalog()) == {"qj71e71", "lj71e71", "rj71en71"}
    with pytest.raises(ValueError):
        EthernetSettings("rncpu_builtin")


def test_defensive_catalog_json_guide_and_independent_reports(inspect):
    original = reference_catalog()
    assert data(build_parser(), "ethernet")["reference_only_models"] == original
    current = inspect()
    original["rncpu_builtin"]["remote_opening_reference"]["source"]["manual"] = "fake"
    assert inspect()["source"] == current["source"]
    assert reference_catalog()["rncpu_builtin"]["remote_opening_reference"]["source"] == current["source"]
    current["source"]["manual"] = "corrupted"
    assert inspect()["source"]["manual"] == "SH-082488ENG-E"


def test_offline_reference_never_binds_or_changes_listener_defaults(inspect, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("no network access for reference-only inspector")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert inspect()["simulator_network_affected"] is False
    assert inspect("open_by_program")["simulator_network_affected"] is False
    assert inspect("do_not_open_by_program")["simulator_network_affected"] is False
    assert build_parser().get_default("max_clients") == 64
    assert Server.__init__.__defaults__ is not None
