"""M5 agreed design policies; no claims about physical PLC state or end codes."""

from itertools import product
import socket

import pytest

from tables import CONTROL_COMMANDS, PROFILES, applicable
from test_m3_m4_client import TRANSPORTS, connected
from test_m3_m4_raw import packet, receive


pytestmark = pytest.mark.unverified
STATE_CODES = {"STOP": 0, "RUN": 1, "PAUSE": 2}
GATED = {0x1001, 0x1002, 0x1003, 0x1005, 0x1006}
CELLS = [(frame, wire, command) for frame, wire, command in product(
    ("3E", "4E"), ("binary", "ascii"), CONTROL_COMMANDS
) if applicable(command, PROFILES[0], frame, wire, milestone=5)[0]]


def numbers(wire, *fields):
    return b"".join(f"{value:0{size * 2}X}".encode() if wire == "ascii" else value.to_bytes(size, "little")
                    for value, size in fields)


def transact(connection, frame, wire, command, data, subcommand=0):
    connection.sendall(packet(frame, wire, command, subcommand, data))
    return receive(connection, frame, wire)


def payload(wire, command):
    if command in (0x1630, 0x1631):
        return numbers(wire, (4, 2)) + b"A1b2"
    return numbers(wire, (1, 2), (0, 1), (0, 1)) if command == 0x1001 else numbers(wire, (1, 2))


@pytest.mark.parametrize("frame,wire,command", CELLS, ids=[f"{f}-{w}-{c.name}" for f, w, c in CELLS])
def test_client_control_matrix(server_factory, frame, wire, command):
    initial = "STOP" if command.name in {"latchclear", "reset"} else "RUN"
    server = server_factory(initial_state=initial, password="A1b2")
    with connected(server, frame, wire) as client:
        if command.name == "run":
            result = client.remote_run(clear_mode=0)
        elif command.name in {"lock", "unlock"}:
            if command.name == "unlock":
                client.remote_lock(password="A1b2")
            result = getattr(client, f"remote_{command.name}")(password="A1b2")
        else:
            result = getattr(client, f"remote_{command.name}")()
        assert result is None
        assert client.echo_test("0A") == (2, "0A")
    expected = {"run": "RUN", "stop": "STOP", "pause": "PAUSE"}.get(command.name, initial)
    assert server.state == expected
    assert server.memory.read_words("SD", 203, 1) == [STATE_CODES[expected]]
    assert server.reset_count == (1 if command.name == "reset" else 0)
    assert server.locked == (command.name == "lock")


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("initial,command", list(product(("RUN", "STOP", "PAUSE"), sorted(GATED))))
def test_state_transition_table(server_factory, frame, wire, initial, command):
    server = server_factory(initial_state=initial)
    invalid = (command == 0x1003 and initial == "STOP") or (command in {0x1005, 0x1006} and initial != "STOP")
    server.memory.write_words("D", 0, [42])
    with socket.create_connection(server.address, timeout=1) as connection:
        status, data = transact(connection, frame, wire, command, payload(wire, command))
        assert (status, data) == (0xC202 if invalid else 0, b"")
        assert transact(connection, frame, wire, 0x0619, numbers(wire, (2, 2)) + b"0A") == (
            0, (b"0002" if wire == "ascii" else b"\x02\x00") + b"0A"
        )
    expected = initial if invalid else {0x1001: "RUN", 0x1002: "STOP", 0x1003: "PAUSE"}.get(command, "STOP")
    assert server.state == expected
    assert server.memory.read_words("SD", 203, 1) == [STATE_CODES[expected]]
    assert server.memory.read_words("D", 0, 1) == [42]
    assert server.reset_count == (1 if command == 0x1006 and not invalid else 0)


@pytest.mark.parametrize("state", ["RUN", "STOP", "PAUSE"])
def test_initial_state_and_default(server_factory, state):
    server = server_factory(initial_state=state)
    assert server.state == state
    assert server.memory.read_words("SD", 203, 1) == [STATE_CODES[state]]
    assert server.reset_count == 0 and not server.locked


def test_default_is_run(server_factory):
    server = server_factory()
    assert server.state == "RUN"
    assert server.memory.read_words("SD", 203, 1) == [1]


@pytest.mark.parametrize("options", [
    {"initial_state": "INVALID"}, {"initial_state": "run"}, {"password": ""},
    {"password": "123"}, {"password": "12345"}, {"password": "ab\u00e9d"}, {"password": 1234},
    {"latch_ranges": {"UNKNOWN": [(0, 1)]}}, {"latch_ranges": {"L": [(3, 2)]}},
    {"latch_ranges": {"D": [(-1, 3)]}}, {"latch_ranges": {"L": [(0, 0x1000000)]}},
])
def test_invalid_configuration_rejected_at_construction(options):
    from virtual_plc.server import Server

    with pytest.raises(ValueError):
        Server(**options)


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_force_modes_follow_normal_state_rules(server_factory, frame, wire):
    server = server_factory()
    with connected(server, frame, wire) as client:
        client.remote_run(clear_mode=0, force_exec=True)
        assert server.state == "RUN"
        client.remote_pause(force_exec=True)
        assert server.state == "PAUSE"
        client.remote_pause(force_exec=False)
        assert server.state == "PAUSE"
        client.remote_stop()
        assert server.state == "STOP"


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_successful_reset_uses_same_socket_and_clears_no_memory(server_factory, frame, wire, monkeypatch):
    server = server_factory(initial_state="STOP")
    server.memory.write_words("D", 0, [123])
    server.memory.write_bits("L", 0, [1])
    server.memory.write_words("SD", 0, [77])
    with connected(server, frame, wire) as client:
        original_socket = client._sock
        def forbidden_reconnect(*args):
            pytest.fail("A successful reset must not reconnect")
        monkeypatch.setattr(client, "connect", forbidden_reconnect)
        client.remote_reset()
        client.remote_reset()
        assert client._sock is original_socket
        assert original_socket.gettimeout() == 1
        assert client.echo_test("0A") == (2, "0A")
    assert server.reset_count == 2 and server.state == "STOP"
    assert server.memory.read_words("D", 0, 1) == [123]
    assert server.memory.read_bits("L", 0, 1) == [1]
    assert server.memory.read_words("SD", 0, 1) == [77]


BAD_FIELDS = [
    (0x1001, ((0, 2), (0, 1), (0, 1))), (0x1001, ((2, 2), (0, 1), (0, 1))),
    (0x1001, ((1, 2), (3, 1), (0, 1))), (0x1001, ((1, 2), (0, 1), (1, 1))),
    (0x1003, ((0, 2),)), (0x1003, ((2, 2),)),
    (0x1002, ((3, 2),)), (0x1005, ((0, 2),)), (0x1006, ((3, 2),)),
]


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("command,fields", BAD_FIELDS)
def test_invalid_fields_do_not_change_state_or_memory(server_factory, frame, wire, command, fields):
    server = server_factory(initial_state="STOP")
    server.memory.write_words("D", 0, [7])
    with socket.create_connection(server.address, timeout=1) as connection:
        assert transact(connection, frame, wire, command, numbers(wire, *fields)) == (0xC05C, b"")
    assert server.state == "STOP" and server.reset_count == 0
    assert server.memory.read_words("D", 0, 1) == [7]


@pytest.mark.parametrize("frame,wire,command", CELLS)
@pytest.mark.parametrize("change", ["short", "extra"])
def test_bad_payload_length_is_length_error(server_factory, frame, wire, command, change):
    server = server_factory(initial_state="STOP", password="A1b2")
    data = payload(wire, command.code)
    data = data[:-1] if change == "short" else data + b"0"
    with socket.create_connection(server.address, timeout=1) as connection:
        assert transact(connection, frame, wire, command.code, data) == (0xC057, b"")
    assert server.state == "STOP" and not server.locked and server.reset_count == 0


@pytest.mark.parametrize("frame,wire,command", CELLS)
def test_nonzero_subcommand_is_unsupported(server_factory, frame, wire, command):
    server = server_factory()
    with socket.create_connection(server.address, timeout=1) as connection:
        assert transact(connection, frame, wire, command.code, payload(wire, command.code), subcommand=1) == (0xC059, b"")


def test_control_table_and_error_provenance():
    from virtual_plc.commands import ERROR_CODES, LOCK_GATED

    assert LOCK_GATED == GATED
    assert {c.code for c in CONTROL_COMMANDS} == GATED | {0x1630, 0x1631}
    for code, name, source in [(0xC200, "LOCKED", "memory"), (0xC201, "WRONG_PASSWORD", "memory"),
                               (0xC202, "INVALID_STATE", "design")]:
        assert ERROR_CODES[code] == {"name": name, "source": source, "status": "unverified"}


def test_older_ascii_data_error_mapping_is_preserved(server_factory):
    server = server_factory()
    with socket.create_connection(server.address, timeout=1) as connection:
        # Truncated ASCII word payload: the established M3 policy is C05C.
        assert transact(connection, "3E", "ascii", 0x1401, b"D*000000000112") == (0xC05C, b"")
