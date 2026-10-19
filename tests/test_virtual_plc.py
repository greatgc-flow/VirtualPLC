"""Independent pytest M1 tests. Deliberately loopback-only; no real PLC traffic."""
import socket
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from virtual_plc.memory import Memory
from virtual_plc.protocol import FrameError, SIMULATED_ERROR, process, nibble_pack, nibble_unpack
from virtual_plc.server import Server

ROUTE = bytes.fromhex("00 FF FF 03 00")

def make_request(cmd=0x0401, sub=0, address=100, dev=0xA8, count=1,
                 data=b"", route=ROUTE):
    body = (struct.pack("<HHH", 0x10, cmd, sub) + address.to_bytes(3, "little")
            + bytes([dev]) + struct.pack("<H", count) + data)
    return b"\x50\x00" + route + struct.pack("<H", len(body)) + body

def receive_exact(sock, n):
    result = b""
    while len(result) < n:
        block = sock.recv(n - len(result))
        if not block:
            raise EOFError("socket closed during response")
        result += block
    return result

def request_reply(sock, packet):
    sock.sendall(packet)
    header = receive_exact(sock, 9)
    assert header[:2] == b"\xd0\x00"
    assert header[2:7] == ROUTE
    size = int.from_bytes(header[7:9], "little")
    body = receive_exact(sock, size)
    return int.from_bytes(body[:2], "little"), body[2:]

@pytest.fixture
def memory():
    return Memory(d_size=1024, m_size=1024)

@pytest.fixture
def running_server():
    server = Server(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever,
        kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

def socket_to(port):
    sock = socket.create_connection(("127.0.0.1", port), timeout=1)
    sock.settimeout(2)
    return sock

def test_new_memory_is_zero(memory):
    assert memory.read_words(100, 4) == [0] * 4
    assert memory.read_bits(20, 3) == [0, 0, 0]

@pytest.mark.parametrize("value", [0, 1, 32767, 32768, 65535])
def test_word_roundtrip(memory, value):
    memory.write_words(100, [value])
    assert memory.read_words(100, 1) == [value]

@pytest.mark.parametrize("values", [[0], [1], [1, 0, 1], [0, 0, 1, 1]])
def test_bit_roundtrip(memory, values):
    memory.write_bits(10, values)
    assert memory.read_bits(10, len(values)) == values

@pytest.mark.parametrize("head,values", [
    (1023, [1, 2]), (-1, [1]), (0, []), (0, [65536]), (0, [-1]), (1024, [1])
])
def test_atomic_bad_word_write(memory, head, values):
    before = memory.snapshot()
    with pytest.raises(ValueError):
        memory.write_words(head, values)
    assert memory.snapshot() == before

@pytest.mark.parametrize("head,values", [
    (1023, [1, 0]), (-1, [1]), (0, []), (0, [2]), (0, [-1]), (1024, [1])
])
def test_atomic_bad_bit_write(memory, head, values):
    before = memory.snapshot()
    with pytest.raises(ValueError):
        memory.write_bits(head, values)
    assert memory.snapshot() == before

@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 6, 7, 8])
def test_bit_wire_roundtrip(count):
    values = [x % 2 for x in range(count)]
    assert nibble_unpack(nibble_pack(values), count) == values

def test_bad_odd_padding_rejected():
    with pytest.raises(ValueError):
        nibble_unpack(b"\x11", 1)

def test_reset_and_snapshot_version(memory):
    memory.write_words(5, [123])
    snapshot = memory.snapshot()
    memory.reset()
    assert memory.read_words(5, 1) == [0]
    assert snapshot["D"][5] == 123
    assert snapshot["version"] < memory.snapshot()["version"]

def test_concurrent_whole_vector_atomic(memory):
    a, b = [0x11] * 16, [0x22] * 16
    def write(values):
        for _ in range(200):
            memory.write_words(100, values)
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1, f2 = pool.submit(write, a), pool.submit(write, b)
        for _ in range(100):
            assert memory.read_words(100, 16) in ([0] * 16, a, b)
        f1.result(timeout=3)
        f2.result(timeout=3)

def test_protocol_word_read_write(memory):
    values = struct.pack("<HHH", 100, 65535, 4321)
    packet = make_request(cmd=0x1401, address=100, count=3, data=values)
    assert process(ROUTE, packet[9:], memory)[9:] == b"\x00\x00"
    packet = make_request(address=100, count=3)
    assert process(ROUTE, packet[9:], memory)[9:] == b"\x00\x00" + values

def test_protocol_bit_read_write(memory):
    values = nibble_pack([1, 0, 1, 1, 0])
    packet = make_request(cmd=0x1401, sub=1, dev=0x90, count=5, data=values)
    assert process(ROUTE, packet[9:], memory)[9:] == b"\x00\x00"
    packet = make_request(sub=1, dev=0x90, count=5)
    assert process(ROUTE, packet[9:], memory)[9:] == b"\x00\x00" + values

@pytest.mark.parametrize("packet", [
    make_request(cmd=0xFFFF),
    make_request(address=1024),
    make_request(count=0),
    make_request(sub=1, dev=0xA8),
    make_request(cmd=0x1401, count=2, data=b"\x01\x00"),
])
def test_provisional_error_does_not_mutate(memory, packet):
    before = memory.snapshot()
    reply = process(ROUTE, packet[9:], memory)
    assert int.from_bytes(reply[9:11], "little") == SIMULATED_ERROR
    assert memory.snapshot() == before

def test_incomplete_command_is_fatal(memory):
    with pytest.raises(FrameError):
        process(ROUTE, b"\x00\x01", memory)

def test_network_word_roundtrip(running_server):
    with socket_to(running_server) as sock:
        values = struct.pack("<HH", 321, 456)
        assert request_reply(sock, make_request(cmd=0x1401,
            address=200, count=2, data=values)) == (0, b"")
        assert request_reply(sock, make_request(address=200, count=2)) == (0, values)

def test_network_multi_client_shared_memory(running_server):
    with socket_to(running_server) as one, socket_to(running_server) as two:
        assert request_reply(one, make_request(cmd=0x1401,
            address=40, data=b"\x2a\x00")) == (0, b"")
        assert request_reply(two, make_request(address=40)) == (0, b"\x2a\x00")

def test_network_split_frame(running_server):
    with socket_to(running_server) as sock:
        packet = make_request(address=30)
        for byte in packet:
            sock.sendall(bytes([byte]))
        assert request_reply(sock, b"")[0] == 0

def test_network_multiple_frames_single_send(running_server):
    with socket_to(running_server) as sock:
        packet = make_request(address=1)
        sock.sendall(packet + packet)
        for _ in range(2):
            assert request_reply(sock, b"") == (0, b"\x00\x00")

@pytest.mark.parametrize("broken", [
    b"\x00\x00" + make_request()[2:],
    make_request()[:7] + b"\xff\xff" + make_request()[9:]
])
def test_bad_frame_closes_connection(running_server, broken):
    with socket_to(running_server) as sock:
        sock.sendall(broken)
        try:
            assert sock.recv(1) == b""
        except ConnectionResetError:
            pass

def test_non_loopback_bind_forbidden():
    with pytest.raises(ValueError):
        Server(("0.0.0.0", 0))
