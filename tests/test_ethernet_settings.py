"""GX Works2/3 model-scoped Ethernet defaults, overrides, and MC policies (#14)."""

import json
import socket

import pytest

from test_m1_server_raw import device_data, exchange, request
from test_m3_m4_raw import packet
from virtual_plc.__main__ import main
from virtual_plc.ethernet import EthernetSettings, model_catalog
from virtual_plc.server import Server


@pytest.mark.parametrize("model,profile", [("qj71e71", "Q"), ("rj71en71", "iQ-R")])
def test_manual_timer_factory_defaults_and_provenance(model, profile):
    settings = EthernetSettings(model)
    report = settings.report()
    assert settings.profile == profile
    assert report["model"] == model
    assert report["profile"] == profile
    assert report["parameters"]["tcp_ulp_ms"]["value"] == 30000
    assert report["parameters"]["response_monitor_ms"]["value"] == 30000
    assert report["parameters"]["tcp_resend_ms"]["value"] == 10000
    assert report["parameters"]["tcp_zero_window_ms"]["value"] == 10000
    assert report["parameters"]["tcp_end_ms"]["value"] == 20000
    assert report["parameters"]["ip_assembly_ms"]["value"] == 5000
    assert report["parameters"]["alive_start_ms"]["value"] == 600000
    assert report["parameters"]["alive_interval_ms"]["value"] == 10000
    assert report["parameters"]["alive_retries"]["value"] == 3
    for field in report["parameters"].values():
        assert field["source"]["manual"].startswith("SH-")
        assert field["source"]["page"]
        assert field["effect"] in ("reference_only", "simulated")
        assert field["value"] == field["default"]
    assert report["parameters"]["communication_data_code"]["value"] == "binary"
    assert report["parameters"]["allow_write_during_run"]["value"] is False
    assert report["parameters"]["tcp_ulp_ms"]["effect"] == "reference_only"
    assert report["parameters"]["communication_data_code"]["effect"] == "simulated"
    assert report["parameters"]["allow_write_during_run"]["effect"] == "simulated"
    assert settings.report() == json.loads(json.dumps(settings.report()))


def test_model_specific_timer_units_and_ranges():
    q = EthernetSettings("qj71e71")
    r = EthernetSettings("rj71en71")
    assert q.report()["parameters"]["tcp_ulp_ms"]["step"] == 500
    assert r.report()["parameters"]["tcp_ulp_ms"]["step"] == 100
    assert q.report()["parameters"]["alive_retries"]["max"] == 32767
    assert r.report()["parameters"]["alive_retries"]["max"] == 99999
    assert r.report()["parameters"]["tcp_resend_ms"]["min"] == 100


def test_override_updates_single_field_without_mutating_factory_defaults():
    changes = {"timers": {"tcp_ulp_ms": 35000, "response_monitor_ms": 35000},
               "communication_data_code": "ascii", "allow_write_during_run": True}
    new = EthernetSettings("qj71e71", changes)
    report = new.report()
    assert report["parameters"]["tcp_ulp_ms"]["value"] == 35000
    assert report["parameters"]["tcp_ulp_ms"]["default"] == 30000
    assert report["parameters"]["tcp_ulp_ms"]["overridden"] is True
    assert report["parameters"]["tcp_resend_ms"]["overridden"] is False
    assert report["parameters"]["communication_data_code"]["value"] == "ascii"
    assert report["parameters"]["allow_write_during_run"]["value"] is True
    changes["timers"]["tcp_ulp_ms"] = 999999
    assert new.values["tcp_ulp_ms"] == 35000
    assert EthernetSettings("qj71e71").values["tcp_ulp_ms"] == 30000


@pytest.mark.parametrize("model,overrides", [
    ("unknown", {}),
    ("qj71e71", []),
    ("qj71e71", {"unknown": 1}),
    ("qj71e71", {"timers": {"typo": 10000}}),
    ("qj71e71", {"timers": {"tcp_ulp_ms": True}}),
    ("qj71e71", {"timers": {"tcp_ulp_ms": 100}}),
    ("qj71e71", {"timers": {"tcp_ulp_ms": 1001}}),
    ("qj71e71", {"timers": {"alive_retries": 0}}),
    ("qj71e71", {"timers": {"alive_retries": 32768}}),
    ("rj71en71", {"timers": {"tcp_ulp_ms": 101}}),
    ("rj71en71", {"timers": {"tcp_ulp_ms": 0}}),
    ("rj71en71", {"timers": {"tcp_ulp_ms": 16383100}}),
    ("rj71en71", {"timers": {"alive_retries": 100000}}),
    ("qj71e71", {"communication_data_code": "auto"}),
    ("qj71e71", {"allow_write_during_run": 1}),
    ("rj71en71", {"timers": {"tcp_resend_ms": 20000}}),
    ("rj71en71", {"timers": {"response_monitor_ms": 10000}}),
])
def test_unknown_and_out_of_range_config_rejected_before_bind(model, overrides):
    with pytest.raises(ValueError):
        EthernetSettings(model, overrides)


def test_model_catalog_is_json_and_no_claim_that_reference_timers_are_applied():
    data = model_catalog()
    assert set(data) == {"qj71e71", "lj71e71", "rj71en71"}
    assert all(spec["source"]["url"].startswith("https://") for spec in data.values())
    assert all(spec["parameters"]["tcp_resend_ms"]["effect"] == "reference_only"
               for spec in data.values())
    assert "tcp_ulp_ms" in json.dumps(data)


def test_profile_mismatch_fails_before_socket_bind():
    with pytest.raises(ValueError, match="profile"):
        Server(profile="Q", ethernet_model="rj71en71")
    with pytest.raises(ValueError, match="profile"):
        Server(profile="iQ-R", ethernet_model="qj71e71")
    with pytest.raises(ValueError, match="ethernet_model"):
        Server(ethernet_overrides={"timers": {"tcp_ulp_ms": 40000}})


def test_legacy_without_model_still_allows_binary_ascii_and_run_writes():
    with Server(port=0) as server:
        with socket.create_connection(server.address, timeout=2) as connection:
            connection.settimeout(2)
            assert exchange(connection, request(0x1401, data=device_data(payload=b"\x67\x45")))[0] == 0
            assert exchange(connection, request(data=device_data())) == (0, b"\x67\x45")
            connection.sendall(packet("3E", "ascii", 0x0401))
            assert connection.recv(4) == b"D000"


def test_model_run_write_gate_blocks_and_does_not_mutate_on_all_listeners():
    with Server(profile="Q", ethernet_model="qj71e71",
                listeners=[("tcp", 0), ("tcp", 0), ("udp", 0)]) as server:
        a, b, u = server.addresses
        with socket.create_connection(a[1:], timeout=2) as conn:
            conn.settimeout(2)
            code, _ = exchange(conn, request(0x1401, data=device_data(payload=b"\x34\x12")))
            assert code == 0x0055
        with socket.create_connection(b[1:], timeout=2) as conn:
            conn.settimeout(2)
            assert exchange(conn, request(data=device_data())) == (0, b"\x00\x00")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(2)
            udp.sendto(request(0x1401, data=device_data(payload=b"\x34\x12")), u[1:])
            answer = udp.recvfrom(8192)[0]
            assert answer[9:11] == b"\x55\x00"
        assert server.memory.read_words("D", 0, 1) == [0]


def test_optin_model_stopped_allows_write_and_enabled_run_override():
    with Server(ethernet_model="qj71e71", initial_state="STOP") as s:
        with socket.create_connection(s.address, timeout=2) as c:
            c.settimeout(2)
            assert exchange(c, request(0x1401, data=device_data(payload=b"\x02\x00")))[0] == 0
    with Server(ethernet_model="qj71e71",
                ethernet_overrides={"allow_write_during_run": True}) as s:
        with socket.create_connection(s.address, timeout=2) as c:
            c.settimeout(2)
            assert exchange(c, request(0x1401, data=device_data(payload=b"\x03\x00")))[0] == 0


def test_model_code_mode_rejects_ascii_tcp_and_udp_without_changing_memory():
    with Server(ethernet_model="qj71e71", listeners=[("tcp", 0), ("udp", 0)]) as server:
        with socket.create_connection(server.address, timeout=2) as conn:
            conn.settimeout(2)
            conn.sendall(packet("3E", "ascii", 0x1401, data=b"D*00000000011234"))
            assert conn.recv(1) == b""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(0.08)
            udp.sendto(packet("3E", "ascii"), server.addresses[1][1:])
            with pytest.raises(socket.timeout):
                udp.recvfrom(8192)
        assert server.memory.read_words("D", 0, 1) == [0]


def test_ascii_override_rejects_binary_and_accepts_ascii():
    with Server(ethernet_model="qj71e71",
                ethernet_overrides={"communication_data_code": "ascii"}) as server:
        with socket.create_connection(server.address, timeout=2) as conn:
            conn.settimeout(2)
            conn.sendall(request(data=device_data()))
            assert conn.recv(1) == b""
        with socket.create_connection(server.address, timeout=2) as conn:
            conn.settimeout(2)
            conn.sendall(packet("3E", "ascii"))
            assert conn.recv(4) == b"D000"


def test_cli_effective_config_inspection_and_guide_json(tmp_path, monkeypatch, capsys):
    from virtual_plc import __main__ as cli

    path = tmp_path / "ethernet.json"
    path.write_text(json.dumps({"timers": {"tcp_ulp_ms": 35000,
                                         "response_monitor_ms": 35000},
                                "communication_data_code": "ascii",
                                "allow_write_during_run": True}), encoding="utf-8")
    monkeypatch.setattr(cli.Server, "start", lambda *_: pytest.fail("inspection must not bind"))
    assert main(["--ethernet-model", "qj71e71", "--ethernet-config", str(path),
                 "--show-effective-ethernet"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["parameters"]["tcp_ulp_ms"]["value"] == 35000
    assert report["parameters"]["communication_data_code"]["value"] == "ascii"
    assert report["parameters"]["allow_write_during_run"]["value"] is True
    assert main(["guide", "ethernet", "--json"]) == 0
    guide = json.loads(capsys.readouterr().out)
    assert set(guide["models"]) == {"qj71e71", "lj71e71", "rj71en71"}


@pytest.mark.parametrize("config", [{"unexpected": 1}, {"timers": {"tcp_ulp_ms": 10}},
                                    {"allow_write_during_run": "yes"}])
def test_cli_invalid_ethernet_config_fails_before_binding(tmp_path, capsys, config):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(["--ethernet-model", "qj71e71", "--ethernet-config", str(path),
              "--show-effective-ethernet"])
    assert error.value.code == 2
    assert "guide ethernet" in capsys.readouterr().err


def test_cli_requires_model_for_ethernet_configuration(capsys):
    with pytest.raises(SystemExit) as err:
        main(["--ethernet-config", "whatever.json", "--show-effective-ethernet"])
    assert err.value.code == 2
    assert "guide ethernet" in capsys.readouterr().err
