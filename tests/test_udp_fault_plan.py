"""UDP-only datagram response faults: drop, delay, duplicate, truncate, corrupt_header (#13).

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
    [{"action": {"type": "reorder"}}],
    [{"action": {"type": "bad_end_code", "code": 1}}],
    [{"action": {"type": ["drop"]}}],
    [{"action": {"type": "duplicate", "count": 2}}],
    [{"action": {"type": "truncate"}}],
    [{"action": {"type": "truncate", "n": 0}}],
    [{"action": {"type": "truncate", "n": True}}],
    [{"action": {"type": "truncate", "n": "1"}}],
    [{"action": {"type": "truncate", "n": 1.0}}],
    [{"action": {"type": "truncate", "n": 1, "seconds": 0}}],
    [{"action": {"type": "corrupt_header", "offset": 9}}],
    [{"action": {"type": "corrupt_header", "offset": -1}}],
    [{"action": {"type": "corrupt_header", "xor": 0}}],
    [{"action": {"type": "corrupt_header", "xor": 256}}],
    [{"action": {"type": "corrupt_header", "mask": 1}}],
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
            expected = encode_response(decode_request(frame), data=b"\x00\x00")
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


def test_udp_plan_atomic_selection_across_threads():
    from concurrent.futures import ThreadPoolExecutor
    faults = plan([{"times": 9, "action": {"type": "drop"}}])
    with ThreadPoolExecutor(max_workers=12) as pool:
        actions = list(pool.map(
            lambda i: faults.select(0x0401, peer="127.0.0.1"),
            range(60)))
    assert sum(item == {"type": "drop"} for item in actions) == 9


@pytest.mark.parametrize("document", [
    "[]", "{}", '{"steps":[],"extra":1}',
    '{"steps":"bad"}', '{"steps":[null]}',
])
def test_udp_json_schema_is_strict(tmp_path, document):
    from virtual_plc.udp_faults import UdpFaultPlan
    path = tmp_path / "udp.json"
    path.write_text(document, encoding="utf-8")
    with pytest.raises(ValueError):
        UdpFaultPlan.from_file(path)


# --- #13 datagram-native actions: duplicate, truncate, corrupt_header ---

def test_udp_plan_new_actions_validate_and_fill_defaults():
    faults = plan([
        {"action": {"type": "duplicate"}},
        {"action": {"type": "truncate", "n": 1}},
        {"action": {"type": "corrupt_header"}},
        {"action": {"type": "corrupt_header", "offset": 8, "xor": 255}},
    ])
    peer = {"peer": "127.0.0.1"}
    assert faults.select(1, **peer) == {"type": "duplicate"}
    assert faults.select(1, **peer) == {"type": "truncate", "n": 1}
    assert faults.select(1, **peer) == {"type": "corrupt_header", "offset": 0, "xor": 1}
    assert faults.select(1, **peer) == {"type": "corrupt_header", "offset": 8, "xor": 255}
    assert faults.select(1, **peer) is None


def test_udp_action_fields_are_the_schema_source():
    from virtual_plc.udp_faults import UDP_ACTION_FIELDS
    assert set(UDP_ACTION_FIELDS) == {"drop", "delay", "duplicate", "truncate", "corrupt_header"}


def test_udp_duplicate_sends_same_reply_twice_for_one_execution():
    hook_calls = []
    faults = plan([{"match": {"command": "0x1401"}, "action": {"type": "duplicate"}}])
    write = packet("3E", "binary", 0x1401, data=device_data(payload=b"\x34\x12"))
    read = packet("4E", "binary", serial=0x3344)
    with Server(listeners=[("udp", 0)], udp_fault_plan=faults, udp_metrics=True,
                response_hook=lambda response: hook_calls.append(response) or response) as server:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            first = recv_udp(client, write, server.address)
            assert first == encode_response(decode_request(write))
            assert client.recvfrom(8192)[0] == first
            assert len(hook_calls) == 1  # one dispatch, two datagrams
            # The next datagram is the read reply: no third copy precedes it.
            assert recv_udp(client, read, server.address) == encode_response(
                decode_request(read), data=b"\x34\x12")
    metrics = server.get_udp_metrics()
    assert (metrics["received"], metrics["sent"], metrics["fault_dropped"]) == (2, 3, 0)
    assert len(hook_calls) == 2


@pytest.mark.parametrize("n, kept", [(1, 1), (5, 5), (10**6, None)])
def test_udp_truncate_sends_prefix_after_committed_write(n, kept):
    faults = plan([{"match": {"nth": 1}, "action": {"type": "truncate", "n": n}}])
    write = packet("3E", "binary", 0x1401, data=device_data(payload=b"\x34\x12"))
    full = encode_response(decode_request(write))
    with Server(listeners=[("udp", 0)], udp_fault_plan=faults, udp_metrics=True) as server:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            assert recv_udp(client, write, server.address) == full[:kept]
            assert server.memory.read_words("D", 0, 1) == [0x1234]
            assert recv_udp(client, write, server.address) == full  # times=1 exhausted
    assert server.get_udp_metrics()["sent"] == 2


@pytest.mark.parametrize("frame, wire", [("3E", "binary"), ("4E", "ascii")])
def test_udp_corrupt_header_flips_one_byte(frame, wire):
    faults = plan([{"action": {"type": "corrupt_header", "offset": 1, "xor": 0xFF}}])
    read = packet(frame, wire, serial=0x1234)
    full = encode_response(decode_request(read), data=b"\x00\x00")
    with Server(listeners=[("udp", 0)], udp_fault_plan=faults) as server:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            reply = recv_udp(client, read, server.address)
            assert reply == full[:1] + bytes([full[1] ^ 0xFF]) + full[2:]
            assert recv_udp(client, read, server.address) == full


def test_udp_corrupt_header_offset_past_short_1e_reply_is_unchanged():
    """A 1E binary write reply is 2 bytes; offsets beyond a datagram never raise."""
    faults = plan([{"action": {"type": "corrupt_header", "offset": 8}},
                   {"action": {"type": "corrupt_header", "offset": 1, "xor": 0x80}}])
    frame = one_e_request(3, head=0, count=1, payload=b"\x34\x12")
    with Server(slmp_1e=True, listeners=[("udp", 0)], udp_fault_plan=faults) as server:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            assert recv_udp(client, frame, server.address) == b"\x83\x00"
            assert recv_udp(client, frame, server.address) == b"\x83\x80"
            assert server.memory.read_words("D", 0, 1) == [0x1234]


def test_udp_fault_cli_rejects_invalid_new_action_before_bind(tmp_path, monkeypatch, capsys):
    from virtual_plc import __main__ as cli

    def forbidden(*args, **kwargs):
        raise AssertionError("Server must not be constructed for an invalid plan")

    monkeypatch.setattr(cli, "Server", forbidden)
    for action in ({"type": "truncate", "n": 0}, {"type": "corrupt_header", "offset": 9},
                   {"type": "reorder"}):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"steps": [{"action": action}]}), encoding="utf-8")
        with pytest.raises(SystemExit) as error:
            cli.main(["--listen", "udp:0", "--udp-fault-plan", str(bad)])
        assert error.value.code == 2
        assert "guide faults" in capsys.readouterr().err


def test_udp_actions_documented_in_faults_doc_and_guide():
    from pathlib import Path
    from virtual_plc import guide
    from virtual_plc.__main__ import build_parser
    from virtual_plc.udp_faults import UDP_ACTION_FIELDS
    root = Path(__file__).resolve().parents[1]
    section = (root / "docs/FAULTS.md").read_text(encoding="utf-8").split(
        "## UDP datagram response faults", 1)[1]
    rows = "\n".join(line for line in section.splitlines() if line.startswith("|"))
    assert not [kind for kind in UDP_ACTION_FIELDS if f"`{kind}`" not in rows]
    udp_line = next(line for line in guide.render(build_parser(), "faults").splitlines()
                    if line.startswith("UDP actions"))
    assert all(kind in udp_line for kind in UDP_ACTION_FIELDS)
    assert "reorder" in (root / "docs/DESIGN.md").read_text(encoding="utf-8").split(
        "### UDP datagram response faults", 1)[1].split("\n## ", 1)[0].lower()
