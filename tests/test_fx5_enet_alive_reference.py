"""RED-first tests: FX5-ENET operational alive timers, reference ONLY.

Official Mitsubishi SH-082026ENG-H printed p.70 (PDF page index 71):
Change/Set Timer Value default No; start 600s, interval 10s, retry 3;
s: 1..16383, ms: 100..16383000, retry count: 1..32767.
The source does not specify a 100-ms step; do not invent one.
"""
import importlib
import json
import socket

import pytest

from virtual_plc import Server
from virtual_plc.ethernet import EthernetSettings, model_catalog, reference_catalog
from virtual_plc.guide import data
from virtual_plc.__main__ import build_parser


@pytest.fixture
def inspect():
    return getattr(importlib.import_module("virtual_plc.ethernet"),
                   "inspect_reference_fx5_enet_alive_timers")


def test_factory_reference_defaults_and_vendor_source(inspect):
    result = inspect()
    assert result["model"] == "fx5_enet"
    assert result["status"] == "OFFICIAL_MANUAL_REFERENCE_ONLY"
    assert result["change_set_timer_value"] is False
    assert result["physical_hardware_certified"] is False
    assert result["simulator_network_affected"] is False
    assert result["source"]["manual"].startswith("SH-082026ENG")
    assert result["source"]["page"] == "70"
    assert result["source"]["url"].startswith("https://")
    p = result["parameters"]
    assert p["start"]["value"] == 600
    assert p["start"]["unit"] == "s"
    assert p["start"]["milliseconds"] == 600000
    assert p["interval"]["value"] == 10
    assert p["interval"]["unit"] == "s"
    assert p["interval"]["milliseconds"] == 10000
    assert p["retry"]["value"] == 3
    assert p["retry"]["unit"] == "count"
    assert all(not field["overridden"] for field in p.values())
    assert json.loads(json.dumps(result)) == result
    assert inspect({}) == result


def test_explicit_change_flag_and_override_provenance(inspect):
    info = inspect({
        "change_set_timer_value": True,
        "start": {"value":600, "unit":"s"},  # same value, explicitly specified
        "interval": {"value":250, "unit":"ms"},
        "retry": 1,
    })
    assert info["change_set_timer_value"] is True
    assert info["parameters"]["start"]["milliseconds"] == 600000
    assert info["parameters"]["start"]["overridden"] is True
    assert info["parameters"]["interval"]["milliseconds"] == 250
    assert info["parameters"]["interval"]["unit"] == "ms"
    assert info["parameters"]["retry"]["value"] == 1
    assert info["parameters"]["retry"]["overridden"] is True
    assert info["parameters"]["start"]["default_milliseconds"] == 600000
    assert info["parameters"]["interval"]["default_milliseconds"] == 10000
    assert info["parameters"]["retry"]["default"] == 3
    assert inspect({"change_set_timer_value": True})["change_set_timer_value"] is True


@pytest.mark.parametrize("unit,minimum,maximum", [
    ("s", 1, 16383),
    ("ms", 100, 16383000),
])
@pytest.mark.parametrize("field", ["start", "interval"])
def test_each_timer_accepts_exact_documented_bounds(inspect, unit, minimum, maximum, field):
    for point in (minimum, maximum):
        result = inspect({"change_set_timer_value": True,
                          field: {"value": point, "unit": unit}})
        assert result["parameters"][field]["milliseconds"] == (
            point * 1000 if unit == "s" else point
        )
        assert result["parameters"][field]["overridden"] is True


@pytest.mark.parametrize("number", [1, 32767])
def test_retry_exact_boundaries(inspect, number):
    result = inspect({"change_set_timer_value": True, "retry": number})
    assert result["parameters"]["retry"]["value"] == number


@pytest.mark.parametrize("value", [None, 0, True, False, "yes", "600", [], {}])
def test_invalid_override_root_or_flag(inspect, value):
    if value is None:
        assert inspect(None) == inspect()
        return
    with pytest.raises(ValueError):
        inspect(value)


@pytest.mark.parametrize("bad", [
    {"unknown": 1},
    {"change_set_timer_value": "yes"},
    {"change_set_timer_value": 1},
    {"start": {"value": 100, "unit": "s"}},
    {"change_set_timer_value": False, "retry": 5},
    {"change_set_timer_value": False, "start": {"value": 1, "unit": "s"}},
    {"change_set_timer_value": True, "start": None},
    {"change_set_timer_value": True, "start": []},
    {"change_set_timer_value": True, "start": {"value": 1}},
    {"change_set_timer_value": True, "start": {"unit": "s"}},
    {"change_set_timer_value": True, "start": {"value": 1, "unit": "s", "extra": 0}},
    {"change_set_timer_value": True, "start": {"value": False, "unit": "s"}},
    {"change_set_timer_value": True, "start": {"value": 1.5, "unit": "s"}},
    {"change_set_timer_value": True, "start": {"value": "10", "unit": "s"}},
    {"change_set_timer_value": True, "start": {"value": 0, "unit": "s"}},
    {"change_set_timer_value": True, "start": {"value": 16384, "unit": "s"}},
    {"change_set_timer_value": True, "interval": {"value": 99, "unit": "ms"}},
    {"change_set_timer_value": True, "interval": {"value": 16383001, "unit": "ms"}},
    {"change_set_timer_value": True, "interval": {"value": 100, "unit": "MS"}},
    {"change_set_timer_value": True, "retry": 0},
    {"change_set_timer_value": True, "retry": 32768},
    {"change_set_timer_value": True, "retry": True},
    {"change_set_timer_value": True, "retry": 3.0},
])
def test_reference_alives_fail_closed_on_malformed_settings(inspect, bad):
    with pytest.raises(ValueError):
        inspect(bad)


def test_input_mutation_cannot_change_snapshot_or_reference_catalog(inspect):
    overrides = {"change_set_timer_value": True,
                 "start": {"value": 120, "unit": "s"}}
    result = inspect(overrides)
    overrides["start"]["value"] = 500
    assert result["parameters"]["start"]["value"] == 120
    assert inspect()["parameters"]["start"]["value"] == 600
    ref = reference_catalog()
    ref["fx5_enet"]["alive_timer_reference"]["start"]["default"] = 999
    assert reference_catalog()["fx5_enet"]["alive_timer_reference"]["start"]["default"] == 600


def test_single_ssot_projection_and_hardware_separation(inspect):
    catalog = reference_catalog()
    assert catalog["fx5_enet"]["alive_timer_reference"]["start"]["default"] == 600
    assert catalog["fx5_enet"]["alive_timer_reference"]["interval"]["default"] == 10
    assert catalog["fx5_enet"]["alive_timer_reference"]["retry"]["default"] == 3
    assert catalog["fx5_enet"]["alive_timer_source"]["page"] == "70"
    assert "alive_timer_reference" not in catalog["fx5_cpu_builtin"]
    assert "alive_timer_reference" not in catalog["rncpu_builtin"]
    assert "fx5_enet" not in model_catalog()
    with pytest.raises(ValueError):
        EthernetSettings("fx5_enet")
    assert data(build_parser(), "ethernet")["reference_only_models"] == catalog
    assert inspect()["source"] == catalog["fx5_enet"]["alive_timer_source"]


def test_no_sockets_or_server_option_mutation(inspect, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("no sockets for reference-only validation")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert inspect()["parameters"]["start"]["milliseconds"] == 600000
    assert inspect({"change_set_timer_value": True,
                    "interval": {"value": 100, "unit": "ms"}})[
                        "simulator_network_affected"] is False
    assert build_parser().get_default("max_clients") == 64
    assert Server.__init__.__defaults__ is not None
