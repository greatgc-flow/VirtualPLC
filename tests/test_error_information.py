"""Tests for abnormal response error information per SH-080008 5.2/5.3 and bad_end_code fault."""

from itertools import product
import socket
import struct

from pymcprotocol import Type3E, Type4E
from pymcprotocol.mcprotocolerror import MCProtocolError
import pytest

from test_m1_server_raw import receive_exact
from virtual_plc.faults import FaultPlan
from virtual_plc.memory import Memory
from virtual_plc.server import Server

pytestmark = pytest.mark.unverified

PROFILES = ("Q", "iQ-R")
FRAMES = ("3E", "4E")
WIRES = ("binary", "ascii")
MATRIX = list(product(FRAMES, WIRES, PROFILES))


def build_raw_unsupported(frame, wire, serial=0xBEEF):
    route_bin = b"\x00\xff\xff\x03\x00"
    route_asc = b"00FF03FF00"
    if wire == "ascii":
        body = b"000499990000"
        prefix = b"5400" + f"{serial:04X}0000".encode() if frame == "4E" else b"5000"
        req = prefix + route_asc + f"{len(body):04X}".encode() + body
        resp_prefix = b"D400" + f"{serial:04X}0000".encode() if frame == "4E" else b"D000"
        expected = resp_prefix + route_asc + b"0016C059" + route_asc + b"99990000"
    else:
        body = struct.pack("<HHH", 4, 0x9999, 0)
        prefix = b"\x54\x00" + struct.pack("<HH", serial, 0) if frame == "4E" else b"\x50\x00"
        req = prefix + route_bin + struct.pack("<H", len(body)) + body
        resp_prefix = b"\xd4\x00" + struct.pack("<HH", serial, 0) if frame == "4E" else b"\xd0\x00"
        expected = resp_prefix + route_bin + struct.pack("<H", 11) + struct.pack("<H", 0xC059) + route_bin + struct.pack("<HH", 0x9999, 0)
    return req, expected


@pytest.mark.parametrize("frame,wire,profile", MATRIX)
def test_unsupported_command_error_response_exact_bytes(frame, wire, profile):
    req, expected = build_raw_unsupported(frame, wire)
    with Server(profile=profile, port=0) as server:
        with socket.create_connection(server.address, timeout=1) as conn:
            conn.sendall(req)
            reply = receive_exact(conn, len(expected))
            assert reply == expected


def build_read_request(frame, wire, profile, serial=0xBEEF):
    route_bin = b"\x00\xff\xff\x03\x00"
    route_asc = b"00FF03FF00"
    is_iqr = profile == "iQ-R"
    subcommand = 2 if is_iqr else 0
    if wire == "ascii":
        dev = b"D***000000000001" if is_iqr else b"D*0000000001"
        body = f"00040401{subcommand:04X}".encode() + dev
        prefix = b"5400" + f"{serial:04X}0000".encode() if frame == "4E" else b"5000"
        req = prefix + route_asc + f"{len(body):04X}".encode() + body
        resp_prefix = b"D400" + f"{serial:04X}0000".encode() if frame == "4E" else b"D000"
        expected = resp_prefix + route_asc + b"0016C056" + route_asc + f"0401{subcommand:04X}".encode()
    else:
        dev = b"\x00\x00\x00\x00\xa8\x00\x01\x00" if is_iqr else b"\x00\x00\x00\xa8\x01\x00"
        body = struct.pack("<HHH", 4, 0x0401, subcommand) + dev
        prefix = b"\x54\x00" + struct.pack("<HH", serial, 0) if frame == "4E" else b"\x50\x00"
        req = prefix + route_bin + struct.pack("<H", len(body)) + body
        resp_prefix = b"\xd4\x00" + struct.pack("<HH", serial, 0) if frame == "4E" else b"\xd0\x00"
        expected = resp_prefix + route_bin + struct.pack("<H", 11) + struct.pack("<H", 0xC056) + route_bin + struct.pack("<HH", 0x0401, subcommand)
    return req, expected


@pytest.mark.parametrize("frame,wire,profile", MATRIX)
def test_bad_end_code_drops_read_data_and_carries_error_info(frame, wire, profile):
    memory = Memory(profile)
    memory.write_words("D", 0, [0x1234])
    plan = FaultPlan([{"match": {"command": 0x0401}, "action": {"type": "bad_end_code", "code": 0xC056}}])

    req, expected = build_read_request(frame, wire, profile)
    with Server(memory=memory, fault_plan=plan, profile=profile, port=0) as server:
        with socket.create_connection(server.address, timeout=1) as conn:
            conn.sendall(req)
            reply = receive_exact(conn, len(expected))
            assert reply == expected
            # Ensure the seeded data is NOT leaked into the error response
            assert b"1234" not in reply
            assert b"\x34\x12" not in reply


@pytest.mark.parametrize("frame,wire", list(product(FRAMES, WIRES)))
def test_pymcprotocol_client_raises_mcprotocol_error_with_right_code(frame, wire):
    plan = FaultPlan([{"match": {"command": 0x0401}, "action": {"type": "bad_end_code", "code": 0xC056}}])
    with Server(fault_plan=plan, port=0) as server:
        client = (Type4E if frame == "4E" else Type3E)(plctype="Q")
        client.setaccessopt(commtype=wire)
        if frame == "4E":
            client.set_subheaderserial(0xBEEF)
        client.connect(*server.address)
        try:
            with pytest.raises(MCProtocolError) as exc_info:
                client.batchread_wordunits("D0", 1)
            assert exc_info.value.errorcode == "0xC056"
        finally:
            client.close()


def test_bad_end_code_zero_keeps_normal_response():
    memory = Memory("Q")
    memory.write_words("D", 0, [0x1234])
    plan = FaultPlan([{"match": {"command": 0x0401}, "action": {"type": "bad_end_code", "code": 0}}])
    with Server(memory=memory, fault_plan=plan, port=0) as server:
        client = Type3E(plctype="Q")
        client.connect(*server.address)
        try:
            assert client.batchread_wordunits("D0", 1) == [0x1234]
        finally:
            client.close()
