"""Raw faults across all four transports; faults are post-dispatch effects."""

from concurrent.futures import ThreadPoolExecutor
import os
import socket
import struct
import threading
import time

import pytest

from test_m1_server_raw import receive_exact
from test_m3_m4_client import TRANSPORTS
from test_m3_m4_raw import packet, receive


ECHO = 0x0619


def start_fault_server(server_factory, action, *, match=None, times=1, **options):
    from virtual_plc.faults import FaultPlan

    return server_factory(fault_plan=FaultPlan([{"match": match or {"command": ECHO}, "times": times,
                                               "action": action}]), **options)


def echo_packet(frame, wire):
    return packet(frame, wire, ECHO, data=b"00020A" if wire == "ascii" else b"\x02\x000A")


def expected_echo(frame, wire):
    return b"00020A" if wire == "ascii" else b"\x02\x000A"


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_drop_once_keeps_connection_and_next_response_usable(server_factory, frame, wire):
    server = start_fault_server(server_factory, {"type": "drop"})
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(echo_packet(frame, wire))
        connection.settimeout(0.03)
        with pytest.raises(socket.timeout):
            connection.recv(1)
        connection.settimeout(1)
        connection.sendall(echo_packet(frame, wire))
        assert receive(connection, frame, wire) == (0, expected_echo(frame, wire))


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_delay_is_bounded_and_does_not_change_frame(server_factory, frame, wire):
    server = start_fault_server(server_factory, {"type": "delay", "seconds": 0.03})
    with socket.create_connection(server.address, timeout=1) as connection:
        started = time.monotonic()
        connection.sendall(echo_packet(frame, wire))
        assert receive(connection, frame, wire) == (0, expected_echo(frame, wire))
        assert time.monotonic() - started >= 0.02


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("kind", ["truncate", "corrupt_header", "partial_send"])
def test_wire_transformations_and_chunked_transmission(server_factory, frame, wire, kind):
    original = []
    action = {"type": kind}
    if kind == "truncate":
        action["n"] = 5
    elif kind == "corrupt_header":
        action.update(offset=0, xor=1)
    else:
        action.update(chunks=[1, 2, 3], pause=0.005)
    def hook(response):
        original.append(response)
        return response
    server = start_fault_server(server_factory, action, response_hook=hook)
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(echo_packet(frame, wire))
        size = 5 if kind == "truncate" else ((26 if frame == "4E" else 18) + 10 if wire == "ascii"
                                            else (13 if frame == "4E" else 9) + 6)
        data = receive_exact(connection, size)
    expected = original[0][:5] if kind == "truncate" else original[0]
    if kind == "corrupt_header":
        expected = bytes([expected[0] ^ 1]) + expected[1:]
    assert data == expected


@pytest.mark.unverified
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_bad_end_code_uses_correct_offset_after_existing_hook(server_factory, frame, wire):
    original = []
    def hook(response):
        original.append(response)
        return response
    server = start_fault_server(server_factory, {"type": "bad_end_code", "code": 0xC05C}, response_hook=hook)
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(echo_packet(frame, wire))
        assert receive(connection, frame, wire) == (0xC05C, expected_echo(frame, wire))
    offset = (13 if frame == "4E" else 9) * (2 if wire == "ascii" else 1)
    assert original[0][offset:offset + (4 if wire == "ascii" else 2)] == (b"0000" if wire == "ascii" else b"\x00\x00")


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("kind", ["close_before_response", "close_after_response", "rst"])
def test_close_actions_and_abortive_linger(server_factory, monkeypatch, frame, wire, kind):
    linger = []
    original = socket.socket.setsockopt
    def record(connection, level, option, value, *args):
        if level == socket.SOL_SOCKET and option == socket.SO_LINGER:
            linger.append(value)
        return original(connection, level, option, value, *args)
    monkeypatch.setattr(socket.socket, "setsockopt", record)
    server = start_fault_server(server_factory, {"type": kind})
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(echo_packet(frame, wire))
        if kind == "close_after_response":
            assert receive(connection, frame, wire) == (0, expected_echo(frame, wire))
        try:
            assert connection.recv(1) == b""
        except ConnectionResetError:
            assert kind in {"rst", "close_before_response"}
    if kind == "rst":
        assert linger == [struct.pack("hh" if os.name == "nt" else "ii", 1, 0)]
    else:
        assert linger == []


def test_connection_and_request_matches_are_local_and_repeated(server_factory):
    server = start_fault_server(server_factory, {"type": "drop"}, match={"connection": 1, "nth": 2})
    with socket.create_connection(server.address, timeout=1) as first, socket.create_connection(server.address, timeout=1) as second:
        for connection in (first, second):
            connection.sendall(echo_packet("3E", "binary"))
            assert receive(connection, "3E", "binary") == (0, b"\x02\x000A")
        first.sendall(echo_packet("3E", "binary"))
        first.settimeout(0.03)
        with pytest.raises(socket.timeout):
            first.recv(1)
        second.sendall(echo_packet("3E", "binary"))
        assert receive(second, "3E", "binary") == (0, b"\x02\x000A")
        first.settimeout(1)
        first.sendall(echo_packet("3E", "binary"))
        assert receive(first, "3E", "binary") == (0, b"\x02\x000A")


@pytest.mark.parametrize("kind", ["drop", "close_before_response", "silent_hold"])
def test_response_faults_do_not_rollback_committed_writes(server_factory, kind):
    entered = threading.Event()
    def hook(response):
        entered.set()
        return response
    server = start_fault_server(server_factory, {"type": kind}, match={"command": 0x1401}, response_hook=hook)
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(packet("3E", "binary", 0x1401, data=bytes.fromhex("00 00 00 a8 01 00 34 12")))
        assert entered.wait(1)
        assert server.memory.read_words("D", 0, 1) == [0x1234]
        with socket.create_connection(server.address, timeout=1) as other:
            other.sendall(packet("3E", "binary"))
            assert receive(other, "3E", "binary") == (0, b"\x34\x12")


@pytest.mark.parametrize("action", [{"type": "delay", "seconds": 30}, {"type": "silent_hold"},
    {"type": "partial_send", "chunks": [1], "pause": 30}])
def test_stop_interrupts_all_fault_waits(server_factory, action):
    entered = threading.Event()
    def hook(response):
        entered.set()
        return response
    server = start_fault_server(server_factory, action, response_hook=hook)
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(echo_packet("3E", "binary"))
        assert entered.wait(1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(server.stop).result(timeout=2)


def test_no_plan_is_inert_and_skips_fault_sender(server_factory, monkeypatch):
    import virtual_plc.faults as faults

    def forbidden(*args, **kwargs):
        pytest.fail("No fault plan must use the original send path")
    monkeypatch.setattr(faults, "send_fault", forbidden)
    server = server_factory(fault_plan=None)
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(echo_packet("3E", "binary"))
        assert receive(connection, "3E", "binary") == (0, b"\x02\x000A")
