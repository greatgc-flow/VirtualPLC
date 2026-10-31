"""1E remote RUN/STOP owner safety tests, manual JY997D56001-K pp.132-133.

The manual requires the STOP origin to execute RUN; it documents reset/power
cycle release, but does not promise release on TCP disconnect. The simulator
therefore keeps an orphaned STOP until explicit local administrative reset.
"""
import socket

import pytest

from virtual_plc import Server
from virtual_plc.one_e import frame_size_1e

RUN = bytes.fromhex("13 FF 00 00")
STOP = bytes.fromhex("14 FF 00 00")
RUN_ASCII = b"13FF0000"
STOP_ASCII = b"14FF0000"
DENIED_RUN = bytes.fromhex("93 5B 5F C0")
DENIED_STOP = bytes.fromhex("94 5B 5F C0")


def send(client, packet, count):
    client.sendall(packet)
    reply = b""
    while len(reply) < count:
        chunk = client.recv(count - len(reply))
        assert chunk
        reply += chunk
    return reply


@pytest.mark.parametrize("run,stop,run_ack,stop_ack,deny_run,deny_stop", [
    (RUN, STOP, b"\x93\x00", b"\x94\x00", DENIED_RUN, DENIED_STOP),
    (RUN_ASCII, STOP_ASCII, b"9300", b"9400", b"935BC05F", b"945BC05F"),
])
def test_1e_stop_is_owned_by_originating_tcp_connection(
        run, stop, run_ack, stop_ack, deny_run, deny_stop):
    with Server(slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as a, \
                socket.create_connection(plc.address, timeout=2) as b:
            a.settimeout(2)
            b.settimeout(2)
            assert send(a, stop, len(stop_ack)) == stop_ack
            assert plc.state == "STOP"
            assert plc.memory.read_words("SD", 203, 1) == [0]
            assert send(b, run, len(deny_run)) == deny_run
            assert send(b, stop, len(deny_stop)) == deny_stop
            assert plc.state == "STOP"
            assert send(a, stop, len(stop_ack)) == stop_ack
            assert send(a, run, len(run_ack)) == run_ack
            assert plc.state == "RUN"
            assert send(b, stop, len(stop_ack)) == stop_ack
            assert send(a, run, len(deny_run)) == deny_run
            assert send(b, run, len(run_ack)) == run_ack
            assert plc.state == "RUN"


def test_1e_owner_is_not_transferred_by_disconnect_or_reconnect():
    with Server(slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as a:
            a.settimeout(2)
            assert send(a, STOP, 2) == b"\x94\x00"
        with socket.create_connection(plc.address, timeout=2) as b:
            b.settimeout(2)
            assert send(b, RUN, 4) == DENIED_RUN
            assert send(b, STOP, 4) == DENIED_STOP
            assert plc.state == "STOP"
            plc.reset_1e_remote_control()  # local simulated reset, not remote password bypass
            assert plc.state == "STOP"  # fail-safe: no automatic RUN on reset
            assert send(b, RUN, 2) == b"\x93\x00"
            assert plc.state == "RUN"
            assert plc.reset_count == 1


@pytest.mark.parametrize("packet,size", [
    (RUN, 4), (STOP, 4), (RUN_ASCII, 8), (STOP_ASCII, 8),
])
def test_1e_control_exact_fixed_size_and_partial_frames(packet, size):
    assert frame_size_1e(packet) == size
    assert frame_size_1e(packet[:-1]) is None


def test_1e_udp_remote_control_rejected_without_connection_ownership():
    with Server(slmp_1e=True, listeners=[("udp", 0)]) as plc:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(2)
            for packet, expected in ((RUN, DENIED_RUN), (STOP, DENIED_STOP),
                                     (RUN_ASCII, b"935BC05F"), (STOP_ASCII, b"945BC05F")):
                udp.sendto(packet, plc.address)
                assert udp.recvfrom(1024)[0] == expected
            assert plc.state == "RUN"


@pytest.mark.parametrize("bad", [
    bytes.fromhex("14 00 00 00"),  # wrong PC number
    bytes.fromhex("13 FF 01 00"),  # nonzero timer
    b"14FE0000", b"13FF0001",
])
def test_1e_invalid_remote_header_does_not_alter_state(bad):
    with Server(slmp_1e=True, listeners=[("udp", 0)]) as plc:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(0.15)
            udp.sendto(bad, plc.address)
            with pytest.raises(socket.timeout):
                udp.recvfrom(1024)
        assert plc.state == "RUN"


def test_1e_control_owner_across_two_tcp_listener_ports():
    with Server(slmp_1e=True, listeners=[("tcp", 0), ("tcp", 0)]) as plc:
        with socket.create_connection(plc.addresses[0][1:], timeout=2) as a, \
                socket.create_connection(plc.addresses[1][1:], timeout=2) as b:
            a.settimeout(2)
            b.settimeout(2)
            assert send(a, STOP, 2) == b"\x94\x00"
            assert send(b, RUN, 4) == DENIED_RUN
            assert send(a, RUN, 2) == b"\x93\x00"


def test_1e_control_hook_invoked_once_with_success_and_denied_reply():
    outputs = []
    def record(data):
        outputs.append(data)
        return data
    with Server(slmp_1e=True, response_hook=record) as plc:
        with socket.create_connection(plc.address, timeout=2) as a, \
                socket.create_connection(plc.address, timeout=2) as b:
            a.settimeout(2)
            b.settimeout(2)
            assert send(a, STOP, 2) == b"\x94\x00"
            assert send(b, RUN, 4) == DENIED_RUN
            assert send(a, RUN, 2) == b"\x93\x00"
    assert outputs == [b"\x94\x00", DENIED_RUN, b"\x93\x00"]


def test_1e_remote_control_reset_rejects_non_1e_runtime():
    with pytest.raises(ValueError):
        Server().reset_1e_remote_control()
