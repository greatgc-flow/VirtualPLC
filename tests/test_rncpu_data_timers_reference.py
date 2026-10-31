"""R04CPU built-in Ethernet A038H timers, official offline GUI contract.

Manufacturer SH-081257ENG-AD: built-in R04CPU Application Settings
pp.329-330 explicitly reference shared timer table pp.396-397.
CPU manual SH-082488ENG-E p.685 assigns A038H. Never infer that
other RnCPU firmware or RJ71EN71 network module shares hardware behavior.
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
    # RED-first: new API must be missing until implementation commit.
    return getattr(importlib.import_module("virtual_plc.ethernet"),
                   "inspect_reference_rncpu_data_timers")


DEFAULTS = {
    "tcp_ulp_ms": 30000,
    "tcp_zero_window_ms": 10000,
    "tcp_resend_ms": 10000,
    "tcp_end_ms": 20000,
    "ip_assembly_ms": 5000,
    "response_monitor_ms": 30000,
    "alive_start_ms": 600000,
    "alive_interval_ms": 10000,
    "alive_retries": 3,
}


def test_r04cpu_factory_reference_no_timer_change(inspect):
    report = inspect()
    assert report["interface"] == "rncpu_builtin"
    assert report["model"] == "R04CPU"
    assert report["parameter_id"] == "A038H"
    assert report["change_set_timer_value"] is False
    assert report["status"] == "OFFICIAL_MANUAL_REFERENCE_ONLY"
    assert report["physical_hardware_certified"] is False
    assert report["simulator_network_affected"] is False
    assert report["factory_model_scope"] == "R04CPU_GXWORKS3_EXAMPLE"
    assert {n: v["value"] for n, v in report["parameters"].items()} == DEFAULTS
    assert all(v["overridden"] is False for v in report["parameters"].values())
    assert json.loads(json.dumps(report)) == report
    assert inspect("R04CPU", {}) == report
    assert inspect("R04CPU", None) == report


def test_explicit_equal_default_preserves_override_intent(inspect):
    report = inspect("R04CPU", {
        "change_set_timer_value": True,
        "timers": {"tcp_resend_ms": {"value": 10, "unit": "s"},
                   "tcp_zero_window_ms": {"value": 10000, "unit": "ms"}},
    })
    assert report["change_set_timer_value"] is True
    assert report["parameters"]["tcp_resend_ms"]["value"] == 10000
    assert report["parameters"]["tcp_resend_ms"]["overridden"] is True
    assert report["parameters"]["tcp_zero_window_ms"]["overridden"] is True
    assert report["parameters"]["tcp_ulp_ms"]["overridden"] is False
    assert report["parameters"]["tcp_resend_ms"]["default"] == 10000


@pytest.mark.parametrize("timer", [k for k in DEFAULTS if k != "alive_retries"])
@pytest.mark.parametrize("unit,low,high", [("ms", 100, 16383000), ("s", 1, 16383)])
def test_each_time_field_supports_vendor_bounds_when_other_constraints_hold(
        inspect, timer, unit, low, high):
    # Validate raw source range using individually altered timer data.
    # Some extremes are invalid in context because the official global
    # inequalities/paired timer values still apply; make them fail closed.
    for point in (low, high):
        candidate = {"change_set_timer_value": True, "timers": {
            timer: {"value": point, "unit": unit},
        }}
        if timer in ("tcp_resend_ms", "tcp_zero_window_ms"):
            candidate["timers"] = {
                "tcp_resend_ms": {"value": point, "unit": unit},
                "tcp_zero_window_ms": {"value": point, "unit": unit},
            }
        if timer in ("alive_start_ms", "alive_interval_ms"):
            expected_valid = True  # independent existence-check timers
        else:
            values = dict(DEFAULTS)
            for key in candidate["timers"]:
                values[key] = point * 1000 if unit == "s" else point
            expected_valid = (values["response_monitor_ms"] >= values["tcp_ulp_ms"]
                >= values["tcp_end_ms"] >= values["tcp_resend_ms"]
                >= values["ip_assembly_ms"] and
                values["tcp_resend_ms"] == values["tcp_zero_window_ms"])
        if expected_valid:
            report = inspect("R04CPU", candidate)
            assert report["parameters"][timer]["value"] == (
                point * 1000 if unit == "s" else point)
        else:
            with pytest.raises(ValueError):
                inspect("R04CPU", candidate)


@pytest.mark.parametrize("retry", [1, 3, 99999])
def test_retry_count_boundaries(inspect, retry):
    report = inspect("R04CPU", {
        "change_set_timer_value": True, "timers": {"alive_retries": retry}
    })
    assert report["parameters"]["alive_retries"]["value"] == retry
    assert report["parameters"]["alive_retries"]["unit"] == "count"


def test_equal_tcp_retry_and_ip_assembly_is_allowed_by_ge_relation(inspect):
    # Printed p.397 specifies '>=' not a strict '>' inequality.
    result = inspect("R04CPU", {
        "change_set_timer_value": True,
        "timers": {
            "ip_assembly_ms": {"value": 10, "unit": "s"},
        },
    })
    assert result["parameters"]["ip_assembly_ms"]["value"] == 10000


@pytest.mark.parametrize("bad", [
    {"change_set_timer_value": 1},
    {"change_set_timer_value": "yes"},
    {"change_set_timer_value": None},
    {"unexpected": 0},
    {"timers": None},
    {"timers": []},
    {"timers": {"alive_retries": 4}},
    {"change_set_timer_value": False, "timers": {"alive_retries": 3}},
    {"change_set_timer_value": True, "timers": {"bad_timer": 1}},
    {"change_set_timer_value": True, "timers": {"alive_retries": False}},
    {"change_set_timer_value": True, "timers": {"alive_retries": 0}},
    {"change_set_timer_value": True, "timers": {"alive_retries": 100000}},
    {"change_set_timer_value": True, "timers": {"alive_retries": "3"}},
    {"change_set_timer_value": True, "timers": {"alive_retries": 3.0}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": None}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": 30000}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": {"value": 10}}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": {"unit": "s"}}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": {"value": 10, "unit": "s", "x": 1}}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": {"value": True, "unit": "ms"}}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": {"value": 99, "unit": "ms"}}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": {"value": 101, "unit": "ms"}}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": {"value": 16383001, "unit": "ms"}}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": {"value": 0, "unit": "s"}}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": {"value": 16384, "unit": "s"}}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": {"value": 10, "unit": "MS"}}},
    {"change_set_timer_value": True, "timers": {"tcp_ulp_ms": {"value": 10, "unit": None}}},
    {"change_set_timer_value": True, "timers": {"tcp_end_ms": {"value": 9, "unit": "s"}}},
    {"change_set_timer_value": True, "timers": {"response_monitor_ms": {"value": 15, "unit": "s"}}},
    {"change_set_timer_value": True, "timers": {"tcp_resend_ms": {"value": 15, "unit": "s"}}},
])
def test_unknown_invalid_partial_and_cross_field_inputs_fail_closed(inspect, bad):
    with pytest.raises(ValueError):
        inspect("R04CPU", bad)


@pytest.mark.parametrize("bad", [
    "", "R08CPU", "R00CPU", "r04cpu", "rj71en71",
    "fx5_cpu_builtin", "R04ENCPU", False, None, [], {},
])
def test_not_all_cpu_families_or_firmware_are_assumed_equivalent(inspect, bad):
    with pytest.raises(ValueError):
        inspect(bad)


@pytest.mark.parametrize("bad", [False, True, [], "", "null", 1, 1.0, ()])
def test_invalid_root_is_not_omitted(inspect, bad):
    with pytest.raises(ValueError):
        inspect("R04CPU", bad)


def test_manufacturer_ssot_source_scope_and_defensive_copies(inspect):
    original = reference_catalog()
    metadata = original["rncpu_builtin"]["data_timer_reference"]
    assert metadata["parameter_id"] == "A038H"
    assert metadata["factory_model_scope"] == "R04CPU_GXWORKS3_EXAMPLE"
    assert metadata["source"]["manual"] == "SH-081257ENG-AD"
    assert metadata["source"]["page"] == "329-330, 396-397"
    assert metadata["source"]["url"].endswith("/sh081257engad.pdf")
    assert {k: v["default"] for k, v in metadata["parameters"].items()} == DEFAULTS
    assert metadata["cpu_parameter_source"]["manual"] == "SH-082488ENG-E"
    assert metadata["cpu_parameter_source"]["page"] == "685"
    assert inspect()["source"] == metadata["source"]
    assert "data_timer_reference" not in original["fx5_enet"]
    assert "data_timer_reference" not in original["fx5_cpu_builtin"]
    assert set(model_catalog()) == {"qj71e71", "lj71e71", "rj71en71"}
    with pytest.raises(ValueError):
        EthernetSettings("rncpu_builtin")
    assert data(build_parser(), "ethernet")["reference_only_models"] == original
    original["rncpu_builtin"]["data_timer_reference"]["parameters"]["tcp_ulp_ms"]["default"] = 123
    assert inspect()["parameters"]["tcp_ulp_ms"]["value"] == 30000
    report = inspect()
    report["source"]["manual"] = "corrupted"
    report["parameters"]["tcp_ulp_ms"]["value"] = 1
    assert inspect()["source"]["manual"] == "SH-081257ENG-AD"
    assert inspect()["parameters"]["tcp_ulp_ms"]["value"] == 30000


def test_reference_timer_has_no_network_or_runtime_side_effect(inspect, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline metadata shall never access a network")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    report = inspect()
    assert report["simulator_network_affected"] is False
    assert report["physical_hardware_certified"] is False
    assert build_parser().get_default("max_clients") == 64
    assert Server.__init__.__defaults__ is not None
