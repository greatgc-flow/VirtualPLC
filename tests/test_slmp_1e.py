"""1E FX5 batch-frame wire contracts from Mitsubishi JY997D56001-K pp.41-49,119-127.

No real PLC parity claim. These literal byte vectors are independent of the
new 1E decoder; tests run only on local ephemeral sockets.
"""
import socket
import pytest

from virtual_plc import Server
from virtual_plc.__main__ import main
from virtual_plc.memory import Memory

# Manufacturer p.124: D100..102 binary request and response, values 1234,5,6789.
READ_D100 = bytes.fromhex("01 ff 00 00 64 00 00 00 20 44 03 00")
RESP_D100 = bytes.fromhex("81 00 34 12 05 00 89 67")
READ_D100_ASCII = b"01FF00004420000000640300"
RESP_D100_ASCII = b"8100123400056789"


def req(command, *, wire="binary", device="D", head=100, count=1,
        payload=b"", pc=0xff, timer=0, reserved=0):
    # Golden fixture builder follows manual 1E request layout, no runtime imports.
    name = device.encode("ascii").ljust(2, b" ")
    if wire == "ascii":
        return (f"{command:02X}{pc:02X}{timer:04X}".encode()
                + name.hex().upper().encode() + f"{head:08X}{count:02X}{reserved:02X}".encode()
                + payload)
    return (bytes((command, pc)) + timer.to_bytes(2, "little")
            + head.to_bytes(4, "little") + name[::-1] + bytes((count, reserved))
            + payload)


def receive_exact(conn, count):
    data = b""
    while len(data) < count:
        chunk = conn.recv(count - len(data))
        if not chunk:
            raise AssertionError("1E response truncated")
        data += chunk
    return data


def test_1e_is_optin_and_preflight_rejects_incompatible_fidelity():
    assert Server().slmp_1e is False
    assert Server(slmp_1e=True).slmp_1e is True
    with pytest.raises(ValueError):
        Server(slmp_1e=True, ethernet_model="qj71e71")
    with pytest.raises(ValueError):
        Server(slmp_1e=True, profile="iQ-R")
    from virtual_plc.faults import FaultPlan
    # Existing TCP fault injection only understands 3E/4E.
    with pytest.raises(ValueError):
        Server(slmp_1e=True, fault_plan=FaultPlan([]))


def test_1e_binary_and_ascii_literal_manual_vectors():
    memory = Memory("Q")
    memory.write_words("D", 100, [0x1234, 5, 0x6789])
    with Server(slmp_1e=True, memory=memory) as plc:
        for request, expected in ((READ_D100, RESP_D100),
                                  (READ_D100_ASCII, RESP_D100_ASCII)):
            with socket.create_connection(plc.address, timeout=2) as client:
                client.settimeout(2)
                client.sendall(request)
                assert receive_exact(client, len(expected)) == expected


@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_1e_batch_bit_read_write_word_read_write_shared_memory(wire):
    memory = Memory("Q")
    with Server(slmp_1e=True, memory=memory) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            bits = b"1011" if wire == "ascii" else b"\x10\x11"
            client.sendall(req(2, wire=wire, device="M", head=100, count=4, payload=bits))
            assert receive_exact(client, 4 if wire == "ascii" else 2) == (
                b"8200" if wire == "ascii" else b"\x82\x00")
            client.sendall(req(0, wire=wire, device="M", head=100, count=4))
            assert receive_exact(client, 8 if wire == "ascii" else 4) == (
                b"80001011" if wire == "ascii" else b"\x80\x00\x10\x11")
            words = b"1234BEEF" if wire == "ascii" else b"\x34\x12\xef\xbe"
            client.sendall(req(3, wire=wire, head=200, count=2, payload=words))
            assert receive_exact(client, 4 if wire == "ascii" else 2) == (
                b"8300" if wire == "ascii" else b"\x83\x00")
            client.sendall(req(1, wire=wire, head=200, count=2))
            assert receive_exact(client, 12 if wire == "ascii" else 6) == (
                b"81001234BEEF" if wire == "ascii" else b"\x81\x00\x34\x12\xef\xbe")
    assert memory.read_bits("M", 100, 4) == [1, 0, 1, 1]
    assert memory.read_words("D", 200, 2) == [0x1234, 0xBEEF]


def test_1e_bit_device_16_point_word_mode_and_alignment():
    memory = Memory("Q")
    with Server(slmp_1e=True, memory=memory) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(req(3, device="M", head=32, count=1, payload=b"\x34\x12"))
            assert receive_exact(client, 2) == b"\x83\x00"
            client.sendall(req(1, device="M", head=32, count=1))
            assert receive_exact(client, 4) == b"\x81\x00\x34\x12"
            # 1E word/group mode on bit devices must be 16-bit aligned.
            client.sendall(req(1, device="M", head=33, count=1))
            assert receive_exact(client, 4) == b"\x81\x5b\x5c\xc0"
    assert memory.read_bits("M", 32, 16)[2] == 1


def test_1e_bit_read_256_points_count_zero():
    memory = Memory("Q")
    memory.write_bits("M", 0, [1] * 256)
    with Server(slmp_1e=True, memory=memory) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(req(0, device="M", head=0, count=0))
            assert receive_exact(client, 130) == b"\x80\x00" + b"\x11" * 128


@pytest.mark.parametrize("request,expected", [
    (req(1, count=65), b"\x81\x5b\x52\xc0"),
    (req(0, device="D", count=1), b"\x80\x5b\x5c\xc0"),
    (req(1, device="M", count=33), b"\x81\x5b\x52\xc0"),
    (req(3, head=7999, count=2, payload=b"\x01\x00\x02\x00"), b"\x83\x5b\x56\xc0"),
])
def test_1e_error_contains_5b_and_manual_16bit_code(request, expected):
    with Server(slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(request)
            assert receive_exact(client, 4) == expected


@pytest.mark.parametrize("bad", [
    req(3, count=1, payload=b"\x01\x00", pc=0),
    req(3, count=1, payload=b"\x01\x00", reserved=1),
    req(3, wire="ascii", count=1, payload=b"0001", pc=0),
    bytes.fromhex("50 00 00 ff ff 03 00 0c 00 04 00 01 04 00 00 00 00 a8 01 00"),
])
def test_1e_invalid_header_does_not_mutate_memory(bad):
    memory = Memory("Q")
    with Server(slmp_1e=True, memory=memory, listeners=[("udp", 0)]) as plc:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(0.1)
            client.sendto(bad, plc.address)
            with pytest.raises(socket.timeout):
                client.recvfrom(4096)
    assert memory.read_words("D", 100, 1) == [0]


def test_1e_tcp_fragmentation_and_multiple_coalesced_requests():
    memory = Memory("Q")
    memory.write_words("D", 100, [0x1234, 5, 0x6789])
    with Server(slmp_1e=True, memory=memory) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            for byte in READ_D100[:-1]:
                client.sendall(bytes((byte,)))
            client.settimeout(0.05)
            with pytest.raises(socket.timeout):
                client.recv(1)
            client.settimeout(2)
            client.sendall(READ_D100[-1:] + READ_D100_ASCII + READ_D100)
            assert receive_exact(client, len(RESP_D100) + len(RESP_D100_ASCII) + len(RESP_D100)) == (
                RESP_D100 + RESP_D100_ASCII + RESP_D100)


def test_1e_udp_and_tcp_share_single_plc_state():
    with Server(slmp_1e=True, listeners=[("tcp", 0), ("udp", 0)]) as plc:
        host, port = plc.addresses[1][1:]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(2)
            udp.sendto(req(3, head=100, count=1, payload=b"\x34\x12"), (host, port))
            assert udp.recvfrom(4096)[0] == b"\x83\x00"
        with socket.create_connection(plc.address, timeout=2) as tcp:
            tcp.settimeout(2)
            tcp.sendall(req(1, head=100))
            assert receive_exact(tcp, 4) == b"\x81\x00\x34\x12"


def test_1e_cli_exposes_explicit_mode_without_mimicking_fx5_hardware():
    from virtual_plc.__main__ import build_parser
    parser = build_parser()
    assert "--slmp-1e" in parser._option_string_actions
    from virtual_plc.ethernet import model_catalog, reference_catalog
    assert "fx5_enet" not in model_catalog()
    assert reference_catalog()["fx5_enet"]["implementation"] == "research_only"
