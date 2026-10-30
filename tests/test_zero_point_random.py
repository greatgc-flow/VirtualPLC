"""Tests for random access zero-point rejection and single-zero validity.

When total points == 0:
- random bit write (0x1402, bit subcommand) -> EndCode.RANDOM_BIT_POINTS_OUT_OF_RANGE (0xC053)
- random word/dword read (0x0403) and write (0x1402) -> EndCode.RANDOM_POINTS_OUT_OF_RANGE (0xC054)
Word-only and dword-only (one count zero, the other nonzero) remain valid.
"""

from itertools import product
import socket
import pytest

from test_m3_m4_raw import packet, receive
from virtual_plc.commands import EndCode
from virtual_plc.memory import Memory
from virtual_plc.server import Server

pytestmark = pytest.mark.unverified

FRAMES = ("3E", "4E")
WIRES = ("binary", "ascii")
PROFILES = ("Q", "iQ-R")
MATRIX = list(product(FRAMES, WIRES, PROFILES))


@pytest.mark.parametrize("frame,wire,profile", MATRIX)
@pytest.mark.parametrize("command", [0x0403, 0x1402])
def test_random_word_dword_both_zero_rejected(frame, wire, profile, command):
    memory = Memory(profile)
    memory.write_words("D", 0, [42, 43])
    subcommand = 2 if profile == "iQ-R" else 0
    data = b"0000" if wire == "ascii" else b"\x00\x00"

    with Server(memory=memory, profile=profile, port=0) as server:
        with socket.create_connection(server.address, timeout=1) as conn:
            conn.sendall(packet(frame, wire, command, subcommand, data))
            status, _ = receive(conn, frame, wire)
            assert status == EndCode.RANDOM_POINTS_OUT_OF_RANGE
            assert memory.read_words("D", 0, 2) == [42, 43]


@pytest.mark.parametrize("frame,wire,profile", MATRIX)
def test_random_bit_zero_rejected(frame, wire, profile):
    memory = Memory(profile)
    memory.write_bits("M", 0, [1])
    subcommand = 3 if profile == "iQ-R" else 1
    data = b"00" if wire == "ascii" else b"\x00"

    with Server(memory=memory, profile=profile, port=0) as server:
        with socket.create_connection(server.address, timeout=1) as conn:
            conn.sendall(packet(frame, wire, 0x1402, subcommand, data))
            status, _ = receive(conn, frame, wire)
            assert status == EndCode.RANDOM_BIT_POINTS_OUT_OF_RANGE
            assert memory.read_bits("M", 0, 1) == [1]


@pytest.mark.parametrize("frame,wire,profile", MATRIX)
def test_random_word_only_valid(frame, wire, profile):
    memory = Memory(profile)
    memory.write_words("D", 0, [0x1111])
    subcommand = 2 if profile == "iQ-R" else 0
    is_iqr = profile == "iQ-R"

    # 1. Random read word-only (word count 1, dword count 0)
    if wire == "ascii":
        read_data = b"0100" + (b"D***00000000" if is_iqr else b"D*000000")
        write_data = b"0100" + (b"D***00000000" if is_iqr else b"D*000000") + b"2222"
    else:
        desc = b"\x00\x00\x00\x00\xa8\x00" if is_iqr else b"\x00\x00\x00\xa8"
        read_data = b"\x01\x00" + desc
        write_data = b"\x01\x00" + desc + b"\x22\x22"

    with Server(memory=memory, profile=profile, port=0) as server:
        with socket.create_connection(server.address, timeout=1) as conn:
            conn.sendall(packet(frame, wire, 0x0403, subcommand, read_data))
            status, data = receive(conn, frame, wire)
            assert status == EndCode.OK
            assert data == (b"1111" if wire == "ascii" else b"\x11\x11")

            conn.sendall(packet(frame, wire, 0x1402, subcommand, write_data))
            status, _ = receive(conn, frame, wire)
            assert status == EndCode.OK
            assert memory.read_words("D", 0, 1) == [0x2222]


@pytest.mark.parametrize("frame,wire,profile", MATRIX)
def test_random_dword_only_valid(frame, wire, profile):
    memory = Memory(profile)
    memory.write_words("D", 0, [0x5678, 0x1234])
    subcommand = 2 if profile == "iQ-R" else 0
    is_iqr = profile == "iQ-R"

    # 2. Random read dword-only (word count 0, dword count 1)
    if wire == "ascii":
        read_data = b"0001" + (b"D***00000000" if is_iqr else b"D*000000")
        write_data = b"0001" + (b"D***00000000" if is_iqr else b"D*000000") + b"BEEFCAFE"
    else:
        desc = b"\x00\x00\x00\x00\xa8\x00" if is_iqr else b"\x00\x00\x00\xa8"
        read_data = b"\x00\x01" + desc
        write_data = b"\x00\x01" + desc + b"\xef\xbe\xfe\xca"

    with Server(memory=memory, profile=profile, port=0) as server:
        with socket.create_connection(server.address, timeout=1) as conn:
            conn.sendall(packet(frame, wire, 0x0403, subcommand, read_data))
            status, data = receive(conn, frame, wire)
            assert status == EndCode.OK
            assert data == (b"56781234" if wire == "ascii" else b"\x78\x56\x34\x12")

            conn.sendall(packet(frame, wire, 0x1402, subcommand, write_data))
            status, _ = receive(conn, frame, wire)
            assert status == EndCode.OK
            assert memory.read_words("D", 0, 2) == [0xBEEF, 0xCAFE]
