"""iQ-R 4+2 vectors, wire-class rejection and raw-only LSTC coverage."""

import socket

import pymcprotocol
import pytest

from tables import PROFILES
from test_m1_server_raw import receive_exact
from test_m3_m4_client import TRANSPORTS
from test_m3_m4_raw import packet, receive
from test_m6_client import endpoints


pytestmark = pytest.mark.unverified
VECTORS = [
    ("3E", "binary", bytes.fromhex("50 00 00 ff ff 03 00 0e 00 04 00 01 04 02 00 04 03 02 01 a8 00 01 00"),
     bytes.fromhex("d0 00 00 ff ff 03 00 04 00 00 00 34 12")),
    ("4E", "binary", bytes.fromhex("54 00 ef be 00 00 00 ff ff 03 00 0e 00 04 00 01 04 02 00 04 03 02 01 a8 00 01 00"),
     bytes.fromhex("d4 00 ef be 00 00 00 ff ff 03 00 04 00 00 00 34 12")),
    ("3E", "ascii", b"5000" b"00FF03FF00" b"001C" b"000404010002D***169090600001",
     b"D000" b"00FF03FF00" b"0008" b"00001234"),
    ("4E", "ascii", b"5400" b"BEEF0000" b"00FF03FF00" b"001C" b"000404010002D***169090600001",
     b"D400" b"BEEF0000" b"00FF03FF00" b"0008" b"00001234"),
]


@pytest.mark.parametrize("frame,wire,frame_bytes,reply", VECTORS)
def test_real_encoder_matches_manual_4_plus_2_vector(monkeypatch, frame, wire, frame_bytes, reply):
    client = (pymcprotocol.Type4E if frame == "4E" else pymcprotocol.Type3E)(plctype="iQ-R")
    client.setaccessopt(commtype=wire)
    if frame == "4E":
        client.set_subheaderserial(0xBEEF)
    sent = []
    monkeypatch.setattr(client, "_send", sent.append)
    monkeypatch.setattr(client, "_recv", lambda: reply)
    assert client.batchread_wordunits("D16909060", 1) == [0x1234]
    assert sent == [frame_bytes]


@pytest.mark.parametrize("frame,wire,frame_bytes,reply", VECTORS)
def test_server_manual_4_plus_2_vector(endpoints, frame, wire, frame_bytes, reply):
    server = endpoints("iQ-R")
    server.memory.write_words("D", 16909060, [0x1234])
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(frame_bytes)
        assert receive_exact(connection, len(reply)) == reply


@pytest.mark.parametrize("profile", PROFILES, ids=[p.name for p in PROFILES])
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("command,bit", [(0x0401, False), (0x0401, True), (0x1401, False),
    (0x1401, True), (0x0403, False), (0x1402, False), (0x1402, True)])
def test_opposite_wire_class_subcommand_is_rejected(endpoints, profile, frame, wire, command, bit):
    server = endpoints(profile.name)
    wrong = (1 if bit else 0) if profile.name == "iQ-R" else (3 if bit else 2)
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(packet(frame, wire, command, wrong, b""))
        assert receive(connection, frame, wire)[0] != 0
        echo = b"0002OK" if wire == "ascii" else b"\x02\x00OK"
        connection.sendall(packet(frame, wire, 0x0619, data=echo))
        assert receive(connection, frame, wire) == (0, echo)


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_lstc_is_modelled_through_raw_requests(endpoints, frame, wire):
    server = endpoints("iQ-R")
    descriptor = b"LSTC00000000" if wire == "ascii" else bytes.fromhex("00 00 00 00 58 00")
    count = b"0001" if wire == "ascii" else b"\x01\x00"
    value = b"1" if wire == "ascii" else b"\x10"
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(packet(frame, wire, 0x1401, 3, descriptor + count + value))
        assert receive(connection, frame, wire) == (0, b"")
        connection.sendall(packet(frame, wire, 0x0401, 3, descriptor + count))
        assert receive(connection, frame, wire) == (0, value)
    assert server.memory.read_bits("LSTC", 0, 1) == [1]


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("bad_value", [2, 0x0101])
def test_random_bit_uint16_invalid_tail_is_atomic(endpoints, frame, wire, bad_value):
    server = endpoints("iQ-R")
    server.memory.write_bits("M", 0, [0, 1])
    data = (b"02M***000000000001M***00000001" + f"{bad_value:04X}".encode()) if wire == "ascii" else (
        b"\x02" + bytes.fromhex("00 00 00 00 90 00 01 00 01 00 00 00 90 00") + bad_value.to_bytes(2, "little"))
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(packet(frame, wire, 0x1402, 3, data))
        assert receive(connection, frame, wire)[0] != 0
    assert server.memory.read_bits("M", 0, 2) == [0, 1]


@pytest.mark.parametrize("frame", ["3E", "4E"])
def test_device_code_high_byte_is_not_discarded(endpoints, frame):
    server = endpoints("iQ-R")
    # 01A8 is not D (00A8), despite sharing the low byte.
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(packet(frame, "binary", 0x0401, 2, bytes.fromhex("00 00 00 00 a8 01 01 00")))
        assert receive(connection, frame, "binary")[0] != 0


@pytest.mark.parametrize("frame", ["3E", "4E"])
def test_ascii_eight_digit_overflow_is_error_not_truncation(endpoints, frame):
    server = endpoints("iQ-R")
    server.memory.write_words("D", 0, [7])
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(packet(frame, "ascii", 0x1402, 2, b"0200D***000000000001D***1000000000002"))
        assert receive(connection, frame, "ascii")[0] != 0
    assert server.memory.read_words("D", 0, 1) == [7]
