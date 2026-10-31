"""RED-first, model-scoped GX Works3 FX5 SLMP port reference preflight.

The vendor port table is REFERENCE ONLY. No runtime socket binding or
physical FX5 hardware is touched. Official manuals SH-082625ENG-H p.100
and SH-082026ENG-H p.79; service-specific count FAQ #40032.
"""
import importlib
import json

import pytest

from virtual_plc import Server
from virtual_plc.ethernet import EthernetSettings, reference_catalog, model_catalog
from virtual_plc.__main__ import build_parser
from virtual_plc.guide import data


@pytest.fixture
def inspect():
    # Defer new helper lookup so TDD RED does not break test collection.
    return getattr(importlib.import_module("virtual_plc.ethernet"),
                   "inspect_reference_slmp_port")


@pytest.mark.parametrize("model", ["fx5_cpu_builtin", "fx5_enet"])
@pytest.mark.parametrize("port,classification,permitted,recommended", [
    (0, "simulator_only_ephemeral", False, False),
    (1, "permitted_not_recommended", True, False),
    (80, "permitted_not_recommended", True, False),
    (1023, "permitted_not_recommended", True, False),
    (1024, "recommended", True, True),
    (5000, "recommended", True, True),
    (5548, "recommended", True, True),
    (5549, "vendor_system_reserved", False, False),
    (5559, "vendor_system_reserved", False, False),
    (5569, "vendor_system_reserved", False, False),
    (5570, "recommended", True, True),
    (61439, "recommended", True, True),
    (61440, "permitted_not_recommended", True, False),
    (65534, "permitted_not_recommended", True, False),
    (65535, "outside_vendor_range", False, False),
])
def test_fx5_slmp_port_classification_is_reference_only(
        inspect, model, port, classification, permitted, recommended):
    result = inspect(model, port)
    assert result["model"] == model
    assert result["port"] == port
    assert result["classification"] == classification
    assert result["permitted"] is permitted
    assert result["recommended"] is recommended
    assert result["status"] == "OFFICIAL_MANUAL_REFERENCE_ONLY"
    assert result["physical_hardware_certified"] is False
    assert result["simulator_bind_affected"] is False
    assert result["source"]["url"].startswith("https://")
    assert result["source"]["page"] in ("100", "79")
    assert "5549" in result["note"] or "reference" in result["note"].lower()
    assert json.loads(json.dumps(result)) == result


@pytest.mark.parametrize("value", [None, False, True, -1, 65536, 5000.0, "5000", [], {}])
def test_fx5_port_rejects_wrong_types_and_outside_tcp_port_space(inspect, value):
    with pytest.raises(ValueError):
        inspect("fx5_enet", value)


@pytest.mark.parametrize("model", [None, "", "unknown", "rncpu_builtin",
                                    "qj71e71", "lj71e71", "rj71en71"])
def test_preflight_is_not_misrepresented_as_a_universal_ethernet_rule(inspect, model):
    with pytest.raises(ValueError):
        inspect(model, 5000)


def test_reference_catalog_uses_exact_manual_ranges_and_keeps_models_unrunnable():
    catalog = reference_catalog()
    assert set(catalog) == {"fx5_cpu_builtin", "fx5_enet", "rncpu_builtin"}
    for model, page in (("fx5_cpu_builtin", "100"), ("fx5_enet", "79")):
        record = catalog[model]
        assert record["implementation"] == "research_only"
        assert record["reference"]["vendor_port_ranges"] == [[1, 5548], [5570, 65534]]
        assert record["reference"]["vendor_port_recommended_ranges"] == [
            [1024, 5548], [5570, 61439],
        ]
        assert record["reference"]["vendor_reserved_port_range"] == [5549, 5569]
        assert record["port_source"]["page"] == page
        assert record["port_source"]["url"].startswith("https://")
        assert model not in model_catalog()
        with pytest.raises(ValueError):
            EthernetSettings(model)


def test_cpu_slmp_8_connections_must_not_absorb_simple_cpu_communication_16():
    cpu = reference_catalog()["fx5_cpu_builtin"]
    assert cpu["reference"]["connection_limit"] == 8
    assert cpu["reference"]["slmp_server_frames"] == ["1E", "3E"]
    special = cpu["service_specific_connection_reference"]
    assert special["feature"] == "simple_cpu_communication"
    assert special["target_limits"] == {
        "FX5U": 16, "FX5UC": 16, "FX5UJ": 8, "FX5S": 8,
    }
    assert special["status"] == "OFFICIAL_MANUAL_REFERENCE_ONLY"
    assert special["source"]["url"].endswith("/40032")
    assert "not" in special["scope"].lower()
    assert reference_catalog()["fx5_enet"]["reference"]["connection_limit"] == 32
    assert "service_specific_connection_reference" not in reference_catalog()["fx5_enet"]


def test_reference_catalog_is_defensively_copied_and_projected_in_guide():
    original = reference_catalog()
    original["fx5_cpu_builtin"]["reference"]["vendor_port_ranges"][0][0] = 9000
    original["fx5_cpu_builtin"]["service_specific_connection_reference"]["target_limits"]["FX5U"] = 999
    original["fx5_enet"]["port_source"]["page"] = "wrong"
    again = reference_catalog()
    assert again["fx5_cpu_builtin"]["reference"]["vendor_port_ranges"][0][0] == 1
    assert again["fx5_cpu_builtin"]["service_specific_connection_reference"]["target_limits"]["FX5U"] == 16
    assert again["fx5_enet"]["port_source"]["page"] == "79"
    guide = data(build_parser(), "ethernet")
    assert guide["reference_only_models"] == again
    assert set(guide["models"]) == set(model_catalog())


def test_model_reference_checks_do_not_change_legacy_port_zero_or_max_clients(inspect):
    assert inspect("fx5_cpu_builtin", 0)["permitted"] is False
    assert build_parser().get_default("max_clients") == 64
    with Server(port=0) as plc:
        assert plc.address[1] > 0
        assert plc.ethernet is None
    assert set(model_catalog()) == {"qj71e71", "lj71e71", "rj71en71"}


def test_offline_reference_inspection_never_creates_sockets(inspect, monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("reference-only preflight must never touch sockets")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_server", forbidden)
    for model in ("fx5_cpu_builtin", "fx5_enet"):
        for port in (0, 5000, 5550, 65534):
            assert inspect(model, port)["simulator_bind_affected"] is False
