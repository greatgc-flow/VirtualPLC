"""T5–T13/T16/T18: raw 3E binary transport, independent of production codec.

Frame helpers are test-only arithmetic, not independent golden byte oracles.
Exact end codes and memory-based protocol details await manual cross-check.
"""

from concurrent.futures import ThreadPoolExecutor
import socket
import struct
import threading

import pytest


pytestmark = pytest.mark.unverified


def request(command=0x0401, subcommand=0, data=b"", route=b"\x00\xff\xff\x03\x00"):
    body = struct.pack("<HHH", 4, command, subcommand) + data
    return b"\x50\x00" + route + struct.pack("<H", len(body)) + body


def device_data(head=0, code=0xA8, points=1, payload=b""):
    return head.to_bytes(3, "little") + bytes([code]) + struct.pack("<H", points) + payload


def receive_exact(connection, count):
    result = bytearray()
    while len(result) < count:
        chunk = connection.recv(count - len(result))
        assert chunk, f"EOF after {len(result)} of {count} bytes"
        result.extend(chunk)
    return bytes(result)


def response(connection, route=b"\x00\xff\xff\x03\x00"):
    header = receive_exact(connection, 9)
    assert header[:2] == b"\xd0\x00"
    assert header[2:7] == route
    length = int.from_bytes(header[7:9], "little")
    assert length >= 2
    body = receive_exact(connection, length)
    return int.from_bytes(body[:2], "little"), body[2:]


def exchange(connection, frame):
    connection.sendall(frame)
    return response(connection)


@pytest.mark.unverified
def test_error_table_has_provenance():
    from virtual_plc.commands import ERROR_CODES

    expected = {
        0x0000: "OK", 0xC051: "POINTS_OUT_OF_RANGE", 0xC056: "ADDRESS_OUT_OF_RANGE",
        0xC059: "UNSUPPORTED_COMMAND", 0xC05C: "REQUEST_DATA_ERROR", 0xC057: "DATA_LENGTH_MISMATCH",
    }
    for code, name in expected.items():
        assert ERROR_CODES[code] == {"name": name, "source": "design", "status": "unverified"}


@pytest.mark.unverified
@pytest.mark.parametrize("command, subcommand, data, expected", [
    (0x0401, 0, device_data(points=0), 0xC051),
    (0x0401, 0, device_data(points=4097), 0xC051),
    (0x0401, 0, device_data(head=8192), 0xC056),
    (0xFFFF, 0, b"", 0xC059),
    (0x1401, 0, device_data(points=2, payload=b"\x01\x00"), 0xC057),
    (0x1401, 0, device_data(points=1, payload=b"\x01\x00\x02\x00"), 0xC057),
    (0x1401, 1, device_data(code=0x90, points=2, payload=b"\x20"), 0xC05C),
    (0x1401, 1, device_data(code=0x90, points=2, payload=b"\x1f"), 0xC05C),
    (0x1401, 1, device_data(code=0x90, points=1, payload=b"\x11"), 0xC05C),
], ids=["T6-zero", "T6-over-limit", "T5-range", "T7-unsupported", "short-write",
        "long-write", "bad-high-nibble", "bad-low-nibble", "odd-padding"])
def test_decoded_errors_preserve_memory_and_connection(raw_socket, memory, command, subcommand, data, expected):
    memory.write_words("D", 0, [0xBEEF, 0xCAFE])
    memory.write_bits("M", 0, [0, 1])
    status, _ = exchange(raw_socket, request(command, subcommand, data))
    assert status == expected
    assert memory.read_words("D", 0, 2) == [0xBEEF, 0xCAFE]
    assert memory.read_bits("M", 0, 2) == [0, 1]
    assert exchange(raw_socket, request(data=device_data())) == (0, b"\xef\xbe")


@pytest.mark.parametrize("subcommand, data", [
    (2, device_data()), (3, device_data(code=0x90)),
    (1, device_data()), (0, device_data(code=0xFF)),
    (0, device_data(head=1, code=0x90)),
], ids=["T8-iQR-word", "T8-iQR-bit", "D-bit", "unknown-device", "unaligned-M-word"])
def test_invalid_access_has_unspecified_nonzero_code(raw_socket, subcommand, data):
    status, _ = exchange(raw_socket, request(subcommand=subcommand, data=data))
    assert status != 0


def test_t9_fragmentation_one_byte_at_a_time(raw_socket, scenarios):
    assert any(row["seed"] == "T9" and row["action"]["method"] == "bytewise" for row in scenarios)
    frame = request(data=device_data())
    for byte in frame[:-1]:
        raw_socket.sendall(bytes([byte]))
    raw_socket.settimeout(0.05)
    with pytest.raises(socket.timeout):
        raw_socket.recv(1)
    raw_socket.settimeout(2)
    raw_socket.sendall(frame[-1:])
    assert response(raw_socket) == (0, b"\x00\x00")


def test_t10_merged_write_then_read_is_fifo(raw_socket, scenarios):
    assert any(row["seed"] == "T10" for row in scenarios)
    write = request(0x1401, data=device_data(payload=b"\x34\x12"))
    read = request(data=device_data())
    raw_socket.sendall(write + read)
    assert response(raw_socket) == (0, b"")
    assert response(raw_socket) == (0, b"\x34\x12")


@pytest.mark.parametrize("cut", [8, 9, 22], ids=["header", "after-length", "write-payload"])
def test_t11_eof_mid_frame_does_not_mutate(server, memory, cut, scenarios):
    assert {row["action"]["variant"] for row in scenarios if row["seed"] == "T11"} == {
        "truncated_header", "truncated_payload"
    }
    memory.write_words("D", 0, [0xBEEF, 0xCAFE])
    frame = request(0x1401, data=device_data(points=2, payload=b"\x01\x00\x02\x00"))
    with socket.create_connection(server.address, timeout=2) as connection:
        connection.sendall(frame[:cut])
        connection.shutdown(socket.SHUT_WR)
        assert connection.recv(1) == b""
    assert memory.read_words("D", 0, 2) == [0xBEEF, 0xCAFE]
    with socket.create_connection(server.address, timeout=2) as connection:
        assert exchange(connection, request(data=device_data())) == (0, b"\xef\xbe")


@pytest.mark.parametrize("bad", [
    b"\x51\x00\x00\xff\xff\x03\x00\x06\x00\x04\x00\x01\x01\x00\x00",
    b"\x50\x00\x00\xff\xff\x03\x00\x05\x00\x04\x00\x01\x01\x00",
])
def test_malformed_frame_closes_only_bad_client(server, memory, bad):
    memory.write_words("D", 0, [9])
    with socket.create_connection(server.address, timeout=2) as connection:
        connection.sendall(bad)
        try:
            assert connection.recv(1) == b""
        except ConnectionResetError:
            pass  # OS may reset when closing with unread input.
    with socket.create_connection(server.address, timeout=2) as connection:
        assert exchange(connection, request(data=device_data())) == (0, b"\x09\x00")


@pytest.mark.unverified
@pytest.mark.parametrize("code, subcommand, payload, read_method, initial", [
    (0xA8, 0, b"\x00\x00\x01\x00", "read_words", [7]),
    (0x90, 1, b"\x01", "read_bits", [1]),
])
def test_t12_partial_range_write_is_atomic(server_factory, memory_factory, code, subcommand, payload, read_method, initial):
    device = "D" if code == 0xA8 else "M"
    memory = memory_factory(limits={device: (0, 31)})
    getattr(memory, "write_words" if device == "D" else "write_bits")(device, 31, initial)
    server = server_factory(memory=memory)
    with socket.create_connection(server.address, timeout=2) as connection:
        status, _ = exchange(connection, request(0x1401, subcommand, device_data(31, code, 2, payload)))
        assert status == 0xC056
    assert getattr(memory, read_method)(device, 31, 1) == initial


def test_t13_cross_client_visibility(server, scenarios):
    assert any(row["action"]["behavior"] == "multi_client_visibility" for row in scenarios)
    with socket.create_connection(server.address, timeout=2) as first, socket.create_connection(server.address, timeout=2) as second:
        assert exchange(first, request(0x1401, data=device_data(payload=b"\x34\x12"))) == (0, b"")
        assert exchange(second, request(data=device_data())) == (0, b"\x34\x12")
        assert exchange(first, request(data=device_data())) == (0, b"\x34\x12")


def test_t13_concurrent_writers_never_expose_torn_vectors(server, memory, scenarios):
    assert any(row["action"]["behavior"] == "overlap_concurrent" for row in scenarios)
    count = 128
    memory.write_words("D", 0, [0x1111] * count)
    barrier = threading.Barrier(3, timeout=5)
    patterns = (b"\x11\x11" * count, b"\xee\xee" * count)

    def writer(pattern):
        with socket.create_connection(server.address, timeout=2) as connection:
            barrier.wait()
            for _ in range(30):
                assert exchange(connection, request(0x1401, data=device_data(points=count, payload=pattern))) == (0, b"")

    def reader():
        with socket.create_connection(server.address, timeout=2) as connection:
            barrier.wait()
            observed = []
            for _ in range(60):
                status, data = exchange(connection, request(data=device_data(points=count)))
                assert status == 0
                assert data in patterns
                observed.append(data)
            return observed

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(writer, pattern) for pattern in patterns]
        reading = pool.submit(reader)
        for future in futures:
            future.result(timeout=15)
        assert len(reading.result(timeout=15)) == 60


def test_t16_large_valid_response_exceeds_client_recv_limit(raw_socket, memory):
    # 2050 words -> 4100 data bytes; server fixture explicitly permits 4096 points.
    values = list(range(2050))
    memory.write_words("D", 0, values)
    status, data = exchange(raw_socket, request(data=device_data(points=len(values))))
    assert status == 0
    assert len(data) == 4100
    assert data == struct.pack("<2050H", *values)


def test_valid_count_limit_and_last_address_are_inclusive(raw_socket, memory):
    memory.write_words("D", 8191, [0x1234])
    assert exchange(raw_socket, request(data=device_data(head=8191))) == (0, b"\x34\x12")
    status, data = exchange(raw_socket, request(data=device_data(points=4096)))
    assert status == 0
    assert data == b"\x00\x00" * 4096


def test_t18_m16_word_reads_m16_through_m31(raw_socket, memory):
    memory.write_bits("M", 16, [1] + [0] * 14 + [1])
    memory.write_bits("M", 256, [0] * 16)
    assert exchange(raw_socket, request(data=device_data(head=16, code=0x90))) == (0, b"\x01\x80")


def test_clean_disconnect_and_reconnect(server):
    with socket.create_connection(server.address, timeout=2):
        pass
    with socket.create_connection(server.address, timeout=2) as connection:
        assert exchange(connection, request(data=device_data())) == (0, b"\x00\x00")


def test_accepted_sockets_enable_tcp_nodelay(server_factory, monkeypatch):
    original = socket.socket.setsockopt
    configured = []

    def record_option(connection, level, option, value, *args):
        result = original(connection, level, option, value, *args)
        if level == socket.IPPROTO_TCP and option == socket.TCP_NODELAY:
            try:
                peer = connection.getpeername()
            except OSError:
                return result  # A listener or unconnected socket is not an accepted client.
            configured.append((connection.getsockname(), peer, connection.getsockopt(level, option)))
        return result

    monkeypatch.setattr(socket.socket, "setsockopt", record_option)
    server = server_factory()
    for _ in range(2):
        with socket.create_connection(server.address, timeout=2) as connection:
            peer = connection.getsockname()
            assert exchange(connection, request(data=device_data())) == (0, b"\x00\x00")
            assert (server.address, peer, 1) in configured


@pytest.mark.parametrize("prefix", [b"", b"\x50\x00\x00"])
def test_idle_or_incomplete_client_timeout_is_isolated(server_factory, prefix):
    server = server_factory(idle_timeout=0.1)
    with socket.create_connection(server.address, timeout=2) as connection:
        if prefix:
            connection.sendall(prefix)
        assert connection.recv(1) == b""
    with socket.create_connection(server.address, timeout=2) as connection:
        assert exchange(connection, request(data=device_data())) == (0, b"\x00\x00")


def test_stop_closes_incomplete_clients_and_is_idempotent(server_factory):
    server = server_factory()
    with socket.create_connection(server.address, timeout=2) as connection:
        connection.sendall(b"\x50")
        server.stop()
        server.stop()
        try:
            assert connection.recv(1) == b""
        except ConnectionResetError:
            pass


def test_response_hook_receives_full_response_and_transforms_it(server_factory):
    seen = []

    def transform(frame):
        seen.append(frame)
        return frame[:-1] + b"Z"

    server = server_factory(response_hook=transform)
    with socket.create_connection(server.address, timeout=2) as connection:
        assert exchange(connection, request(0x0619, data=b"\x01\x00A")) == (0, b"\x01\x00Z")
    assert seen == [bytes.fromhex("d0 00 00 ff ff 03 00 05 00 00 00 01 00 41")]


def test_identity_hook_runs_once_per_response(server_factory):
    seen = []

    def identity(frame):
        seen.append(frame)
        return frame

    server = server_factory(response_hook=identity)
    with socket.create_connection(server.address, timeout=2) as connection:
        connection.sendall(request(data=device_data()) * 2)
        assert response(connection) == (0, b"\x00\x00")
        assert response(connection) == (0, b"\x00\x00")
    assert seen == [bytes.fromhex("d0 00 00 ff ff 03 00 04 00 00 00 00 00")] * 2


def test_cputype_wire_body_is_padded_name_then_code(raw_socket):
    status, data = exchange(raw_socket, request(0x0101))
    assert status == 0
    assert data == b"VirtualPLC-Q\x00\x00\x00\x00\xff\xff"
