"""TDD: R04CPU CPU-built-in GX Works3 external-device slots and PLC ports.

Mitsubishi SH-081257ENG-AD printed pp.324-326:
CPU built-in setting numbers 1-16; RJ71EN71 network part 1-64.
Own PLC port 1-4999 or 5010-65534, default blank; recommended
1024-4999 or 5010-61439; separate RnCPU system services 5005/6/7.
This is offline reference evidence, not max simultaneous TCP sockets.
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
    # Deferred import permits a true tests-only RED without collection error.
    return getattr(importlib.import_module("virtual_plc.ethernet"),
                   "inspect_reference_rncpu_external_device")


def test_unspecified_connection_and_blank_plc_port_are_not_invented_defaults(inspect):
    report = inspect()
    assert report["model"] == "R04CPU"
    assert report["interface"] == "rncpu_builtin"
    assert report["connection_number"] is None
    assert report["connection_status"] == "UNSPECIFIED"
    assert report["plc_port"] is None
    assert report["plc_port_classification"] == "blank_default"
    assert report["plc_port_configurable"] is True
    assert report["plc_port_recommended"] is False
    assert report["factory_plc_port"] is None
    assert report["simulator_bind_affected"] is False
    assert report["physical_hardware_certified"] is False
    assert report["status"] == "OFFICIAL_MANUAL_REFERENCE_ONLY"
    assert report["connection_range_scope"] == "gxworks3_configured_user_connection_numbers_not_tcp_client_capacity"
    assert json.loads(json.dumps(report)) == report
    assert inspect("R04CPU", None, None) == report


@pytest.mark.parametrize("number", [1, 2, 15, 16])
def test_supported_cpu_configuration_numbers_only(inspect, number):
    result = inspect("R04CPU", number)
    assert result["connection_number"] == number
    assert result["connection_status"] == "CONFIGURATION_SLOT_VALID"
    assert result["user_connection_number_range"] == [1, 16]
    assert result["not_a_simultaneous_tcp_socket_limit"] is True


@pytest.mark.parametrize("bad", [
    -1, 0, 17, 64, 65535, True, False, 1.0, "1", "", [],
    [1], {}, (), object(),
])
def test_invalid_slot_number_is_rejected_without_network_module_fallback(inspect, bad):
    with pytest.raises(ValueError):
        inspect("R04CPU", bad)


@pytest.mark.parametrize("model", [
    "rncpu_builtin", "R08CPU", "R01CPU", "RJ71EN71", "rj71en71",
    "R04ENCPU", "FX5U", "LJ71E71", "", None, False, [], {},
])
def test_unsupported_hardware_must_not_inherit_r04cpu_reference(inspect, model):
    with pytest.raises(ValueError):
        inspect(model, 1, 1024)


@pytest.mark.parametrize("port", [1, 1023, 61443, 61500, 61695])
def test_permitted_but_discouraged_ports_are_not_rejected_as_invalid(inspect, port):
    result = inspect("R04CPU", 16, port)
    assert result["plc_port_classification"] == "permitted_not_recommended"
    assert result["plc_port_configurable"] is True
    assert result["plc_port_recommended"] is False


@pytest.mark.parametrize("port", [1024, 4999, 5010, 61439])
def test_recommended_vendor_own_ports(inspect, port):
    result = inspect("R04CPU", 1, port)
    assert result["plc_port_classification"] == "recommended"
    assert result["plc_port_configurable"] is True
    assert result["plc_port_recommended"] is True


@pytest.mark.parametrize("port", [0, 5000, 5002, 5003, 5004, 65535])
def test_outside_vendor_configurable_range_or_simulator_ephemeral(inspect, port):
    result = inspect("R04CPU", 1, port)
    assert result["plc_port_configurable"] is False
    assert result["plc_port_recommended"] is False
    assert result["plc_port_classification"] == (
        "simulator_only_ephemeral" if port == 0 else "outside_vendor_configurable_range"
    )


@pytest.mark.parametrize("port,service", [
    (20, "ftp_server_data"), (21, "ftp_server_control"),
    (80, "web_server"), (123, "sntp_client"),
    (5001, "melsoft_udp"), (5005, "auto_open_udp"),
    (5006, "melsoft_udp"), (5007, "melsoft_tcp"),
    (5008, "melsoft_direct_udp"), (5009, "network_module_search_udp"),
    (61440, "iqss_data_udp"), (61441, "slmp_snd_udp"),
    (61442, "iqss_backup_restore_udp"), (61448, "dns_client_udp"),
    (61450, "cc_link_field_basic_udp"), (61461, "database_access_udp"),
    (61696, "simple_cpu_communication_udp"),
    (61999, "simple_cpu_communication_udp"),
    (62000, "ftp_client_dynamic_tcp"),
    (65534, "ftp_client_dynamic_tcp"),
])
def test_existing_system_service_ports_never_become_configurable_user_ports(inspect, port, service):
    result = inspect("R04CPU", 1, port)
    assert result["plc_port_classification"] == "system_service_port_not_user_configurable"
    assert result["system_service"] == service
    assert result["system_port_source"]["page"] == "554"
    assert result["plc_port_configurable"] is False
    assert result["plc_port_recommended"] is False
    assert result["simulator_bind_affected"] is False


@pytest.mark.parametrize("port", [
    -1, 65536, 99999, True, False, 1.0, "", "5005", "1024", [],
    [1024], {}, object(),
])
def test_wrong_port_types_and_values_fail_closed(inspect, port):
    with pytest.raises(ValueError):
        inspect("R04CPU", 1, port)


def test_scopes_source_of_truth_and_network_part_difference(inspect):
    c = reference_catalog()
    r = c["rncpu_builtin"]["external_device_configuration_reference"]
    assert r["factory_model_scope"] == "R04CPU_GXWORKS3_CPU_BUILTIN_EXAMPLE"
    assert r["connection_number_range"] == [1, 16]
    assert r["plc_port_ranges"] == [[1, 4999], [5010, 65534]]
    assert r["plc_port_recommended_ranges"] == [[1024, 4999], [5010, 61439]]
    assert r["factory_plc_port"] is None
    assert r["system_port_source"]["page"] == "554"
    assert r["system_service_ports"]["5001"] == "melsoft_udp"
    assert r["system_service_ports"]["61441"] == "slmp_snd_udp"
    assert r["system_port_ranges"] == [
        {"start": 61696, "end": 61999,
         "service": "simple_cpu_communication_udp"},
        {"start": 62000, "end": 65534,
         "service": "ftp_client_dynamic_tcp"},
    ]
    assert r["source"]["manual"] == "SH-081257ENG-AD"
    assert r["source"]["page"] == "324-326"
    assert r["source"]["url"].endswith("/sh081257engad.pdf")
    assert "external_device_configuration_reference" not in c["fx5_enet"]
    assert "external_device_configuration_reference" not in c["fx5_cpu_builtin"]
    assert "rncpu_builtin" not in model_catalog()
    assert set(model_catalog()) == {"qj71e71", "lj71e71", "rj71en71"}
    with pytest.raises(ValueError):
        EthernetSettings("rncpu_builtin")
    assert data(build_parser(), "ethernet")["reference_only_models"] == c
    assert inspect("R04CPU", 16, 61439)["source"] == r["source"]


def test_independent_defensive_copies_do_not_mutate_ssot(inspect):
    c = reference_catalog()
    c["rncpu_builtin"]["external_device_configuration_reference"]["connection_number_range"][1] = 999
    c["rncpu_builtin"]["reference"]["auto_open_udp"] = 1234
    assert inspect("R04CPU", 16, 5005)["system_service"] == "auto_open_udp"
    assert inspect("R04CPU", 16, 1024)["user_connection_number_range"] == [1, 16]
    result = inspect()
    result["source"]["manual"] = "FAKE"
    result["user_connection_number_range"][1] = 900
    assert inspect()["source"]["manual"] == "SH-081257ENG-AD"
    assert inspect()["user_connection_number_range"] == [1, 16]


def test_offline_preflight_never_opens_socket_or_changes_simulator(monkeypatch, inspect):
    def forbidden(*args, **kwargs):
        raise AssertionError("must remain offline")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    for number, port in [(None, None), (1, 5005), (16, 65535), (16, 61439)]:
        result = inspect("R04CPU", number, port)
        assert result["simulator_bind_affected"] is False
    assert build_parser().get_default("max_clients") == 64
    assert Server.__init__.__defaults__ is not None
