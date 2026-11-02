"""UDP-only datagram response faults: opt-in drop and delay (#13).

No physical PLC, no production network, no assumptions about datagram
arrival timing. Every socket uses loopback + port 0.
"""

import json
import socket
import threading
from types import SimpleNamespace

import pytest

from test_m1_server_raw import device_data, exchange, request
from test_m3_m4_raw import packet
from test_slmp_1e import req as one_e_request
from virtual_plc import Server
from virtual_plc.codec import decode_request, encode_response


def plan(steps):
    from virtual_plc.udp_faults import UdpFaultPlan
    return UdpFaultPlan(steps)


def recv_udp(sock, frame, target):
    sock.sendto(frame, target)
    return sock.recvfrom(8192)[0]


@pytest.mark.parametrize("steps", [
    None, {}, ({"action": {"type": "drop"}},),
    [{"action": {"type": "rst"}}],
    [{"action": {"type": "partial_send", "chunks": [1]}}],
    [{"action": {"type": "duplicate"}}],
    [{"action": {"type": "delay", "seconds": -1}}],
    [{"action": {"type": "delay", "seconds": float("nan")}}],
    [{"action": {"type": "delay", "seconds": True}}],
    [{"action": {"type": "delay", "seconds": "1"}}],
    [{"action": {"type": "drop"}, "times": 0}],
    [{"action": {"type": "drop"}, "times": True}],
    [{"action": {"type": "drop"}, "match": {"nth": 0}}],
    [{"action": {"type": "drop"}, "match": {"peer": "not-an-ip"}}],
    [{"action": {"type": "drop"}, "match": {"connection": 1}}],
    [{"action": {"type": "drop"}, "match": {"command": True}}],
    [{"action": {"type": "drop"}, "action2": {"type": "delay"}}],
    [{"action": {"type": "drop", "seconds": 1}}],
])
def test_udp_plan_rejects_non_datagram_actions_and_invalid_fields(steps):
    with pytest.raises(ValueError):
        plan(steps)


def test_udp_plan_matching_copy_exhaustion_and_ordinals():
    steps = [{
        "match": {"command": "0x1401", "nth": 2, "peer": "127.0.0.1"},
        "times": 2,
        "action": {"type": "drop"},
    }, {"action": {"type": "delay", "seconds": 0}}]
    faults = plan(steps)
    steps[0]["action"]["type"] = "rst"
    assert faults.select(0x0401, peer="127.0.0.1") == {"type": "delay", "seconds": 0}
    assert faults.select(0x1401, peer="127.0.0.1") == {"type": "drop"}
    assert faults.select(0x1401, peer="127.0.0.1") is None
    assert faults.select(0x1401, peer="127.0.0.1") is None


def test_udp_plan_empty_and_server_preflight():
    from virtual_plc.udp_faults import UdpFaultPlan
    from virtual_plc.faults import FaultPlan
    with Server(listeners=[("udp", 0)], udp_fault_plan=UdpFaultPlan([])):
        pass
    with pytest.raises(ValueError, match="UDP"):
        Server(listeners=[("tcp", 0)], udp_fault_plan=UdpFaultPlan([]))
    with pytest.raises(ValueError, match="udp_fault_plan"):
        Server(listeners=[("udp", 0)], udp_fault_plan=FaultPlan([]))
    with pytest.raises(ValueError, match="TCP fault"):
        Server(listeners=[("tcp", 0), ("udp", 0)], fault_plan=FaultPlan([]))


def test_udp_drop_postdispatch_and_tcp_unaffected():
    """A dropped UDP write response is not a dropped PLC write."""
    from virtual_plc.udp_faults import UdpFaultPlan
    faults = UdpFaultPlan([{"match": {"command": "0x1401", "nth": 1},
                            "action": {"type": "drop"}}])
    with Server(listeners=[("tcp", 0), ("udp", 0)],
                udp_fault_plan=faults) as server:
        _, host, port = server.addresses[1]
        write = packet("3E", "binary", 0x1401,
                       data=device_data(payload=b"\x34\x12"))
        read = packet("4E", "binary", serial=0x3344)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(0.08)
            client.sendto(write, (host, port))
            with pytest.raises(socket.timeout):
                client.recvfrom(8192)
            with socket.create_connection(server.address, timeout=2) as tcp:
                assert exchange(tcp, request(data=device_data())) == (0, b"\x34\x12")
            client.settimeout(2)
            assert recv_udp(client, read, (host, port)) == encode_response(
                decode_request(read), data=b"\x34\x12")


def test_udp_delay_zero_and_first_matching_action():
    faults = plan([{"match": {"nth": 1}, "times": 1,
                    "action": {"type": "delay", "seconds": 0}}])
    with Server(listeners=[("udp", 0)], udp_fault_plan=faults) as server:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            frame = packet("4E", "ascii", serial=0x1234)
            expected = encode_response(decode_request(frame), data=b"0000")
            assert recv_udp(client, frame, server.address) == expected
            assert recv_udp(client, frame, server.address) == expected


def test_udp_delay_cancelled_by_stop_and_fresh_restart(monkeypatch):
    from virtual_plc.udp_faults import UdpFaultPlan
    selected = threading.Event()
    response_hook_called = threading.Event()
    faults = UdpFaultPlan([{"action": {"type": "delay", "seconds": 30}}])
    original = faults.select

    def select(*args, **kwargs):
        choice = original(*args, **kwargs)
        selected.set()
        return choice

    monkeypatch.setattr(faults, "select", select)
    server = Server(listeners=[("udp", 0)], udp_fault_plan=faults,
                    response_hook=lambda response: (
                        response_hook_called.set() or response))
    server.start()
    frame = packet("3E", "binary")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(frame, server.address)
            assert response_hook_called.wait(3)
            assert selected.wait(3)
            server.stop()  # must cancel 30-second delay rather than block
            assert server._listener_threads == []
            client.settimeout(0.08)
            with pytest.raises(socket.timeout):
                client.recvfrom(8192)
        server.start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            assert recv_udp(client, frame, server.address) == encode_response(
                decode_request(frame), data=b"\x00\x00")
    finally:
        server.stop()


@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_udp_1e_drop_response_no_mixed_parser(wire):
    from virtual_plc.udp_faults import UdpFaultPlan
    faults = UdpFaultPlan([{"match": {"command": 0x03, "peer": "127.0.0.1"},
                            "action": {"type": "drop"}}])
    payload = b"\x34\x12" if wire == "binary" else b"1234"
    frame = one_e_request(3, wire=wire, head=0, count=1, payload=payload)
    with Server(slmp_1e=True, listeners=[("udp", 0)],
                udp_fault_plan=faults) as server:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(0.08)
            client.sendto(frame, server.address)
            with pytest.raises(socket.timeout):
                client.recvfrom(8192)
            assert server.memory.read_words("D", 0, 1) == [0x1234]


def test_udp_fault_cli_plan_option_and_invalid_file(tmp_path, monkeypatch, capsys):
    from virtual_plc import __main__ as cli
    contents = {"steps": [{"action": {"type": "drop"}}]}
    path = tmp_path / "udp.json"
    path.write_text(json.dumps(contents), encoding="utf-8")
    seen = []

    class DummyServer:
        def __init__(self, host, port, **options):
            seen.append(options)
            self.address = (host, 15111)
            self.addresses = [("udp", host, 15111)]
        def start(self):
            pass
        def stop(self):
            pass

    def interrupt(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "Server", DummyServer)
    monkeypatch.setattr(cli.threading, "Event",
                        lambda: SimpleNamespace(wait=interrupt))
    assert cli.main(["--listen", "udp:0", "--udp-fault-plan", str(path)]) == 0
    assert seen[0]["udp_fault_plan"].select(1, peer="127.0.0.1") == {
        "type": "drop"}
    bad = tmp_path / "bad.json"
    bad.write_text('{"steps":[{"action":{"type":"rst"}}]}', encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        cli.main(["--listen", "udp:0", "--udp-fault-plan", str(bad)])
    assert error.value.code == 2
    assert "guide faults" in capsys.readouterr().err
