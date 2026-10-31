"""Optional 1E physical RUN/STOP selector behavior, isolated simulator tests.

Official Mitsubishi JY997D56001-K printed p.132 (PDF index 133):
remote RUN (13H) may report normal completion with hardware switch STOP
without transitioning PLC CPU to RUN. This is NOT a hardware oracle.
"""
import socket

import pytest

from virtual_plc import Server
from virtual_plc.__main__ import build_parser


STOP = bytes.fromhex("14 FF 00 00")
RUN = bytes.fromhex("13 FF 00 00")
RUN_ASCII = b"13FF0000"


def exchange(conn, payload, length):
    conn.sendall(payload)
    output = b""
    while len(output) < length:
        chunk = conn.recv(length - len(output))
        assert chunk
        output += chunk
    return output


def test_default_1e_run_switch_does_not_change_previous_behavior():
    with Server(slmp_1e=True) as plc:
        assert plc.slmp_1e_run_switch == "RUN"
        with socket.create_connection(plc.address, timeout=2) as conn:
            conn.settimeout(2)
            assert exchange(conn, STOP, 2) == b"\x94\x00"
            assert exchange(conn, RUN, 2) == b"\x93\x00"
            assert plc.state == "RUN"


@pytest.mark.parametrize("packet,reply", [
    (RUN, b"\x93\x00"),
    (RUN_ASCII, b"9300"),
])
def test_switch_stop_successful_remote_run_does_not_start_cpu(packet, reply):
    with Server(slmp_1e=True, slmp_1e_run_switch="STOP",
                initial_state="STOP") as plc:
        assert plc.state == "STOP"
        with socket.create_connection(plc.address, timeout=2) as conn:
            conn.settimeout(2)
            assert exchange(conn, STOP, 2) == b"\x94\x00"
            assert plc.get_1e_remote_control_status()["owned"] is True
            assert exchange(conn, packet, len(reply)) == reply
            # Only remote ownership clears. Physical STOP suppresses RUN.
            assert plc.state == "STOP"
            assert plc.memory.read_words("SD", 203, 1) == [0]
            state = plc.get_1e_remote_control_status()
            assert state["owned"] is False
            assert state["cpu_state"] == "STOP"


def test_switch_stop_releases_owner_only_to_originating_connection():
    with Server(slmp_1e=True, slmp_1e_run_switch="STOP",
                initial_state="STOP") as plc:
        with socket.create_connection(plc.address, timeout=2) as a, \
                socket.create_connection(plc.address, timeout=2) as b:
            a.settimeout(2)
            b.settimeout(2)
            assert exchange(a, STOP, 2) == b"\x94\x00"
            assert exchange(b, RUN, 4) == bytes.fromhex("93 5B 5F C0")
            assert plc.state == "STOP"
            assert plc.get_1e_remote_control_status()["owned"] is True
            assert exchange(a, RUN, 2) == b"\x93\x00"
            assert plc.get_1e_remote_control_status()["owned"] is False
            assert plc.state == "STOP"
            assert exchange(b, STOP, 2) == b"\x94\x00"
            assert plc.get_1e_remote_control_status()["owned"] is True


@pytest.mark.parametrize("value", ["STOP", "stop", "", 0, False, None])
def test_run_switch_validation_and_explicit_scope(value):
    if value == "STOP":
        with pytest.raises(ValueError):
            Server(slmp_1e_run_switch=value)
        with pytest.raises(ValueError):
            Server(slmp_1e=True, slmp_1e_run_switch=value,
                   initial_state="RUN")
    else:
        with pytest.raises(ValueError):
            Server(slmp_1e=True, slmp_1e_run_switch=value)


def test_cli_requires_slmp_1e_mode_for_physical_switch_override():
    parser = build_parser()
    assert "--slmp-1e-run-switch" in parser._option_string_actions
    args = parser.parse_args([
        "--slmp-1e", "--slmp-1e-run-switch", "STOP",
        "--initial-state", "STOP",
    ])
    assert args.slmp_1e_run_switch == "STOP"
    assert args.slmp_1e is True


def test_switch_stop_unaffected_non_control_commands():
    from virtual_plc.memory import Memory
    memory = Memory("Q")
    memory.write_words("D", 100, [0x1234])
    with Server(slmp_1e=True, slmp_1e_run_switch="STOP",
                initial_state="STOP", memory=memory) as plc:
        with socket.create_connection(plc.address, timeout=2) as conn:
            conn.settimeout(2)
            request = bytes.fromhex("01 FF 00 00 64 00 00 00 20 44 01 00")
            assert exchange(conn, request, 4) == bytes.fromhex("81 00 34 12")
        assert plc.state == "STOP"
