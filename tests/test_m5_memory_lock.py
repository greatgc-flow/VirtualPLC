"""M5 latch clearing and server-wide authentication on all transports."""

import socket

import pytest

from test_m3_m4_client import TRANSPORTS, connected
from test_m5_control import GATED, numbers, payload, transact, error_info


pytestmark = pytest.mark.unverified


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("clear_mode", [0, 1, 2])
def test_run_clear_modes_preserve_special_and_latch_ranges(server_factory, frame, wire, clear_mode):
    server = server_factory(initial_state="STOP")
    memory = server.memory
    memory.write_words("D", 0, [99])
    memory.write_bits("L", 0, [1])
    memory.write_bits("M", 0, [1])
    memory.write_bits("SM", 0, [1])
    memory.write_words("SD", 0, [77])
    with connected(server, frame, wire) as client:
        client.remote_run(clear_mode=clear_mode)
        # Idempotent RUN still honors the supplied clear mode.
        memory.write_words("R", 0, [5])
        client.remote_run(clear_mode=clear_mode)
    assert memory.read_words("D", 0, 1) == [99 if clear_mode == 0 else 0]
    assert memory.read_words("R", 0, 1) == [5 if clear_mode == 0 else 0]
    assert memory.read_bits("M", 0, 1) == [1 if clear_mode == 0 else 0]
    assert memory.read_bits("L", 0, 1) == [0 if clear_mode == 2 else 1]
    assert memory.read_bits("SM", 0, 1) == [1]
    assert memory.read_words("SD", 0, 1) == [77]
    assert memory.read_words("SD", 203, 1) == [1]


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("operation", ["latchclear", "run1", "run2"])
def test_custom_latch_ranges_are_inclusive_override_defaults(server_factory, frame, wire, operation):
    server = server_factory(initial_state="STOP", latch_ranges={"D": [(1, 2)], "SM": [(0, 1)], "SD": [(0, 203)]})
    memory = server.memory
    memory.write_words("D", 0, [10, 11, 12, 13])
    memory.write_bits("L", 0, [1])
    memory.write_bits("SM", 0, [1])
    memory.write_words("SD", 0, [88])
    with connected(server, frame, wire) as client:
        if operation == "latchclear":
            client.remote_latchclear()
        else:
            client.remote_run(clear_mode=int(operation[-1]))
    expected = {"latchclear": [10, 0, 0, 13], "run1": [0, 11, 12, 0], "run2": [0, 0, 0, 0]}
    assert memory.read_words("D", 0, 4) == expected[operation]
    assert memory.read_bits("L", 0, 1) == [1 if operation == "latchclear" else 0]
    assert memory.read_bits("SM", 0, 1) == [1]
    assert memory.read_words("SD", 0, 1) == [88]


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_empty_override_and_default_latchclear(server_factory, frame, wire):
    for ranges in (None, {}):
        server = server_factory(initial_state="STOP", latch_ranges=ranges)
        server.memory.write_bits("L", 0, [1])
        server.memory.write_words("D", 0, [7])
        with connected(server, frame, wire) as client:
            client.remote_latchclear()
        assert server.memory.read_bits("L", 0, 1) == [0 if ranges is None else 1]
        assert server.memory.read_words("D", 0, 1) == [7]


def test_profile_latch_default():
    from virtual_plc.profiles import MAX_POINT, PROFILES

    assert PROFILES["Q"].latch_ranges == {"L": ((0, MAX_POINT),)}


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_lock_is_server_wide_survives_disconnect_and_gates_only_control(server_factory, frame, wire):
    server = server_factory(initial_state="STOP", password="A1b2")
    with connected(server, frame, wire) as client:
        client.remote_lock(password="A1b2")
        client.remote_lock(password="A1b2")
    assert server.locked
    with socket.create_connection(server.address, timeout=1) as connection:
        for code in sorted(GATED):
            assert transact(connection, frame, wire, code, payload(wire, code)) == (0xC200, error_info(wire, code))
    assert server.state == "STOP" and server.reset_count == 0
    # A different transport on another connection sees the same lock.
    other_frame, other_wire = ("4E", "ascii") if (frame, wire) != ("4E", "ascii") else ("3E", "binary")
    with connected(server, other_frame, other_wire) as client:
        client.batchwrite_wordunits("D0", [42])
        assert client.batchread_wordunits("D0", 1) == [42]
        client.randomwrite(["D1"], [7], ["D2"], [0x12345678])
        assert client.randomread(["D1"], ["D2"]) == ([7], [0x12345678])
        client.randomwrite_bitunits(["M0"], [1])
        assert client.batchread_bitunits("M0", 1) == [1]
        assert client.echo_test("0A") == (2, "0A")
        assert client.read_cputype()[0] == "VirtualPLC-Q\x00\x00\x00\x00"
        client.remote_unlock(password="A1b2")
        client.remote_unlock(password="A1b2")
        client.remote_run(clear_mode=0)
    assert not server.locked and server.state == "RUN"


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize("command", [0x1630, 0x1631])
def test_wrong_password_does_not_change_lock_or_state(server_factory, frame, wire, locked, command):
    server = server_factory(password="A1b2")
    with socket.create_connection(server.address, timeout=1) as connection:
        if locked:
            assert transact(connection, frame, wire, 0x1631, payload(wire, 0x1631)) == (0, b"")
        assert transact(connection, frame, wire, command, numbers(wire, (4, 2)) + b"a1b2") == (0xC201, error_info(wire, command))
    assert server.locked is locked and server.state == "RUN"


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("command", [0x1630, 0x1631])
def test_no_password_disables_lock_commands(server_factory, frame, wire, command):
    server = server_factory()
    with socket.create_connection(server.address, timeout=1) as connection:
        assert transact(connection, frame, wire, command, payload(wire, command)) == (0xC059, error_info(wire, command))


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("text", [b"123", b"12345", b"ab\xffd"])
def test_password_payload_must_be_four_ascii_characters(server_factory, frame, wire, text):
    server = server_factory(password="A1b2")
    with socket.create_connection(server.address, timeout=1) as connection:
        assert transact(connection, frame, wire, 0x1631, numbers(wire, (len(text), 2)) + text) == (0xC05C, error_info(wire, 0x1631))
    assert not server.locked


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_password_declared_length_must_match_bytes(server_factory, frame, wire):
    server = server_factory(password="A1b2")
    with socket.create_connection(server.address, timeout=1) as connection:
        assert transact(connection, frame, wire, 0x1630, numbers(wire, (3, 2)) + b"A1b2") == (0xC057, error_info(wire, 0x1630))
