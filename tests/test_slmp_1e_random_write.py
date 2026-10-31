"""Literal 1E 04H/05H random-write vectors and atomicity gates.

Mitsubishi JY997D56001-K pp.128-131. Manual-derived, NOT physical oracle.
"""
import socket

import pytest

from virtual_plc import Server
from virtual_plc.memory import Memory
from virtual_plc.one_e import frame_size_1e


# Adapted from manufacturer examples: Y45(hex)=Y37(decimal), M60 and D26.
BIT_BINARY = bytes.fromhex(
    "04 FF 00 00 02 00 25 00 00 00 20 59 01 3C 00 00 00 20 4D 00"
)
BIT_ASCII = b"04FF00000200592000000025014D200000003C00"
WORD_BINARY = bytes.fromhex(
    "05 FF 00 00 02 00 10 00 00 00 20 59 29 7B 1A 00 00 00 20 44 34 12"
)
WORD_ASCII = b"05FF000002005920000000107B2944200000001A1234"


def exact(conn, size):
    output = b""
    while len(output) < size:
        value = conn.recv(size - len(output))
        assert value, "truncated SLMP 1E reply"
        output += value
    return output


@pytest.mark.parametrize("packet,expected,values", [
    (BIT_BINARY, b"\x84\x00", [1, 0]),
    (BIT_ASCII, b"8400", [1, 0]),
])
def test_1e_04_random_bit_write_manual_layout(packet, expected, values):
    memory = Memory("Q")
    with Server(memory=memory, slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(packet)
            assert exact(client, len(expected)) == expected
    assert memory.read_bits("Y", 37, 1) == values[:1]
    assert memory.read_bits("M", 60, 1) == values[1:]


@pytest.mark.parametrize("packet,expected", [
    (WORD_BINARY, b"\x85\x00"),
    (WORD_ASCII, b"8500"),
])
def test_1e_05_random_word_and_bit_group_write_manual_layout(packet, expected):
    memory = Memory("Q")
    with Server(memory=memory, slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(packet)
            assert exact(client, len(expected)) == expected
    assert memory.read_bits("Y", 16, 16) == [(0x7B29 >> i) & 1 for i in range(16)]
    assert memory.read_words("D", 26, 1) == [0x1234]


def test_1e_random_frame_sizes_are_command_specific():
    assert frame_size_1e(BIT_BINARY) == 20
    assert frame_size_1e(BIT_ASCII) == 40
    assert frame_size_1e(WORD_BINARY) == 22
    assert frame_size_1e(WORD_ASCII) == 44
    for packet in (BIT_BINARY, BIT_ASCII, WORD_BINARY, WORD_ASCII):
        assert frame_size_1e(packet[:-1]) == len(packet)


@pytest.mark.parametrize("packet,error", [
    (bytes.fromhex("04 FF 00 00 00 00"), b"\x84\x5b\x53\xc0"),  # zero bit count
    (bytes.fromhex("05 FF 00 00 00 00"), b"\x85\x5b\x54\xc0"),  # zero word count
    (bytes.fromhex("04 FF 00 00 01 00 64 00 00 00 20 44 01"), b"\x84\x5b\x5c\xc0"),
    (bytes.fromhex("05 FF 00 00 01 00 FF 1F 00 00 20 44 01 00"), b"\x85\x5b\x56\xc0"),
    (bytes.fromhex("05 FF 00 00 01 00 11 00 00 00 20 4D 01 00"), b"\x85\x5b\x5c\xc0"),
])
def test_1e_random_negative_contracts(packet, error):
    memory = Memory("Q")
    with Server(memory=memory, slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(packet)
            assert exact(client, len(error)) == error
    assert memory.read_bits("M", 0, 1) == [0]
    assert memory.read_words("D", 0, 1) == [0]


def test_1e_random_invalid_last_item_is_transactional():
    memory = Memory("Q")
    memory.write_words("D", 26, [0xAAAA])
    # Valid first item must not commit when second exceeds D7999.
    bad = (bytes.fromhex("05 FF 00 00 02 00")
           + bytes.fromhex("1A 00 00 00 20 44 34 12")
           + bytes.fromhex("40 1F 00 00 20 44 78 56"))
    with Server(memory=memory, slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(bad)
            assert exact(client, 4) == b"\x85\x5b\x56\xc0"
    assert memory.read_words("D", 26, 1) == [0xAAAA]


def test_1e_random_udp_and_tcp_pipelined_compatibility():
    with Server(slmp_1e=True, listeners=[("tcp", 0), ("udp", 0)]) as plc:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(2)
            udp.sendto(WORD_BINARY, plc.addresses[1][1:])
            assert udp.recvfrom(1024)[0] == b"\x85\x00"
        with socket.create_connection(plc.address, timeout=2) as tcp:
            tcp.settimeout(2)
            tcp.sendall(BIT_ASCII + WORD_ASCII)
            assert exact(tcp, 8) == b"84008500"
    assert plc.memory.read_words("D", 26, 1) == [0x1234]


@pytest.mark.parametrize("packet", [
    b"04FF00000201" + BIT_ASCII[12:],  # reserved not zero
    b"05FF00000200" + WORD_ASCII[12:-4] + b"ZZZZ",  # word nonhex
    bytes.fromhex("04 00 00 00 02 00") + BIT_BINARY[6:],
])
def test_1e_random_invalid_udp_drop_no_mutation(packet):
    memory = Memory("Q")
    with Server(memory=memory, slmp_1e=True, listeners=[("udp", 0)]) as plc:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(0.1)
            udp.sendto(packet, plc.address)
            with pytest.raises(socket.timeout):
                udp.recvfrom(1024)
    assert memory.read_bits("Y", 37, 1) == [0]
    assert memory.read_words("D", 26, 1) == [0]
