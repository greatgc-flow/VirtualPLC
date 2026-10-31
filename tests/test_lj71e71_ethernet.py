"""Official MELSEC-L LJ71E71-100 Ethernet setting contract.

SH-081105ENG-G pp.35-36 gives E71 buffer defaults in 500ms ticks and
initial operation data-code/RUN-write flags. These tests do not assert
physical-device parity for the simulator's chosen error/close semantics.
"""

import socket

import pytest

from test_m1_server_raw import device_data, exchange, request
from virtual_plc.ethernet import EthernetSettings, model_catalog
from virtual_plc.server import Server


L_DEFAULTS = {
    "tcp_ulp_ms": 30000, "tcp_zero_window_ms": 10000,
    "tcp_resend_ms": 10000, "tcp_end_ms": 20000,
    "ip_assembly_ms": 5000, "response_monitor_ms": 30000,
    "alive_start_ms": 600000, "alive_interval_ms": 10000,
    "alive_retries": 3,
}


def test_l_e71_has_own_official_source_and_correct_defaults():
    cfg = EthernetSettings("lj71e71")
    assert cfg.profile == "L"
    report = cfg.report()
    assert report["model"] == "lj71e71"
    assert report["editor"] == "GX Works2"
    assert report["source"]["manual"] == "SH-081105ENG"
    assert "sh081105engg.pdf" in report["source"]["url"]
    assert report["vendor_ports_reference_only"]["auto_open_udp"] == 5000
    for key, expected in L_DEFAULTS.items():
        field = report["parameters"][key]
        assert (field["default"], field["value"], field["effect"]) == (
            expected, expected, "reference_only")
        assert field["source"]["manual"] == "SH-081105ENG"
        assert field["source"]["page"]
    assert report["parameters"]["tcp_ulp_ms"]["step"] == 500
    assert report["parameters"]["ip_assembly_ms"]["max"] == 16383000
    assert report["parameters"]["alive_retries"]["max"] == 32767
    assert report["parameters"]["communication_data_code"]["default"] == "binary"
    assert report["parameters"]["allow_write_during_run"]["default"] is False
    assert report["parameters"]["allow_write_during_run"]["effect"] == "simulated"


def test_l_profile_keeps_independent_model_identity_and_legacy_unchanged():
    catalog = model_catalog()
    assert set(catalog) >= {"lj71e71", "qj71e71", "rj71en71"}
    assert catalog["lj71e71"]["source"]["manual"] != catalog["qj71e71"]["source"]["manual"]
    with pytest.raises(ValueError, match="profile"):
        Server(profile="Q", ethernet_model="lj71e71")
    with Server(profile="L", port=0) as legacy:
        with socket.create_connection(legacy.address, timeout=2) as client:
            client.settimeout(2)
            assert exchange(client, request(0x1401, data=device_data(
                payload=b"\\x05\\x00")))[0] == 0


@pytest.mark.parametrize("value", [0, 501, 999, 16384000, True, "35000"])
def test_l_e71_enforces_500ms_granularity_and_type(value):
    with pytest.raises(ValueError):
        EthernetSettings("lj71e71", {"timers": {"tcp_ulp_ms": value}})


def test_l_e71_overrides_and_same_model_state_across_tcp_listeners():
    cfg = EthernetSettings("lj71e71", {"timers": {
        "tcp_ulp_ms": 35000, "response_monitor_ms": 35000},
        "allow_write_during_run": True})
    assert cfg.report()["parameters"]["tcp_ulp_ms"]["value"] == 35000
    assert cfg.report()["parameters"]["tcp_ulp_ms"]["default"] == 30000
    assert cfg.report()["parameters"]["tcp_ulp_ms"]["overridden"] is True

    with Server(profile="L", ethernet_model="lj71e71",
                ethernet_overrides={"allow_write_during_run": True},
                listeners=[("tcp", 0), ("tcp", 0)]) as server:
        a, b = server.addresses
        with socket.create_connection(a[1:], timeout=2) as writer:
            writer.settimeout(2)
            assert exchange(writer, request(0x1401, data=device_data(
                payload=b"\\x19\\x00")))[0] == 0
        with socket.create_connection(b[1:], timeout=2) as reader:
            reader.settimeout(2)
            assert exchange(reader, request(data=device_data())) == (0, b"\\x19\\x00")


def test_l_e71_run_write_default_rejects_while_stop_allows():
    with Server(profile="L", ethernet_model="lj71e71") as server:
        with socket.create_connection(server.address, timeout=2) as client:
            client.settimeout(2)
            code, _ = exchange(client, request(0x1401, data=device_data(
                payload=b"\\x03\\x00")))
            assert code == 0x0055
        assert server.memory.read_words("D", 0, 1) == [0]
    with Server(profile="L", ethernet_model="lj71e71", initial_state="STOP") as server:
        with socket.create_connection(server.address, timeout=2) as client:
            client.settimeout(2)
            code, _ = exchange(client, request(0x1401, data=device_data(
                payload=b"\\x03\\x00")))
            assert code == 0
