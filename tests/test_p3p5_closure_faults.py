"""P3/P5 closure: connection ordinals, UDP listener isolation and fault-doc drift."""

from pathlib import Path
import re
import socket
import struct
import threading
import time

from pymcprotocol import Type3E

from virtual_plc import FaultPlan, Server, UdpFaultPlan, faults, guide

ROOT = Path(__file__).resolve().parents[1]


def _read_d0(port):
    client = Type3E(plctype="Q")
    client.connect("127.0.0.1", port)
    try:
        return client.batchread_wordunits("D0", 1)
    finally:
        client.close()


def _plan_for_connection(number):
    return FaultPlan([{"match": {"connection": number}, "times": 100,
                       "action": {"type": "bad_end_code", "code": 0xC059}}])


def _status(port):
    client = Type3E(plctype="Q")
    client.connect("127.0.0.1", port)
    try:
        client.batchread_wordunits("D0", 1)
        return "ok"
    except Exception:
        return "fault"
    finally:
        client.close()


def _wait_for_clients(server, count, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with server._clients_lock:
            if len(server._clients) == count:
                return
        time.sleep(0.005)
    raise AssertionError(f"server did not reach {count} admitted clients")


# F3: refused connections do not consume ordinals.
def test_connection_ordinal_skips_connections_refused_by_max_clients():
    with Server(port=0, max_clients=1, fault_plan=_plan_for_connection(2)) as server:
        port = server.address[1]
        holder = socket.create_connection(("127.0.0.1", port))
        try:
            _wait_for_clients(server, 1)  # the server admitted the holder as connection 1
            refused = socket.create_connection(("127.0.0.1", port))
            refused.settimeout(2)
            assert refused.recv(1) == b""  # closed by the limit
            refused.close()
        finally:
            holder.close()
        deadline = time.monotonic() + 3
        while server._clients and time.monotonic() < deadline:
            time.sleep(0.02)
        assert _status(port) == "fault"  # second ADMITTED connection


# F6: one ordinal sequence spans every TCP listener of a Server.
def test_connection_ordinal_is_counted_across_tcp_listeners():
    with Server(listeners=[("tcp", 0), ("tcp", 0)], fault_plan=_plan_for_connection(2)) as server:
        (_, _, first), (_, _, second) = server.addresses
        assert first != second
        assert _status(first) == "ok"     # ordinal 1 on listener A
        assert _status(second) == "fault"  # ordinal 2 on listener B
        assert _status(first) == "ok"     # ordinal 3 on listener A


# F3: ordinals restart at 1 after stop()/start().
def test_connection_ordinal_resets_on_restart():
    server = Server(port=0, fault_plan=_plan_for_connection(1))
    server.start()
    try:
        assert _status(server.address[1]) == "fault"
    finally:
        server.stop()
    server.start()
    try:
        assert _status(server.address[1]) == "fault"
        assert _status(server.address[1]) == "ok"
    finally:
        server.stop()


def _udp_request():
    # 3E binary batch read D0, 1 word.
    body = bytes.fromhex("1000") + bytes.fromhex("0104") + bytes.fromhex("0000") + \
        (0).to_bytes(3, "little") + bytes([0xA8]) + (1).to_bytes(2, "little")
    return bytes.fromhex("5000") + bytes([0, 0xFF]) + struct.pack("<HB", 0x03FF, 0) + \
        struct.pack("<H", len(body)) + body


# F12a: a UDP delay on one listener does not delay another UDP listener.
def test_udp_delay_on_one_listener_does_not_block_another():
    plan = UdpFaultPlan([{"match": {"nth": 1}, "action": {"type": "delay", "seconds": 1.5}}])
    with Server(listeners=[("udp", 0), ("udp", 0)], udp_fault_plan=plan) as server:
        (_, host, slow_port), (_, _, fast_port) = server.addresses
        slow = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        fast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            slow.sendto(_udp_request(), (host, slow_port))
            time.sleep(0.2)  # the slow reply reserves nth=1 and starts its delay
            started = time.monotonic()
            fast.settimeout(1.0)
            fast.sendto(_udp_request(), (host, fast_port))
            reply, _ = fast.recvfrom(8192)
            assert time.monotonic() - started < 1.0
            assert reply[9:11] == b"\x00\x00"
            slow.settimeout(3)
            assert slow.recvfrom(8192)[0][9:11] == b"\x00\x00"
        finally:
            slow.close()
            fast.close()


# F13: every action key is documented in the FAULTS.md action tables.
def test_faults_doc_lists_every_tcp_and_udp_action():
    text = (ROOT / "docs/FAULTS.md").read_text(encoding="utf-8")
    rows = "\n".join(line for line in text.splitlines() if line.startswith("|"))
    missing = [kind for kind in faults.ACTION_FIELDS if f"`{kind}`" not in rows]
    assert not missing
    for kind in ("drop", "delay"):
        assert kind in text.split("## UDP datagram response faults", 1)[1]


def test_faults_doc_and_guide_define_connection_ordinal():
    text = (ROOT / "docs/FAULTS.md").read_text(encoding="utf-8")
    assert "max_clients" in text and re.search(r"restarts? at 1", text)
    assert "restarts at 1" in guide.FAULTS_HEAD


# F9: 1E command matching is documented.
def test_faults_doc_mentions_1e_command_byte_match():
    text = (ROOT / "docs/FAULTS.md").read_text(encoding="utf-8")
    assert "--slmp-1e" in text and "1E command byte" in text
