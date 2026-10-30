"""Manual random-access limits (SH-080008 p.98/105/108) and C053/C054 error codes.

Limits are manual-derived; C053/C054 path-to-code assignment is unverified.
"""

from itertools import product
import socket

import pymcprotocol
from pymcprotocol.mcprotocolerror import MCProtocolError
import pytest

from test_m3_m4_client import TRANSPORTS
from test_m3_m4_raw import packet, receive
from test_m6_client import connected_profile
from virtual_plc.commands import EndCode
from virtual_plc.memory import Memory
from virtual_plc.profiles import PROFILES, WIRE_CLASSES
from virtual_plc.server import Server

pytestmark = pytest.mark.unverified


@pytest.fixture(scope="module")
def limit_servers():
    servers = {}

    def get(profile, max_points=4096):
        key = (profile, max_points)
        if key not in servers:
            server = Server(profile=profile, max_points=max_points, port=0)
            server.start()
            servers[key] = server
        return servers[key]

    yield get
    for server in servers.values():
        server.stop()


def raw_descriptor(profile, wire, device, head):
    if wire == "ascii":
        code = f"{device:<4}" if profile == "iQ-R" else f"{device:<2}"
        code = code.replace(" ", "*")
        addr = f"{head:08d}" if profile == "iQ-R" else f"{head:06d}"
        return (code + addr).encode()
    code_val = 0x90 if device == "M" else 0xA8
    if profile == "iQ-R":
        return head.to_bytes(4, "little") + code_val.to_bytes(2, "little")
    return head.to_bytes(3, "little") + bytes([code_val])


def raw_random_read_payload(profile, wire, word_heads, dword_heads):
    w_cnt, dw_cnt = len(word_heads), len(dword_heads)
    counts = f"{w_cnt:02X}{dw_cnt:02X}".encode() if wire == "ascii" else bytes([w_cnt, dw_cnt])
    body = b"".join(raw_descriptor(profile, wire, "D", h) for h in word_heads)
    body += b"".join(raw_descriptor(profile, wire, "D", h) for h in dword_heads)
    return counts + body


def raw_random_write_payload(profile, wire, word_items, dword_items):
    w_cnt, dw_cnt = len(word_items), len(dword_items)
    counts = f"{w_cnt:02X}{dw_cnt:02X}".encode() if wire == "ascii" else bytes([w_cnt, dw_cnt])
    parts = [counts]
    for h, v in word_items:
        val = f"{v & 0xFFFF:04X}".encode() if wire == "ascii" else (v & 0xFFFF).to_bytes(2, "little")
        parts.append(raw_descriptor(profile, wire, "D", h) + val)
    for h, v in dword_items:
        val = f"{v & 0xFFFFFFFF:08X}".encode() if wire == "ascii" else (v & 0xFFFFFFFF).to_bytes(4, "little")
        parts.append(raw_descriptor(profile, wire, "D", h) + val)
    return b"".join(parts)


def raw_random_bit_payload(profile, wire, bit_items):
    cnt = len(bit_items)
    counts = f"{cnt:02X}".encode() if wire == "ascii" else bytes([cnt])
    parts = [counts]
    for h, v in bit_items:
        if wire == "ascii":
            val = (f"{v:04X}" if profile == "iQ-R" else f"{v:02X}").encode()
        else:
            val = v.to_bytes(2 if profile == "iQ-R" else 1, "little")
        parts.append(raw_descriptor(profile, wire, "M", h) + val)
    return b"".join(parts)


def test_wire_class_random_limit_fields():
    q = WIRE_CLASSES["Q-class"]
    iqr = WIRE_CLASSES["iQ-R"]
    assert (q.random_read_max, q.random_write_weight_max, q.random_bit_max) == (192, 1920, 188)
    assert (iqr.random_read_max, iqr.random_write_weight_max, iqr.random_bit_max) == (96, 960, 94)
    for name in ("Q", "L", "QnA", "iQ-L"):
        assert PROFILES[name].wire is q
    assert PROFILES["iQ-R"].wire is iqr


# --- Random Read (0x0403): words + dwords <= 192 (Q-class) / 96 (iQ-R) ---

@pytest.mark.parametrize("profile,cap", [("Q", 192), ("L", 192), ("iQ-R", 96)])
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("split", ["words_only", "dwords_only", "mixed"])
def test_random_read_in_limit_boundaries_real_client(limit_servers, profile, cap, frame, wire, split):
    server = limit_servers(profile)
    if split == "words_only":
        w_cnt, dw_cnt = cap, 0
    elif split == "dwords_only":
        w_cnt, dw_cnt = 0, cap
    else:
        w_cnt, dw_cnt = cap // 2, cap - (cap // 2)
    words = [f"D{i}" for i in range(w_cnt)]
    dwords = [f"D{500 + 2 * i}" for i in range(dw_cnt)]
    server.memory.write_words("D", 0, [i + 1 for i in range(w_cnt)] if w_cnt else [0])
    if dw_cnt:
        server.memory.write_words("D", 500, [0x1111, 0x2222] * dw_cnt)
    with connected_profile(server, frame, wire) as client:
        res_w, res_dw = client.randomread(words, dwords)
        assert len(res_w) == w_cnt and len(res_dw) == dw_cnt
        if w_cnt:
            assert res_w[0] == 1 and res_w[-1] == w_cnt


@pytest.mark.parametrize("profile,cap", [("Q", 192), ("L", 192), ("QnA", 192), ("iQ-L", 192), ("iQ-R", 96)])
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("over_case", ["words_plus_one", "dwords_plus_one", "mixed_plus_one", "max_255_each"])
def test_random_read_over_limit_raw_and_client(limit_servers, profile, cap, frame, wire, over_case):
    server = limit_servers(profile)
    sub = server.memory.profile.wire.word_subcommand
    if over_case == "words_plus_one":
        w_cnt, dw_cnt = cap + 1, 0
    elif over_case == "dwords_plus_one":
        w_cnt, dw_cnt = 0, cap + 1
    elif over_case == "mixed_plus_one":
        w_cnt, dw_cnt = cap // 2, cap - (cap // 2) + 1
    else:
        w_cnt, dw_cnt = 255, 255

    payload = raw_random_read_payload(profile, wire, range(w_cnt), range(500, 500 + 2 * dw_cnt, 2))
    with socket.create_connection(server.address, timeout=1) as conn:
        conn.sendall(packet(frame, wire, 0x0403, sub, payload))
        status, _ = receive(conn, frame, wire)
        assert status == EndCode.RANDOM_POINTS_OUT_OF_RANGE

    if over_case == "mixed_plus_one" and (frame, wire) == ("3E", "binary"):
        with connected_profile(server, frame, wire) as client:
            with pytest.raises(MCProtocolError) as err:
                client.randomread([f"D{i}" for i in range(w_cnt)], [f"D{500 + 2 * i}" for i in range(dw_cnt)])
            assert err.value.errorcode == "0xC054"


# --- Random Write (0x1402 word/dword): words*12 + dwords*14 <= 1920 (Q) / 960 (iQ-R) ---
# Exact weighted boundary mixes:
# Q (1920): (160, 0) -> 1920; (146, 12) -> 1752+168=1920; (90, 60) -> 1080+840=1920; (20, 120) -> 240+1680=1920;
#           dword-only max is (0, 137) -> 1918 (since 137*14=1918 <= 1920 < 138*14=1932), plus (1, 136) -> 12+1904=1916.
# iQ-R (960): (80, 0) -> 960; (73, 6) -> 876+84=960; (45, 30) -> 540+420=960; (10, 60) -> 120+840=960;
#             (3, 66) -> 36+924=960; dword-only max is (0, 68) -> 952 (68*14=952 <= 960 < 69*14=966).

Q_WRITE_IN_LIMIT = [
    (160, 0),    # word-only exact 1920
    (0, 137),    # dword-only max 1918
    (146, 12),   # exact 1920
    (90, 60),    # exact 1920
    (20, 120),   # exact 1920
    (6, 132),    # exact 1920
]

IQR_WRITE_IN_LIMIT = [
    (80, 0),     # word-only exact 960
    (0, 68),     # dword-only max 952
    (73, 6),     # exact 960
    (45, 30),    # exact 960
    (10, 60),    # exact 960
    (3, 66),     # exact 960
]


@pytest.mark.parametrize("profile,cases", [("Q", Q_WRITE_IN_LIMIT), ("iQ-R", IQR_WRITE_IN_LIMIT)])
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_random_write_weighted_boundaries_in_limit_real_client(limit_servers, profile, cases, frame, wire):
    server = limit_servers(profile)
    cap = server.memory.profile.wire.random_write_weight_max
    with connected_profile(server, frame, wire) as client:
        for w_cnt, dw_cnt in cases:
            assert w_cnt * 12 + dw_cnt * 14 <= cap
            words = [f"D{i}" for i in range(w_cnt)]
            dwords = [f"D{1000 + 2 * i}" for i in range(dw_cnt)]
            w_vals = [(i % 1000) - 500 for i in range(w_cnt)]
            dw_vals = [0x12340000 + i for i in range(dw_cnt)]
            client.randomwrite(words, w_vals, dwords, dw_vals)
            # Verify via randomread (note w_cnt + dw_cnt <= 160 <= 192 for Q, <= 80 <= 96 for iQ-R)
            assert client.randomread(words, dwords) == (w_vals, dw_vals)


Q_WRITE_OVER_LIMIT = [
    (161, 0),    # word-only max+1 -> 1932
    (0, 138),    # dword-only max+1 -> 1932
    (160, 1),    # exact 1920 + 1 dword -> 1934
    (146, 13),   # exact 1920 + 1 dword -> 1934
    (147, 12),   # exact 1920 + 1 word -> 1932
    (90, 61),    # exact 1920 + 1 dword -> 1934
    (91, 60),    # exact 1920 + 1 word -> 1932
    (1, 137),    # 1918 + 12 = 1930 > 1920
    (255, 255),  # uint8 max
]

IQR_WRITE_OVER_LIMIT = [
    (81, 0),     # word-only max+1 -> 972
    (0, 69),     # dword-only max+1 -> 966
    (80, 1),     # exact 960 + 1 dword -> 974
    (73, 7),     # exact 960 + 1 dword -> 974
    (74, 6),     # exact 960 + 1 word -> 972
    (45, 31),    # exact 960 + 1 dword -> 974
    (46, 30),    # exact 960 + 1 word -> 972
    (3, 67),     # exact 960 + 1 dword -> 974
    (4, 66),     # exact 960 + 1 word -> 972
    (1, 68),     # 952 + 12 = 964 > 960
    (255, 255),  # uint8 max
]


@pytest.mark.parametrize("profile,cases", [
    ("Q", Q_WRITE_OVER_LIMIT), ("L", Q_WRITE_OVER_LIMIT[:3]),
    ("iQ-R", IQR_WRITE_OVER_LIMIT),
])
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_random_write_weighted_over_limit_raw_frames(limit_servers, profile, cases, frame, wire):
    server = limit_servers(profile)
    sub = server.memory.profile.wire.word_subcommand
    cap = server.memory.profile.wire.random_write_weight_max
    server.memory.write_words("D", 0, [0x7777, 0x8888])
    with socket.create_connection(server.address, timeout=1) as conn:
        for w_cnt, dw_cnt in cases:
            assert w_cnt * 12 + dw_cnt * 14 > cap
            w_items = [(i, 0x1111) for i in range(w_cnt)]
            dw_items = [(1000 + 2 * i, 0x22223333) for i in range(dw_cnt)]
            payload = raw_random_write_payload(profile, wire, w_items, dw_items)
            conn.sendall(packet(frame, wire, 0x1402, sub, payload))
            status, _ = receive(conn, frame, wire)
            assert status == EndCode.RANDOM_POINTS_OUT_OF_RANGE
    assert server.memory.read_words("D", 0, 2) == [0x7777, 0x8888]


# --- Random Bit Write (0x1402 bit subcommand): points <= 188 (Q) / 94 (iQ-R) ---

@pytest.mark.parametrize("profile,cap", [("Q", 188), ("L", 188), ("iQ-R", 94)])
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_random_bit_write_in_limit_boundary_real_client(limit_servers, profile, cap, frame, wire):
    server = limit_servers(profile)
    bits = [f"M{i}" for i in range(cap)]
    values = [(i + 1) % 2 for i in range(cap)]
    with connected_profile(server, frame, wire) as client:
        client.randomwrite_bitunits(bits, values)
        assert client.batchread_bitunits("M0", cap) == values


@pytest.mark.parametrize("profile,cap", [("Q", 188), ("L", 188), ("QnA", 188), ("iQ-L", 188), ("iQ-R", 94)])
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("extra", [1, 67])  # cap+1 (189 / 95) and 255 (for Q: 188+67=255)
def test_random_bit_write_over_limit_raw_frames(limit_servers, profile, cap, frame, wire, extra):
    server = limit_servers(profile)
    sub = server.memory.profile.wire.bit_subcommand
    count = min(255, cap + extra)
    server.memory.write_bits("M", 0, [0, 1])
    payload = raw_random_bit_payload(profile, wire, [(i, 1) for i in range(count)])
    with socket.create_connection(server.address, timeout=1) as conn:
        conn.sendall(packet(frame, wire, 0x1402, sub, payload))
        status, _ = receive(conn, frame, wire)
        assert status == EndCode.RANDOM_BIT_POINTS_OUT_OF_RANGE
    assert server.memory.read_bits("M", 0, 2) == [0, 1]


# --- Check order & independence from --max-points ---

@pytest.mark.parametrize("profile,read_cap,write_cap_w,bit_cap", [
    ("Q", 192, 160, 188),
    ("iQ-R", 96, 80, 94),
])
def test_check_order_zero_then_over_limit_then_length_and_device(limit_servers, profile, read_cap, write_cap_w, bit_cap):
    """Check order:
    1. Zero total -> C053 (bit) / C054 (word/dword) (when frame is structurally valid or before over-limit)
    2. Over-limit -> C053 (bit) / C054 (word/dword), checked BEFORE payload length mismatch (C057) and device/range (C05C/C056).
    3. In-limit with bad payload length -> C057.
    4. In-limit with bad device/range -> C05C/C056.
    """
    server = limit_servers(profile)
    wire_spec = server.memory.profile.wire
    w_sub, b_sub = wire_spec.word_subcommand, wire_spec.bit_subcommand

    with socket.create_connection(server.address, timeout=1) as conn:
        # 1. Zero total -> C054 / C053
        conn.sendall(packet("3E", "binary", 0x0403, w_sub, b"\x00\x00"))
        assert receive(conn, "3E", "binary")[0] == EndCode.RANDOM_POINTS_OUT_OF_RANGE

        conn.sendall(packet("3E", "binary", 0x1402, w_sub, b"\x00\x00"))
        assert receive(conn, "3E", "binary")[0] == EndCode.RANDOM_POINTS_OUT_OF_RANGE

        conn.sendall(packet("3E", "binary", 0x1402, b_sub, b"\x00"))
        assert receive(conn, "3E", "binary")[0] == EndCode.RANDOM_BIT_POINTS_OUT_OF_RANGE

        # 2. Over-limit count with truncated/mismatched payload -> C054 / C053 (checked before length check C057!)
        conn.sendall(packet("3E", "binary", 0x0403, w_sub, bytes([read_cap + 1, 0])))
        assert receive(conn, "3E", "binary")[0] == EndCode.RANDOM_POINTS_OUT_OF_RANGE

        conn.sendall(packet("3E", "binary", 0x1402, w_sub, bytes([write_cap_w + 1, 0])))
        assert receive(conn, "3E", "binary")[0] == EndCode.RANDOM_POINTS_OUT_OF_RANGE

        conn.sendall(packet("3E", "binary", 0x1402, b_sub, bytes([bit_cap + 1])))
        assert receive(conn, "3E", "binary")[0] == EndCode.RANDOM_BIT_POINTS_OUT_OF_RANGE

        # Over-limit with invalid device code (0xFF) in full-length binary frame -> C054 / C053 before C05C
        bad_dev = b"\x00" * wire_spec.address_size + b"\xff" * wire_spec.code_size
        conn.sendall(packet("3E", "binary", 0x0403, w_sub, bytes([read_cap + 1, 0]) + bad_dev * (read_cap + 1)))
        assert receive(conn, "3E", "binary")[0] == EndCode.RANDOM_POINTS_OUT_OF_RANGE

        conn.sendall(packet("3E", "binary", 0x1402, w_sub, bytes([write_cap_w + 1, 0]) + (bad_dev + b"\x00\x00") * (write_cap_w + 1)))
        assert receive(conn, "3E", "binary")[0] == EndCode.RANDOM_POINTS_OUT_OF_RANGE

        conn.sendall(packet("3E", "binary", 0x1402, b_sub, bytes([bit_cap + 1]) + (bad_dev + b"\x00" * wire_spec.bit_value_size) * (bit_cap + 1)))
        assert receive(conn, "3E", "binary")[0] == EndCode.RANDOM_BIT_POINTS_OUT_OF_RANGE

        # 3. In-limit count with truncated payload -> C057 (DATA_LENGTH_MISMATCH)
        conn.sendall(packet("3E", "binary", 0x0403, w_sub, bytes([read_cap, 0])))
        assert receive(conn, "3E", "binary")[0] == EndCode.DATA_LENGTH_MISMATCH

        conn.sendall(packet("3E", "binary", 0x1402, w_sub, bytes([write_cap_w, 0])))
        assert receive(conn, "3E", "binary")[0] == EndCode.DATA_LENGTH_MISMATCH

        conn.sendall(packet("3E", "binary", 0x1402, b_sub, bytes([bit_cap])))
        assert receive(conn, "3E", "binary")[0] == EndCode.DATA_LENGTH_MISMATCH


@pytest.mark.parametrize("profile,read_cap,write_w,bit_cap", [
    ("Q", 192, 160, 188),
    ("iQ-R", 96, 80, 94),
])
def test_random_limits_independent_of_max_points(limit_servers, profile, read_cap, write_w, bit_cap):
    # Even with max_points=1, random access allows up to the profile's manual random limits,
    # while batch is capped at max_points=1.
    server = limit_servers(profile, max_points=1)
    with connected_profile(server, "3E", "binary") as client:
        # Batch > 1 fails with C051
        with pytest.raises(MCProtocolError) as err:
            client.batchread_wordunits("D0", 2)
        assert err.value.errorcode == "0xC051"

        # Random at full manual capacity succeeds despite max_points=1
        words = [f"D{i}" for i in range(write_w)]
        vals = [i for i in range(write_w)]
        client.randomwrite(words, vals, [], [])
        read_words = [f"D{i}" for i in range(read_cap)]
        res_w, res_dw = client.randomread(read_words, [])
        assert len(res_w) == read_cap and res_w[:write_w] == vals

        bits = [f"M{i}" for i in range(bit_cap)]
        b_vals = [i % 2 for i in range(bit_cap)]
        client.randomwrite_bitunits(bits, b_vals)
        assert server.memory.read_bits("M", 0, bit_cap) == b_vals

    # Conversely, even with max_points=5000, random access over manual limit is rejected
    big_server = limit_servers(profile, max_points=5000)
    sub = big_server.memory.profile.wire.word_subcommand
    payload = raw_random_read_payload(profile, "binary", range(read_cap + 1), [])
    with socket.create_connection(big_server.address, timeout=1) as conn:
        conn.sendall(packet("3E", "binary", 0x0403, sub, payload))
        assert receive(conn, "3E", "binary")[0] == EndCode.RANDOM_POINTS_OUT_OF_RANGE
