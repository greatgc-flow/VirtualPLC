"""Mitsubishi FX5 SLMP 1E 15H/16H diagnostics (JY997D56001-K pp.134-136).

Independent literal manufacturer vectors: these responses intentionally lack
the batch 1E 8X/status prefix. Simulator-only; no hardware oracle claim.
"""

import socket
import pytest
from virtual_plc import Server
from virtual_plc.memory import Memory
from virtual_plc.one_e import frame_size_1e

TYPE_BINARY = bytes.fromhex("15 FF 00 00")
TYPE_ASCII = b"15FF0000"
# Official manual p.136: "ABCDE" with length 05H, in both wire codes.
ECHO_BINARY = bytes.fromhex("16 FF 00 00 05 41 42 43 44 45")
ECHO_ASCII = b"16FF0000054142434445"


def received(conn, n):
    chunks = []
    remaining = n
    while remaining:
        data = conn.recv(remaining)
        assert data, "truncated 1E diagnostic reply"
        chunks.append(data)
        remaining -= len(data)
    return b"".join(chunks)


@pytest.mark.parametrize("message,answer", [
    (TYPE_BINARY, b"\xf3"),
    (TYPE_ASCII, b"F3"),
    (ECHO_BINARY, b"\x05ABCDE"),
    (ECHO_ASCII, b"054142434445"),
])
def test_1e_manual_literal_type_and_loopback(message, answer):
    with Server(slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as conn:
            conn.settimeout(2)
            conn.sendall(message)
            assert received(conn, len(answer)) == answer


def test_1e_tcp_fragmented_then_pipelined_mixed_wire_and_batch():
    memory = Memory("Q")
    memory.write_words("D", 100, [0x1234])
    batch = bytes.fromhex("01 FF 00 00 64 00 00 00 20 44 01 00")
    with Server(slmp_1e=True, memory=memory) as plc:
        with socket.create_connection(plc.address, timeout=2) as conn:
            conn.settimeout(2)
            for byte in ECHO_BINARY[:-1]:
                conn.sendall(bytes([byte]))
            conn.settimeout(0.05)
            with pytest.raises(socket.timeout):
                conn.recv(1)
            conn.settimeout(2)
            conn.sendall(ECHO_BINARY[-1:] + TYPE_ASCII + batch + ECHO_ASCII + TYPE_BINARY)
            expected = b"\x05ABCDE" + b"F3" + bytes.fromhex("81 00 34 12") + b"054142434445" + b"\xf3"
            assert received(conn, len(expected)) == expected


@pytest.mark.parametrize("wire", ["binary", "ascii"])
@pytest.mark.parametrize("size", [1, 254])
def test_1e_loopback_boundaries_and_no_plc_mutation(wire, size):
    content = (b"A" * size if wire == "binary" else b"41" * size)
    message = (bytes([0x16, 0xff, 0, 0, size]) + content if wire == "binary"
               else b"16FF0000" + f"{size:02X}".encode() + content)
    expected = (bytes([size]) + content if wire == "binary"
                else f"{size:02X}".encode() + content)
    mem = Memory("Q")
    mem.write_words("D", 100, [0x4567])
    with Server(slmp_1e=True, memory=mem) as plc:
        with socket.create_connection(plc.address, timeout=2) as conn:
            conn.settimeout(2)
            conn.sendall(message)
            assert received(conn, len(expected)) == expected
    assert mem.read_words("D", 100, 1) == [0x4567]


@pytest.mark.parametrize("payload", [
    bytes.fromhex("16 FF 00 00 00"),              # count 0
    bytes.fromhex("16 FF 00 00 FF"),              # count 255 exceeds max 254
    bytes.fromhex("14 FF 00 00"),                 # remote STOP not yet implemented
    bytes.fromhex("16 00 00 00 01 41"),           # PC != FF
    bytes.fromhex("15 FF 01 00"),                 # timer != 0
    b"16FF000000",                              # ASCII count 0
    b"16FF0000FF",                              # ASCII count 255 invalid
    b"13FF0000",                                # remote RUN not yet implemented
    b"16FF000001ZZ",                            # malformed hex encoded ASCII
    b"15FE0000",                                # ASCII PC != FF
    bytes.fromhex("50 00 00 FF FF 03 00"),      # 3E remains rejected
])
def test_1e_malformed_diagnostics_udp_drop_without_mutation(payload):
    memory = Memory("Q")
    memory.write_words("D", 1, [777])
    with Server(slmp_1e=True, memory=memory, listeners=[("udp", 0)]) as plc:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(0.1)
            udp.sendto(payload, plc.address)
            with pytest.raises(socket.timeout):
                udp.recvfrom(2048)
    assert memory.read_words("D", 1, 1) == [777]


@pytest.mark.parametrize("fragment", [
    b"\x15", b"\x15\xff\x00", b"15", b"15FF000",
    b"\x16\xff\x00\x00", b"16FF00000",
])
def test_1e_diagnostic_partial_header_is_not_yet_a_complete_frame(fragment):
    assert frame_size_1e(fragment) is None


def test_1e_diagnostic_command_sizing_has_no_3e_length_header():
    assert frame_size_1e(TYPE_BINARY) == 4
    assert frame_size_1e(TYPE_ASCII) == 8
    assert frame_size_1e(ECHO_BINARY) == 10
    assert frame_size_1e(ECHO_ASCII) == 20
    assert frame_size_1e(b"16FF0000FE" + b"41" * 254) == 518


def test_1e_diagnostic_udp_and_tcp_share_same_reply_hook_and_memory():
    memory = Memory("Q")
    def hook(reply):
        return reply + b"!"
    with Server(slmp_1e=True, memory=memory, response_hook=hook,
                listeners=[("tcp", 0), ("udp", 0)]) as plc:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(2)
            udp.sendto(TYPE_BINARY, plc.addresses[1][1:])
            assert udp.recvfrom(2048)[0] == b"\xf3!"
            udp.sendto(ECHO_ASCII, plc.addresses[1][1:])
            assert udp.recvfrom(2048)[0] == b"054142434445!"
        with socket.create_connection(plc.address, timeout=2) as conn:
            conn.settimeout(2)
            conn.sendall(TYPE_ASCII + ECHO_BINARY)
            assert received(conn, len(b"F3!" + b"\x05ABCDE!")) == b"F3!" + b"\x05ABCDE!"
    assert memory.read_words("D", 0, 1) == [0]


def test_1e_default_legacy_frames_unchanged_and_fx5_not_runnable():
    from virtual_plc.ethernet import model_catalog, reference_catalog
    assert Server().slmp_1e is False
    assert "fx5_enet" not in model_catalog()
    assert reference_catalog()["fx5_enet"]["implementation"] == "research_only"
