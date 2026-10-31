"""RnCPU built-in Ethernet *service-specific* connection facts.

Manufacturer FAQs:
- #20230: RCPU partner for simple CPU communication uses auto-open UDP
  with no additional partner-side configuration.
- #45267: multiple GOTs to iQ-R built-in port: TCP needs GX Works3
  External Device Configuration per GOT, UDP needs no open setting.
This MUST NOT activate MELSOFT/GOT services or synthesize SLMP policies.
"""
import json
import socket

import pytest

from virtual_plc import Server
from virtual_plc.__main__ import build_parser
from virtual_plc.ethernet import EthernetSettings, reference_catalog, model_catalog
from virtual_plc.guide import data


def test_rncpu_simple_cpu_peer_auto_open_udp_no_extra_setting():
    entry = reference_catalog()["rncpu_builtin"]["service_connection_reference"]
    simple = entry["simple_cpu_communication_partner"]
    assert simple["transport"] == "udp"
    assert simple["auto_open_udp"] is True
    assert simple["requires_additional_open_setting"] is False
    assert simple["role"] == "receiving_rncpu_builtin_ethernet_partner"
    assert simple["status"] == "OFFICIAL_FAQ_REFERENCE_ONLY"
    assert simple["source"]["url"] == "https://fa-faq.mitsubishielectric.co.jp/faq/show/20230"
    assert simple["source"]["faq_id"] == 20230
    assert "SLMP" not in simple["role"]


def test_rncpu_got_tcp_needs_per_got_external_device_config():
    got = reference_catalog()["rncpu_builtin"]["service_connection_reference"]["multiple_got"]
    tcp = got["by_transport"]["tcp"]
    assert tcp["requires_external_device_configuration"] is True
    assert tcp["configure_each_got"] is True
    assert tcp["gxworks3_path"] == [
        "Navigation Window", "Parameter", "RnCPU", "Module parameter",
        "Basic Settings", "External Device Configuration",
        "Detail settings", "Ethernet configuration (built-in Ethernet port)",
    ]
    assert got["source"]["faq_id"] == 45267
    assert got["source"]["url"] == "https://fa-faq.mitsubishielectric.com/faq/show/45267"
    assert got["status"] == "OFFICIAL_FAQ_REFERENCE_ONLY"


def test_rncpu_got_udp_does_not_require_open_setting():
    got = reference_catalog()["rncpu_builtin"]["service_connection_reference"]["multiple_got"]
    udp = got["by_transport"]["udp"]
    assert udp["requires_external_device_configuration"] is False
    assert udp["configure_each_got"] is False
    assert udp["gxworks3_path"] is None
    assert got["scope"] == "multiple_got_to_one_rncpu_builtin_ethernet_port"
    assert got["by_transport"]["udp"] != got["by_transport"]["tcp"]


def test_reference_scope_does_not_enable_vendor_ports_or_simulator():
    cat = reference_catalog()
    rncpu = cat["rncpu_builtin"]
    assert rncpu["implementation"] == "research_only"
    assert rncpu["reference"]["auto_open_udp"] == 5005  # independent existing manual citation
    assert rncpu["reference"]["melsoft_udp"] == 5006
    assert rncpu["reference"]["melsoft_tcp"] == 5007
    service = rncpu["service_connection_reference"]
    assert service["simulator_network_affected"] is False
    assert service["physical_hardware_certified"] is False
    assert service["applicability"] == "rncpu_builtin_only"
    assert "service_connection_reference" not in cat["fx5_cpu_builtin"]
    assert "service_connection_reference" not in cat["fx5_enet"]
    assert "rncpu_builtin" not in model_catalog()
    with pytest.raises(ValueError):
        EthernetSettings("rncpu_builtin")


def test_defensive_immutable_catalog_projection():
    cat = reference_catalog()
    original = json.loads(json.dumps(cat))
    cat["rncpu_builtin"]["service_connection_reference"]["multiple_got"][
        "by_transport"]["tcp"]["gxworks3_path"][0] = "unsafe"
    cat["rncpu_builtin"]["service_connection_reference"]["simple_cpu_communication_partner"][
        "auto_open_udp"] = False
    assert reference_catalog() == original
    guide = data(build_parser(), "ethernet")
    assert guide["reference_only_models"] == original
    assert set(guide["models"]) == {"qj71e71", "lj71e71", "rj71en71"}


def test_no_automatic_rncpu_or_got_listeners_or_socket_access(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("reference metadata cannot access networks")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    catalog = reference_catalog()
    assert catalog["rncpu_builtin"]["service_connection_reference"][
        "simulator_network_affected"] is False
    assert build_parser().get_default("max_clients") == 64
    assert Server.__init__.__defaults__ is not None
