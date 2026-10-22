"""Raw transport detection, strict ASCII parsing, serials, and response sizing."""

import socket
import struct

import pytest

from test_m1_server_raw import receive_exact
from test_m3_m4_client import TRANSPORTS, connected, endpoint
from test_m3_m4_codec import ASCII_3E, ASCII_4E, BINARY_4E, VECTORS


pytestmark = pytest.mark.unverified


def packet(frame, wire, command=0x0401, subcommand=0, data=None, serial=0xBEEF):
    """Test scaffold only; literals in test_m3_m4_codec are the golden oracles."""
    if wire == "ascii":
        body = f"0004{command:04X}{subcommand:04X}".encode() + (b"D*0000000001" if data is None else data)
        prefix = b"5400" + f"{serial:04X}0000".encode() if frame == "4E" else b"5000"
        return prefix + b"00FF03FF00" + f"{len(body):04X}".encode() + body
    body = struct.pack("<HHH", 4, command, subcommand) + (bytes.fromhex("00 00 00 a8 01 00") if data is None else data)
    prefix = b"\x54\x00" + struct.pack("<HH", serial, 0) if frame == "4E" else b"\x50\x00"
    return prefix + b"\x00\xff\xff\x03\x00" + struct.pack("<H", len(body)) + body


def receive(connection, frame, wire, serial=0xBEEF):
    ascii_wire = wire == "ascii"
    width = 2 if ascii_wire else 1
    header = receive_exact(connection, (13 if frame == "4E" else 9) * width)
    prefix = (b"D400" if frame == "4E" else b"D000") if ascii_wire else (b"\xd4\x00" if frame == "4E" else b"\xd0\x00")
    assert header.startswith(prefix)
    offset = len(prefix)
    if frame == "4E":
        expected = f"{serial:04X}0000".encode() if ascii_wire else struct.pack("<HH", serial, 0)
        assert header[offset:offset + 4 * width] == expected
        offset += 4 * width
    assert header[offset:offset + 5 * width] == (b"00FF03FF00" if ascii_wire else b"\x00\xff\xff\x03\x00")
    length = int(header[-4:], 16) if ascii_wire else int.from_bytes(header[-2:], "little")
    body = receive_exact(connection, length)
    status_width = 2 * width
    status = int(body[:status_width], 16) if ascii_wire else int.from_bytes(body[:status_width], "little")
    return status, body[status_width:]


@pytest.mark.parametrize("frame,wire,frame_bytes,expected", VECTORS)
def test_server_literal_vectors(endpoint, frame, wire, frame_bytes, expected):
    server, memory = endpoint
    memory.write_words("D", 100, [0x1995, 0x1202, 0x1130])
    with socket.create_connection(server.address, timeout=0.5) as connection:
        connection.sendall(frame_bytes)
        assert receive_exact(connection, len(expected)) == expected


def test_merged_different_frame_and_wire_requests_on_one_connection(endpoint):
    server, memory = endpoint
    memory.write_words("D", 0, [0xABCD])
    modes = [("3E", "ascii"), ("4E", "binary"), ("4E", "ascii"), ("3E", "binary")]
    with socket.create_connection(server.address, timeout=0.5) as connection:
        connection.sendall(b"".join(packet(frame, wire) for frame, wire in modes))
        for frame, wire in modes:
            assert receive(connection, frame, wire) == (0, b"ABCD" if wire == "ascii" else b"\xcd\xab")


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_fragmented_header_and_body(endpoint, frame, wire):
    server, memory = endpoint
    memory.write_words("D", 0, [0x1234])
    request = packet(frame, wire)
    with socket.create_connection(server.address, timeout=0.5) as connection:
        for byte in request[:-1]:
            connection.sendall(bytes([byte]))
        connection.settimeout(0.02)
        with pytest.raises(socket.timeout):
            connection.recv(1)
        connection.settimeout(0.5)
        connection.sendall(request[-1:])
        assert receive(connection, frame, wire) == (0, b"1234" if wire == "ascii" else b"\x34\x12")


@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_4e_serial_echo_for_each_request(endpoint, wire):
    server, memory = endpoint
    memory.write_words("D", 0, [1])
    with socket.create_connection(server.address, timeout=0.5) as connection:
        for serial in (0, 1, 0x1234, 0xFFFF):
            connection.sendall(packet("4E", wire, serial=serial))
            assert receive(connection, "4E", wire, serial) == (0, b"0001" if wire == "ascii" else b"\x01\x00")


@pytest.mark.parametrize("frame", ["3E", "4E"])
def test_lowercase_hex_in_uppercase_hex_out(endpoint, frame):
    server, memory = endpoint
    with socket.create_connection(server.address, timeout=0.5) as connection:
        connection.sendall(packet(frame, "ascii", 0x1401, data=b"D*0000000001abcd").lower())
        assert receive(connection, frame, "ascii") == (0, b"")
        connection.sendall(packet(frame, "ascii").lower())
        assert receive(connection, frame, "ascii") == (0, b"ABCD")
    assert memory.read_words("D", 0, 1) == [0xABCD]


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_error_offsets_and_response_in_kind(endpoint, frame, wire):
    server, _ = endpoint
    with socket.create_connection(server.address, timeout=0.5) as connection:
        connection.sendall(packet(frame, wire, 0xFFFF, data=b""))
        assert receive(connection, frame, wire) == (0xC059, b"")


@pytest.mark.parametrize("frame", ["3E", "4E"])
@pytest.mark.parametrize("command,subcommand,data", [
    (0x1401, 0, b"D*0000000001GGGG"),
    (0x1401, 1, b"M*000000000210" + b"1"),
    (0x1401, 1, b"M*00000000021X"),
    (0x1402, 0, b"0101D*0000001234D*000002GGGGGGGG"),
    (0x1402, 1, b"02M*00000001D*00000001"),
    (0x0401, 0, b"X*00000A0001"),  # compat never autodetects a hex address.
    (0x0401, 0, b"D*+000010001"),
    (0x0401, 0, b"D* 000010001"),
])
def test_invalid_ascii_payload_is_atomic_and_connection_survives(endpoint, frame, command, subcommand, data):
    server, memory = endpoint
    memory.write_words("D", 0, [7, 8])
    memory.write_bits("M", 0, [0, 1])
    with socket.create_connection(server.address, timeout=0.5) as connection:
        connection.sendall(packet(frame, "ascii", command, subcommand, data))
        assert receive(connection, frame, "ascii")[0] != 0
        connection.sendall(packet(frame, "ascii"))
        assert receive(connection, frame, "ascii") == (0, b"0007")
    assert memory.read_words("D", 0, 2) == [7, 8]
    assert memory.read_bits("M", 0, 2) == [0, 1]


@pytest.mark.parametrize("frame", ["3E", "4E"])
def test_large_ascii_response_exceeds_client_recv_limit(endpoint, frame):
    server, memory = endpoint
    values = list(range(1100))
    memory.write_words("D", 0, values)
    with socket.create_connection(server.address, timeout=0.5) as connection:
        connection.sendall(packet(frame, "ascii", data=b"D*000000044C"))
        status, data = receive(connection, frame, "ascii")
        assert status == 0
        assert len(data) == 4400
        assert data == b"".join(f"{value:04X}".encode() for value in values)


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_response_hook_sees_encoded_frame(server_factory, frame, wire):
    frames = []

    def identity(response):
        frames.append(response)
        return response

    server = server_factory(response_hook=identity)
    with connected(server, frame, wire) as client:
        assert client.echo_test("aB") == (2, "aB")
    assert len(frames) == 1
    expected_prefix = (b"D400" if frame == "4E" else b"D000") if wire == "ascii" else (b"\xd4\x00" if frame == "4E" else b"\xd0\x00")
    assert frames[0].startswith(expected_prefix)
