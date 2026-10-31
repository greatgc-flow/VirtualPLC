"""SLMP 1E P2 regression: owner observability, limits, and concurrency.

The packet builders here follow the explicit manufacturer 1E layout; these
are simulator regression tests, NOT PLC-hardware recordings. All ports are
localhost/ephemeral. JY997D56001-K printed pp.128-133.
"""

import socket
import threading
import time

import pytest

from virtual_plc import Server
from virtual_plc.memory import Memory


def random_packet(command, items, wire="binary"):
    """Build a literal 1E request independently from one_e.py production code."""
    assert command in (4, 5)
    assert len(items) <= 255
    if wire == "binary":
        out = bytearray([command, 0xFF, 0, 0, len(items), 0])
        for device, head, value in items:
            out.extend(int(head).to_bytes(4, "little"))
            out.extend(device.encode("ascii").ljust(2, b" ")[::-1])
            out.extend(int(value).to_bytes(1 if command == 4 else 2, "little"))
        return bytes(out)
    out = f"{command:02X}FF0000{len(items):02X}00".encode("ascii")
    for device, head, value in items:
        name = device.encode("ascii").ljust(2, b" ")
        out += (name.hex().upper().encode("ascii") +
                f"{head:08X}{value:0{2 if command == 4 else 4}X}".encode("ascii"))
    return out


def read_exact(conn, size):
    result = bytearray()
    while len(result) < size:
        part = conn.recv(size - len(result))
        assert part, "connection closed before SLMP reply"
        result += part
    return bytes(result)


def command(conn, payload, expected):
    conn.sendall(payload)
    assert read_exact(conn, len(expected)) == expected


def snapshot(plc):
    return plc.get_1e_remote_control_status()


def assert_empty_owner(state, cpu):
    assert state["cpu_state"] == cpu
    assert state["owned"] is False
    assert state["owner_connected"] is False
    assert state["orphaned"] is False
    assert state["owner_connection_id"] is None


def test_1e_owner_status_lifecycle_and_orphan_recovery():
    with Server(slmp_1e=True, listeners=[("tcp", 0), ("tcp", 0)]) as plc:
        assert_empty_owner(snapshot(plc), "RUN")
        with socket.create_connection(plc.addresses[0][1:], timeout=2) as origin:
            origin.settimeout(2)
            command(origin, bytes.fromhex("14 FF 00 00"), b"\x94\x00")
            state = snapshot(plc)
            assert state["cpu_state"] == "STOP"
            assert state["owned"] is True
            assert state["owner_connected"] is True
            assert state["orphaned"] is False
            assert isinstance(state["owner_connection_id"], int)
            assert state["owner_connection_id"] > 0
            first_id = state["owner_connection_id"]
            with socket.create_connection(plc.addresses[1][1:], timeout=2) as stranger:
                stranger.settimeout(2)
                command(stranger, bytes.fromhex("13 FF 00 00"),
                        b"\x93\x5b\x5f\xc0")
                assert snapshot(plc)["owner_connection_id"] == first_id

        # Asynchronous EOF detection is eventually consistent; never treat a
        # socket close as a release or a new owner.
        deadline = time.monotonic() + 2
        while snapshot(plc)["owner_connected"] and time.monotonic() < deadline:
            time.sleep(0.01)
        state = snapshot(plc)
        assert state == {
            "cpu_state": "STOP", "owned": True,
            "owner_connected": False, "orphaned": True,
            "owner_connection_id": first_id,
        }
        with socket.create_connection(plc.address, timeout=2) as successor:
            successor.settimeout(2)
            command(successor, bytes.fromhex("13 FF 00 00"),
                    b"\x93\x5b\x5f\xc0")
            plc.reset_1e_remote_control()
            assert_empty_owner(snapshot(plc), "STOP")
            command(successor, bytes.fromhex("13 FF 00 00"), b"\x93\x00")
            assert_empty_owner(snapshot(plc), "RUN")


def test_1e_status_rejected_outside_opt_in_mode():
    with pytest.raises(ValueError):
        Server().get_1e_remote_control_status()


@pytest.mark.parametrize("wire", ["binary", "ascii"])
@pytest.mark.parametrize("opcode,limit,device", [
    (4, 80, "M"), (5, 10, "D"),
])
def test_1e_random_maximum_and_one_above(wire, opcode, limit, device):
    def expected(code):
        return (bytes((opcode | 0x80, 0)) if wire == "binary"
                else f"{opcode | 0x80:02X}00".encode("ascii"))
    def denied(code):
        return (bytes((opcode | 0x80, 0x5B)) + code.to_bytes(2, "little")
                if wire == "binary" else
                f"{opcode | 0x80:02X}5B{code:04X}".encode("ascii"))
    good = [(device, i, 1 + i if opcode == 5 else 1)
            for i in range(limit)]
    over = good + [(device, limit, 2 if opcode == 5 else 1)]
    mem = Memory("Q")
    with Server(slmp_1e=True, memory=mem) as plc:
        with socket.create_connection(plc.address, timeout=2) as c:
            c.settimeout(2)
            command(c, random_packet(opcode, good, wire), expected(0))
            command(c, random_packet(opcode, over, wire),
                    denied(0xC053 if opcode == 4 else 0xC054))
    if opcode == 4:
        assert mem.read_bits("M", 0, limit + 1) == [1] * limit + [0]
    else:
        assert mem.read_words("D", 0, limit + 1) == list(range(1, limit + 1)) + [0]


def test_1e_random_repeated_destinations_last_wins_and_rollback_at_custom_limit():
    mem = Memory("Q", limits={"D": (100, 105)})
    mem.write_words("D", 100, [77, 88])
    with Server(slmp_1e=True, memory=mem) as plc:
        with socket.create_connection(plc.address, timeout=2) as c:
            c.settimeout(2)
            command(c, random_packet(5, [("D", 100, 111), ("D", 100, 222)]),
                    b"\x85\x00")
            assert mem.read_words("D", 100, 1) == [222]
            # First record must be rolled back when last record exceeds
            # a custom Memory limit even though it is inside vendor max.
            command(c, random_packet(5, [("D", 100, 333), ("D", 106, 444)]),
                    b"\x85\x5b\x56\xc0")
    assert mem.read_words("D", 100, 2) == [222, 88]


def test_1e_random_unaligned_last_bit_group_does_not_partially_write():
    mem = Memory("Q")
    mem.write_words("D", 100, [0xAAAA])
    bad = random_packet(5, [("D", 100, 0x1111), ("M", 17, 0xBBBB)])
    with Server(slmp_1e=True, memory=mem) as plc:
        with socket.create_connection(plc.address, timeout=2) as c:
            c.settimeout(2)
            command(c, bad, b"\x85\x5b\x5c\xc0")
    assert mem.read_words("D", 100, 1) == [0xAAAA]
    assert mem.read_bits("M", 16, 16) == [0] * 16


def test_1e_ascii_invalid_last_record_never_commits_earlier_records():
    mem = Memory("Q")
    mem.write_words("D", 100, [0xDEAD])
    bad = random_packet(5, [("D", 100, 0x1234), ("D", 101, 0x5678)], "ascii")
    bad = bad[:-1] + b"Z"  # malformed *last* encoded data nibble
    with Server(slmp_1e=True, memory=mem, listeners=[("udp", 0)]) as plc:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as c:
            c.settimeout(0.1)
            c.sendto(bad, plc.address)
            with pytest.raises(socket.timeout):
                c.recvfrom(1024)
    assert mem.read_words("D", 100, 2) == [0xDEAD, 0]


def test_1e_atomic_write_is_not_observable_half_committed_across_two_tcp_ports():
    memory = Memory("Q")
    memory.write_words("D", 100, [0x0001])
    entered = threading.Event()
    release = threading.Event()
    original = memory.write_atomic

    def held_atomic(ops):
        entered.set()
        assert release.wait(3), "test release must be signalled"
        return original(ops)

    memory.write_atomic = held_atomic
    with Server(slmp_1e=True, memory=memory,
                listeners=[("tcp", 0), ("tcp", 0)]) as plc:
        with socket.create_connection(plc.addresses[0][1:], timeout=2) as writer, \
                socket.create_connection(plc.addresses[1][1:], timeout=2) as reader:
            writer.settimeout(2)
            reader.settimeout(0.12)
            try:
                writer.sendall(random_packet(5, [("D", 100, 0x2345),
                                                  ("D", 101, 0x6789)]))
                assert entered.wait(2), "writer must reach guarded commit"
                reader.sendall(bytes.fromhex("01 FF 00 00 64 00 00 00 20 44 02 00"))
                with pytest.raises(socket.timeout):
                    reader.recv(1)  # held by common CPU request lock
            finally:
                release.set()
            reader.settimeout(2)
            assert read_exact(writer, 2) == b"\x85\x00"
            assert read_exact(reader, 6) == bytes.fromhex("81 00 45 23 89 67")
    assert memory.read_words("D", 100, 2) == [0x2345, 0x6789]


def test_memory_write_atomic_null_vs_empty_contract():
    mem = Memory("Q")
    mem.write_words("D", 100, [123])
    assert mem.write_atomic([]) is None  # documented no-op
    with pytest.raises(ValueError):
        mem.write_atomic(None)
    assert mem.read_words("D", 100, 1) == [123]
