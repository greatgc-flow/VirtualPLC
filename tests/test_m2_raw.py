"""M2 raw layout, malformed counts, atomicity and concurrency.

Expected golden bytes below are manual-derived and remain unverified.
Other packet builders are only test scaffolding, not golden oracles.
"""

from concurrent.futures import ThreadPoolExecutor
import socket
import struct
import threading

import pymcprotocol
import pytest

from test_m1_server_raw import device_data, exchange, request


pytestmark = pytest.mark.unverified


def entry(head, code=0xA8, value=None, size=2):
    result = head.to_bytes(3, "little") + bytes([code])
    return result if value is None else result + value.to_bytes(size, "little")


# Literal full frames, derived without production codec or client encoder.
GOLDENS = [
    ("read", "50 00 00 ff ff 03 00 10 00 04 00 03 04 00 00 01 01 00 00 00 a8 02 00 00 a8",
     "d0 00 00 ff ff 03 00 08 00 00 00 fe ff 78 56 34 12", ([-2], [0x12345678])),
    ("write", "50 00 00 ff ff 03 00 16 00 04 00 02 14 00 00 01 01 00 00 00 a8 fe ff 02 00 00 a8 78 56 34 12",
     "d0 00 00 ff ff 03 00 02 00 00 00", None),
    ("bits", "50 00 00 ff ff 03 00 11 00 04 00 02 14 01 00 02 01 00 00 90 01 02 00 00 90 00",
     "d0 00 00 ff ff 03 00 02 00 00 00", None),
]


@pytest.mark.parametrize("kind,frame,reply,result", GOLDENS)
def test_pinned_encoder_matches_manual_random_layout(monkeypatch, kind, frame, reply, result):
    client = pymcprotocol.Type3E()
    sent = []
    monkeypatch.setattr(client, "_send", sent.append)
    monkeypatch.setattr(client, "_recv", lambda: bytes.fromhex(reply))
    if kind == "read":
        observed = client.randomread(["D0"], ["D2"])
    elif kind == "write":
        observed = client.randomwrite(["D0"], [-2], ["D2"], [0x12345678])
    else:
        observed = client.randomwrite_bitunits(["M1", "M2"], [1, 0])
    assert observed == result
    assert sent == [bytes.fromhex(frame)]


@pytest.mark.parametrize("kind,frame,reply,result", GOLDENS)
def test_server_matches_manual_random_response(raw_socket, memory, kind, frame, reply, result):
    if kind == "read":
        memory.write_words("D", 0, [65534, 0, 0x5678, 0x1234])
    assert exchange(raw_socket, bytes.fromhex(frame)) == (0, bytes.fromhex(reply)[11:])
    if kind == "write":
        assert memory.read_words("D", 0, 4) == [65534, 0, 0x5678, 0x1234]
    elif kind == "bits":
        assert memory.read_bits("M", 1, 2) == [1, 0]


@pytest.mark.parametrize("command,subcommand,data", [
    (0x0403, 0, b""), (0x0403, 0, b"\x01"),
    (0x0403, 0, b"\x01\x00" + entry(0)[:-1]),
    (0x0403, 0, b"\x00\x00" + entry(0)),
    (0x1402, 0, b"\x01\x00" + entry(0, value=1)[:-1]),
    (0x1402, 0, b"\x00\x01" + entry(0, value=1, size=4) + b"\x00"),
    (0x1402, 1, b""), (0x1402, 1, b"\x01" + entry(0, 0x90, 1, 1)[:-1]),
    (0x1402, 1, b"\x00" + entry(0, 0x90, 1, 1)),
])
def test_payload_lengths_rejected_before_mutation(raw_socket, memory, command, subcommand, data):
    memory.write_words("D", 0, [7, 8])
    status, _ = exchange(raw_socket, request(command, subcommand, data))
    assert status == 0xC061
    assert memory.read_words("D", 0, 2) == [7, 8]


@pytest.mark.parametrize("kind", ["read-words", "read-dwords", "write-words", "write-dwords", "bits"])
@pytest.mark.parametrize("encoding", ["wrapped", "wide"])
def test_raw_256_entries_cannot_fit_byte_count(raw_socket, memory, kind, encoding):
    # There is no legal count=256 packet. Exercise wrapped and attempted uint16 counts.
    count = b"\x00" if encoding == "wrapped" else b"\x00\x01"
    if kind == "bits":
        command, subcommand = 0x1402, 1
        data = count + entry(0, 0x90, 1, 1) * 256
    else:
        command, subcommand = (0x0403 if kind.startswith("read") else 0x1402), 0
        data = (b"\x00" + count) if kind.endswith("dwords") else (count + b"\x00")
        data += entry(0, value=None if command == 0x0403 else 1,
                      size=4 if kind.endswith("dwords") else 2) * 256
    status, _ = exchange(raw_socket, request(command, subcommand, data))
    assert status != 0
    assert memory.read_words("D", 0, 2) == [0, 0]
    assert memory.read_bits("M", 0, 1) == [0]
    assert exchange(raw_socket, request(data=device_data())) == (0, b"\x00\x00")


@pytest.mark.parametrize("tail,expected", [
    (entry(8191, value=1, size=4), 0xC056),
    (entry(0, 0xFF, 1, 4), 0xC05C),
    (entry(1, 0x90, 1, 4), 0xC05C),
])
def test_mixed_random_write_invalid_tail_is_atomic(raw_socket, memory, tail, expected):
    memory.write_words("D", 0, [7, 8])
    data = b"\x01\x01" + entry(0, value=42) + tail
    status, _ = exchange(raw_socket, request(0x1402, 0, data))
    assert status == expected
    assert memory.read_words("D", 0, 2) == [7, 8]


@pytest.mark.parametrize("tail", [entry(0, 0x90, 2, 1), entry(0, 0xA8, 1, 1),
    entry(8192, 0x90, 1, 1), entry(0, 0xFF, 1, 1)])
def test_random_bit_invalid_tail_is_atomic(raw_socket, memory, tail):
    memory.write_bits("M", 0, [0, 1])
    data = b"\x02" + entry(0, 0x90, 1, 1) + tail
    assert exchange(raw_socket, request(0x1402, 1, data))[0] != 0
    assert memory.read_bits("M", 0, 2) == [0, 1]


@pytest.mark.parametrize("tail", [entry(8191), entry(0, 0xFF), entry(1, 0x90)])
def test_random_read_validates_dword_tail(raw_socket, memory, tail):
    memory.write_words("D", 0, [7])
    status, data = exchange(raw_socket, request(0x0403, 0, b"\x01\x01" + entry(0) + tail))
    assert status != 0
    assert data == b""
    assert memory.read_words("D", 0, 1) == [7]


@pytest.mark.parametrize("subcommand", [2, 3])
def test_iqr_random_subcommands_remain_unsupported(raw_socket, subcommand):
    assert exchange(raw_socket, request(0x1402, subcommand, b"\x00\x00"))[0] != 0


def test_random_requests_are_atomic_across_clients(server, memory):
    count = 64
    memory.write_words("D", 0, [0x1111] * count)
    barrier = threading.Barrier(3, timeout=5)

    def writer(value):
        body = bytes([count, 0]) + b"".join(entry(i, value=value) for i in range(count))
        with socket.create_connection(server.address, timeout=2) as connection:
            barrier.wait()
            for _ in range(20):
                assert exchange(connection, request(0x1402, 0, body)) == (0, b"")

    def reader():
        body = bytes([count, 0]) + b"".join(entry(i) for i in range(count))
        with socket.create_connection(server.address, timeout=2) as connection:
            barrier.wait()
            for _ in range(40):
                status, data = exchange(connection, request(0x0403, 0, body))
                assert status == 0
                assert data in (b"\x11\x11" * count, b"\xee\xee" * count)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(writer, 0x1111), pool.submit(writer, 0xEEEE), pool.submit(reader)]
        for future in futures:
            future.result(timeout=15)
