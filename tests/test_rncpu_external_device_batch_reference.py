"""Independent offline *batch* lint for R04CPU user config slots.

Only scalar per-row ranges come from Mitsubishi SH-081257ENG-AD
pp.324-326/554. Duplicate slots, slot gaps and own-port reuse are
*static analysis diagnostics*, NOT asserted Mitsubishi error codes.
Newer AG manual remains undiffed; no physical hardware certification.
"""
import importlib
import json
import socket

import pytest

from virtual_plc import Server
from virtual_plc.__main__ import build_parser
from virtual_plc.ethernet import (
    EthernetSettings, inspect_reference_rncpu_external_device,
    model_catalog, reference_catalog,
)
from virtual_plc.guide import data


@pytest.fixture
def lint():
    # RED must be observable as missing feature, not broken collection.
    return getattr(importlib.import_module("virtual_plc.ethernet"),
                   "inspect_reference_rncpu_external_device_batch")


def row(number, port):
    return {"connection_number": number, "plc_port": port}


def codes(result):
    return [d["code"] for d in result["diagnostics"]]


def test_none_root_is_not_supplied_not_an_empty_config(lint):
    result = lint()
    assert result["model"] == "R04CPU"
    assert result["input_state"] == "NOT_PROVIDED"
    assert result["static_preflight_state"] == "NOT_PROVIDED"
    assert result["rows"] == []
    assert result["diagnostics"] == []
    assert result["status"] == "SOURCE_SCOPED_STATIC_LINT_NOT_VENDOR_CERTIFIED"
    assert result["vendor_manual_revision"] == "AD"
    assert result["newer_manual_revision"] == "AG"
    assert result["newer_manual_comparison"] == "NOT_VERIFIED"
    assert result["physical_hardware_certified"] is False
    assert result["simulator_network_affected"] is False
    assert result["not_a_simultaneous_tcp_socket_limit"] is True
    assert json.loads(json.dumps(result)) == result


def test_empty_array_is_explicitly_empty(lint):
    out = lint([])
    assert out["input_state"] == "EMPTY"
    assert out["static_preflight_state"] == "EMPTY"
    assert out["rows"] == []
    assert out["diagnostics"] == []
    assert out != lint()


def test_single_row_projects_existing_scalar_offline_check(lint):
    out = lint([row(1, 1024)])
    assert out["input_state"] == "PROVIDED"
    assert out["static_preflight_state"] == "NO_STATIC_ISSUES_FOUND"
    assert out["diagnostics"] == []
    assert out["rows"] == [inspect_reference_rncpu_external_device("R04CPU", 1, 1024)]


def test_two_distinct_slots_and_ports_have_no_static_issues(lint):
    result = lint([row(1, 1024), row(2, 1025)])
    assert result["static_preflight_state"] == "NO_STATIC_ISSUES_FOUND"
    assert result["diagnostics"] == []
    assert [r["connection_number"] for r in result["rows"]] == [1, 2]
    assert all(x["plc_port_recommended"] for x in result["rows"])


@pytest.mark.parametrize("a,b,missing", [
    (1, 3, [2]), (2, 3, [1]), (1, 16, list(range(2, 16))),
    (15, 16, list(range(1, 15))),
])
def test_gaps_are_review_flags_not_a_vendor_rejection(lint, a, b, missing):
    result = lint([row(a, 1024), row(b, 1025)])
    assert result["static_preflight_state"] == "REVIEW_REQUIRED"
    assert codes(result) == ["SLOT_GAP_REVIEW"]
    gap = result["diagnostics"][0]
    assert gap["severity"] == "review"
    assert gap["missing_slots"] == missing
    assert result["physical_hardware_certified"] is False


def test_gap_policy_can_be_disabled_independently(lint):
    source = [row(3, 1024), row(4, 1025)]
    ignored = lint(source, report_slot_gaps=False)
    enabled = lint(source, report_slot_gaps=True)
    assert ignored["report_slot_gaps"] is False
    assert ignored["static_preflight_state"] == "NO_STATIC_ISSUES_FOUND"
    assert ignored["diagnostics"] == []
    assert codes(enabled) == ["SLOT_GAP_REVIEW"]
    assert source == [row(3, 1024), row(4, 1025)]


def test_duplicate_slot_is_static_collision_not_mitsubishi_end_code(lint):
    result = lint([row(1, 1024), row(1, 1025)])
    assert result["static_preflight_state"] == "REJECTED_STATIC_SETTINGS"
    assert codes(result) == ["DUPLICATE_SETTING_NUMBER"]
    duplicate = result["diagnostics"][0]
    assert duplicate["severity"] == "error"
    assert duplicate["connection_number"] == 1
    assert duplicate["positions"] == [0, 1]
    assert result["vendor_end_code"] is None


def test_duplicate_same_port_is_only_review_without_transport_data(lint):
    result = lint([row(1, 1024), row(2, 1024)])
    assert codes(result) == ["POTENTIAL_OWN_PORT_REUSE"]
    assert result["static_preflight_state"] == "REVIEW_REQUIRED"
    diag = result["diagnostics"][0]
    assert diag["severity"] == "review"
    assert diag["plc_port"] == 1024
    assert diag["positions"] == [0, 1]
    assert "transport" in diag["explanation"].lower()


def test_duplicate_slot_port_and_gap_have_stable_order(lint):
    result = lint([row(3, 1024), row(3, 1024), row(7, 1024)])
    assert codes(result) == [
        "DUPLICATE_SETTING_NUMBER", "POTENTIAL_OWN_PORT_REUSE",
        "SLOT_GAP_REVIEW",
    ]
    assert result["static_preflight_state"] == "REJECTED_STATIC_SETTINGS"
    assert result["diagnostics"][-1]["missing_slots"] == [1, 2, 4, 5, 6]


@pytest.mark.parametrize("number,port,classification", [
    (1, 5005, "system_service_port_not_user_configurable"),
    (2, 61441, "system_service_port_not_user_configurable"),
    (1, 61696, "system_service_port_not_user_configurable"),
    (1, 65534, "system_service_port_not_user_configurable"),
    (1, 0, "simulator_only_ephemeral"),
    (1, 5000, "outside_vendor_configurable_range"),
    (1, 65535, "outside_vendor_configurable_range"),
])
def test_bad_user_configurable_ports_report_individual_rows(
        lint, number, port, classification):
    # Focus on own-port classification. Gap warnings are tested separately.
    report = lint([row(number, port)], report_slot_gaps=False)
    assert report["rows"][0]["plc_port_classification"] == classification
    assert codes(report) == ["VENDOR_PORT_NOT_CONFIGURABLE"]
    assert report["static_preflight_state"] == "REJECTED_STATIC_SETTINGS"
    assert report["diagnostics"][0]["positions"] == [0]
    assert report["diagnostics"][0]["plc_port"] == port


@pytest.mark.parametrize("port", [1, 1024, 1025, 4999, 5010, 61439, 61443, 61500])
def test_vendor_allowed_ports_are_not_rejected_as_invalid(lint, port):
    report = lint([row(1, port)])
    assert "VENDOR_PORT_NOT_CONFIGURABLE" not in codes(report)
    assert report["static_preflight_state"] == "NO_STATIC_ISSUES_FOUND"


def test_blank_ports_do_not_trigger_ambiguous_reuse(lint):
    report = lint([row(1, None), row(2, None)])
    assert codes(report) == []
    assert [r["plc_port_classification"] for r in report["rows"]] == [
        "blank_default", "blank_default",
    ]


def test_duplicate_reserved_port_reports_static_port_issues(lint):
    report = lint([row(1, 5005), row(2, 5005)])
    assert codes(report) == [
        "VENDOR_PORT_NOT_CONFIGURABLE", "VENDOR_PORT_NOT_CONFIGURABLE",
        "POTENTIAL_OWN_PORT_REUSE",
    ]
    assert report["static_preflight_state"] == "REJECTED_STATIC_SETTINGS"


@pytest.mark.parametrize("root", ["", "none", True, False, 0, 1, 1.2, {}, (), {0: "x"}])
def test_invalid_root_is_rejected_not_guessed(lint, root):
    with pytest.raises(ValueError):
        lint(root)


@pytest.mark.parametrize("entries", [
    [None], [1], ["row"], [[]], [True],
    [{"connection_number": 1}],
    [{"plc_port": 1024}],
    [{"connection_number": 1, "plc_port": 1024, "transport": "tcp"}],
    [row(0, 1024)], [row(17, 1024)], [row(True, 1024)],
    [row("1", 1024)], [row(None, 1024)],
    [row(1, True)], [row(1, "1024")], [row(1, -1)],
    [row(1, 65536)],
])
def test_invalid_rows_fail_closed_and_do_not_read_sockets(lint, entries):
    with pytest.raises(ValueError):
        lint(entries)


@pytest.mark.parametrize("bad", ["", None, 0, 1, [], {}, "yes"])
def test_optional_gap_policy_requires_real_bool(lint, bad):
    with pytest.raises(ValueError):
        lint([row(1, 1024)], report_slot_gaps=bad)


@pytest.mark.parametrize("bad_model", [
    "rncpu_builtin", "R08CPU", "RJ71EN71", "rj71en71",
    "FX5U", "", None, 0, [], {}, True,
])
def test_model_scope_is_not_guessed(lint, bad_model):
    with pytest.raises(ValueError):
        lint([row(1, 1024)], model=bad_model)


def test_more_than_sixteen_user_slots_is_not_an_unbounded_list(lint):
    records = [row(i, 1024 + i) for i in range(1, 17)]
    assert lint(records)["static_preflight_state"] == "NO_STATIC_ISSUES_FOUND"
    with pytest.raises(ValueError):
        lint(records + [row(1, 4999)])


def test_never_mutate_input_rows_or_ssot(lint):
    inp = [row(1, 1024), row(2, 1024)]
    cat = reference_catalog()
    report = lint(inp)
    assert cat["rncpu_builtin"]["external_device_configuration_reference"]["connection_number_range"] == [1, 16]
    report["rows"][0]["source"]["manual"] = "FAKE"
    report["diagnostics"][0]["positions"].append(88)
    assert inp == [row(1, 1024), row(2, 1024)]
    assert lint(inp)["rows"][0]["source"]["manual"] == "SH-081257ENG-AD"
    assert lint(inp)["diagnostics"][0]["positions"] == [0, 1]
    assert data(build_parser(), "ethernet")["reference_only_models"] == cat


def test_original_scalar_and_runnable_models_remain_unmodified(lint):
    x = inspect_reference_rncpu_external_device("R04CPU", 1, 5005)
    assert x["system_service"] == "auto_open_udp"
    assert lint([row(1, 5005)])["rows"][0] == x
    assert set(model_catalog()) == {"qj71e71", "lj71e71", "rj71en71"}
    with pytest.raises(ValueError):
        EthernetSettings("rncpu_builtin")


def test_no_network_runtime_listener_or_hardware_access(lint, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline batch lint may not access sockets")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert lint([row(1, 5005), row(2, 1024)])["simulator_network_affected"] is False
    assert lint([])["simulator_network_affected"] is False
    assert build_parser().get_default("max_clients") == 64
    assert Server.__init__.__defaults__ is not None


def test_invalid_port_and_missing_slot_can_be_reported_together(lint):
    # Deliberately assert composition instead of concealing independent
    # diagnostics. Slot 2 exists, No.1 is absent, 61441 is reserved.
    result = lint([row(2, 61441)])
    assert codes(result) == [
        "VENDOR_PORT_NOT_CONFIGURABLE", "SLOT_GAP_REVIEW",
    ]
    assert result["static_preflight_state"] == "REJECTED_STATIC_SETTINGS"
    assert result["diagnostics"][1]["missing_slots"] == [1]
