"""Manual batch limits (SH-080008 p.87/91/96, Ethernet E71 column) and C051/C052 error codes.

Limits are manual-derived per profile, wire encoding, and unit; C051/C052 path-to-code
assignment is unverified.
"""

from itertools import product
import socket
import struct

import pymcprotocol
from pymcprotocol.mcprotocolerror import MCProtocolError
import pytest

from test_m1_server_raw import receive_exact
from test_m3_m4_client import TRANSPORTS
from test_m3_m4_raw import packet, receive
from test_m6_client import connected_profile
from virtual_plc import __main__ as cli
from virtual_plc.codec import Request, normalize_request
from virtual_plc.commands import ERROR_CODES, EndCode
from virtual_plc.memory import Memory
from virtual_plc.profiles import BATCH_MAX, PROFILES
from virtual_plc.server import Server

pytestmark = pytest.mark.unverified


@pytest.fixture(scope="module")
def batch_servers():
    servers = {}

    def get(profile, max_points=None):
        key = (profile, max_points)
        if key not in servers:
            server = Server(profile=profile, max_points=max_points, port=0)
            server.start()
            servers[key] = server
        return servers[key]

    yield get
    for server in servers.values():
        server.stop()


def raw_batch_payload(profile, wire, unit, points, write=False, value=1):
    device = "M" if unit == "bit" else "D"
    if wire == "ascii":
        code = (f"{device:<4}" if profile == "iQ-R" else f"{device:<2}").replace(" ", "*")
        addr = f"{0:08d}" if profile == "iQ-R" else f"{0:06d}"
        head = (code + addr + f"{points:04X}").encode()
        if not write:
            return head
        if unit == "bit":
            return head + (b"1" if value else b"0") * points
        return head + f"{value & 0xFFFF:04X}".encode() * points
    code_val = 0x90 if unit == "bit" else 0xA8
    if profile == "iQ-R":
        head = (0).to_bytes(4, "little") + code_val.to_bytes(2, "little") + struct.pack("<H", points)
    else:
        head = (0).to_bytes(3, "little") + bytes([code_val]) + struct.pack("<H", points)
    if not write:
        return head
    if unit == "bit":
        byte_val = 0x11 if value else 0x00
        data = bytearray([byte_val] * (points // 2))
        if points % 2:
            data.append(0x10 if value else 0x00)
        return head + bytes(data)
    return head + struct.pack("<H", value & 0xFFFF) * points


def test_profile_batch_max_table_and_error_provenance():
    expected_std = {("binary", "word"): 960, ("ascii", "word"): 960, ("binary", "bit"): 7168, ("ascii", "bit"): 3584}
    expected_qna = {("binary", "word"): 480, ("ascii", "word"): 480, ("binary", "bit"): 3584, ("ascii", "bit"): 1792}
    for name in ("Q", "L", "iQ-L", "iQ-R"):
        assert PROFILES[name].batch_max == expected_std
        for (wire, unit), cap in expected_std.items():
            assert BATCH_MAX[name, wire, unit] == cap
    assert PROFILES["QnA"].batch_max == expected_qna
    for (wire, unit), cap in expected_qna.items():
        assert BATCH_MAX["QnA", wire, unit] == cap
    assert EndCode.POINTS_OUT_OF_RANGE == 0xC051
    assert EndCode.BIT_POINTS_OUT_OF_RANGE == 0xC052
    assert ERROR_CODES[0xC051] == {"name": "POINTS_OUT_OF_RANGE", "source": "manual", "status": "unverified"}
    assert ERROR_CODES[0xC052] == {"name": "BIT_POINTS_OUT_OF_RANGE", "source": "manual", "status": "unverified"}


def test_normalize_request_preserves_wire_format():
    for profile in ("Q", "QnA", "iQ-R"):
        prof = PROFILES[profile]
        sub = prof.wire.word_subcommand
        for frame in ("3E", "4E"):
            for wire in ("binary", "ascii"):
                payload = raw_batch_payload(profile, wire, "word", 1)
                req = Request((0, 0xFF, 0x03FF, 0), 4, 0x0401, sub, payload, frame=frame, wire=wire)
                norm = normalize_request(req, prof)
                assert norm.wire == wire
                assert norm.frame == frame


def test_default_max_points_is_none_on_server_and_cli():
    server = Server()
    assert server._max_points is None
    parser = cli.build_parser()
    args = parser.parse_args([])
    assert args.max_points is None


def test_direct_memory_calls_are_not_capped_by_batch_limits():
    for profile in ("Q", "QnA", "iQ-R"):
        mem = Memory(profile)
        mem.write_words("D", 0, [1] * 2000)
        assert len(mem.read_words("D", 0, 2000)) == 2000
        mem.write_bits("M", 0, [1] * 8000)
        assert len(mem.read_bits("M", 0, 8000)) == 8000


@pytest.mark.parametrize("profile", ["Q", "L", "QnA", "iQ-L", "iQ-R"])
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("unit", ["word", "bit"])
@pytest.mark.parametrize("write", [False, True], ids=["read", "write"])
def test_batch_limits_0_1_cap_and_cap_plus_1_raw(batch_servers, profile, frame, wire, unit, write):
    server = batch_servers(profile)
    prof = server.memory.profile
    wire_spec = prof.wire
    sub = wire_spec.bit_subcommand if unit == "bit" else wire_spec.word_subcommand
    cmd = 0x1401 if write else 0x0401
    cap = prof.batch_max[wire, unit]
    err_code = EndCode.BIT_POINTS_OUT_OF_RANGE if unit == "bit" else EndCode.POINTS_OUT_OF_RANGE

    if not write:
        if unit == "word":
            server.memory.write_words("D", 0, [0x1234] * cap)
        else:
            server.memory.write_bits("M", 0, [1] * cap)

    with socket.create_connection(server.address, timeout=2) as conn:
        # 0 points -> rejected with C051 (word) / C052 (bit)
        conn.sendall(packet(frame, wire, cmd, sub, raw_batch_payload(profile, wire, unit, 0, write=write)))
        status, _ = receive(conn, frame, wire)
        assert status == err_code

        # 1 point -> accepted (0x0000)
        conn.sendall(packet(frame, wire, cmd, sub, raw_batch_payload(profile, wire, unit, 1, write=write, value=1)))
        status, data = receive(conn, frame, wire)
        assert status == EndCode.OK
        if not write:
            assert len(data) == ((4 if wire == "ascii" else 2) if unit == "word" else 1)

        # cap points -> accepted (0x0000)
        conn.sendall(packet(frame, wire, cmd, sub, raw_batch_payload(profile, wire, unit, cap, write=write, value=1)))
        status, data = receive(conn, frame, wire)
        assert status == EndCode.OK
        if not write:
            expected_len = (cap * (4 if wire == "ascii" else 2)) if unit == "word" else (cap if wire == "ascii" else (cap + 1) // 2)
            assert len(data) == expected_len

        # cap + 1 points -> rejected with C051 (word) / C052 (bit) before mutation
        if write:
            if unit == "word":
                server.memory.write_words("D", 0, [0x7777])
            else:
                server.memory.write_bits("M", 0, [0])
        conn.sendall(packet(frame, wire, cmd, sub, raw_batch_payload(profile, wire, unit, cap + 1, write=write, value=1)))
        status, _ = receive(conn, frame, wire)
        assert status == err_code
        if write:
            if unit == "word":
                assert server.memory.read_words("D", 0, 1) == [0x7777]
            else:
                assert server.memory.read_bits("M", 0, 1) == [0]


@pytest.mark.parametrize("profile", ["Q", "QnA", "iQ-R"])
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_real_client_batch_boundaries_where_fits_recv(batch_servers, profile, frame, wire):
    """Real client tests for 1, cap, and cap+1 (where response fits in client recv(4096))."""
    server = batch_servers(profile)
    prof = server.memory.profile
    w_cap = prof.batch_max[wire, "word"]
    b_cap = prof.batch_max[wire, "bit"]

    with connected_profile(server, frame, wire) as client:
        # Word write at cap and cap+1 works on all transports
        client.batchwrite_wordunits("D0", [123] * w_cap)
        assert server.memory.read_words("D", 0, w_cap) == [123] * w_cap
        with pytest.raises(MCProtocolError) as err:
            client.batchwrite_wordunits("D0", [1] * (w_cap + 1))
        assert err.value.errorcode == "0xC051"

        # Word read at cap fits client recv(4096) in binary (960*2=1920, 480*2=960) and QnA ascii (480*4=1920)
        if wire == "binary" or profile == "QnA":
            assert client.batchread_wordunits("D0", w_cap) == [123] * w_cap
        with pytest.raises(MCProtocolError) as err:
            client.batchread_wordunits("D0", w_cap + 1)
        assert err.value.errorcode == "0xC051"

        # Bit write at cap and cap+1 works on all transports
        bits = [i % 2 for i in range(b_cap)]
        client.batchwrite_bitunits("M0", bits)
        assert server.memory.read_bits("M", 0, b_cap) == bits
        with pytest.raises(MCProtocolError) as err:
            client.batchwrite_bitunits("M0", [1] * (b_cap + 1))
        assert err.value.errorcode == "0xC052"

        # Bit read at cap fits client recv(4096) in binary (7168/2=3584, 3584/2=1792) and ascii (3584, 1792)
        assert client.batchread_bitunits("M0", b_cap) == bits
        with pytest.raises(MCProtocolError) as err:
            client.batchread_bitunits("M0", b_cap + 1)
        assert err.value.errorcode == "0xC052"


@pytest.mark.parametrize("profile", ["Q", "QnA", "iQ-R"])
@pytest.mark.parametrize("wire", ["binary", "ascii"])
@pytest.mark.parametrize("unit", ["word", "bit"])
def test_explicit_max_points_effective_limit_is_min(batch_servers, profile, wire, unit):
    # Explicit max_points smaller than manual cap lowers the effective limit
    small_server = batch_servers(profile, max_points=10)
    sub = small_server.memory.profile.wire.bit_subcommand if unit == "bit" else small_server.memory.profile.wire.word_subcommand
    err_code = EndCode.BIT_POINTS_OUT_OF_RANGE if unit == "bit" else EndCode.POINTS_OUT_OF_RANGE
    with socket.create_connection(small_server.address, timeout=1) as conn:
        conn.sendall(packet("3E", wire, 0x0401, sub, raw_batch_payload(profile, wire, unit, 10)))
        assert receive(conn, "3E", wire)[0] == EndCode.OK
        conn.sendall(packet("3E", wire, 0x0401, sub, raw_batch_payload(profile, wire, unit, 11)))
        assert receive(conn, "3E", wire)[0] == err_code

    # Explicit max_points larger than manual cap cannot exceed the manual cap
    large_server = batch_servers(profile, max_points=10000)
    cap = large_server.memory.profile.batch_max[wire, unit]
    with socket.create_connection(large_server.address, timeout=1) as conn:
        conn.sendall(packet("3E", wire, 0x0401, sub, raw_batch_payload(profile, wire, unit, cap)))
        assert receive(conn, "3E", wire)[0] == EndCode.OK
        conn.sendall(packet("3E", wire, 0x0401, sub, raw_batch_payload(profile, wire, unit, cap + 1)))
        assert receive(conn, "3E", wire)[0] == err_code
