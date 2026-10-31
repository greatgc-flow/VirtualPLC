"""FX5 3E ASCII X/Y octal numbering prerequisite (manual JY997D56001 p.67).

This is a wire address option, NOT a claim that FX5 CPU/ENET is a runnable
hardware model. Default Q/L/R client behavior must remain unchanged.
"""

import socket

import pytest

from test_m3_m4_raw import packet, receive
from virtual_plc.__main__ import build_parser
from virtual_plc.commands import EndCode
from virtual_plc.memory import Memory
from virtual_plc.server import Server


def test_fx5_octal_policy_explicit_and_default_unchanged():
    assert Server().ascii_numbering == "compat"
    assert Server(ascii_numbering="fx5-octal").ascii_numbering == "fx5-octal"
    assert "fx5-octal" in build_parser()._option_string_actions["--ascii-numbering"].choices


@pytest.mark.parametrize("frame", ["3E", "4E"])
def test_fx5_ascii_x_y_octal_address_numbering(frame):
    memory = Memory("Q")
    # 000010(oct)=8(dec), 000017(oct)=15(dec), 000077(oct)=63(dec).
    memory.write_bits("X", 8, [1])
    memory.write_bits("X", 10, [0])
    memory.write_bits("X", 15, [1])
    memory.write_bits("Y", 63, [1])
    with Server(memory=memory, ascii_numbering="fx5-octal") as plc:
        with socket.create_connection(plc.address, timeout=2) as conn:
            conn.settimeout(2)
            for desc in (b"X*0000100001", b"X*0000170001", b"Y*0000770001"):
                conn.sendall(packet(frame, "ascii", 0x0401, 1, desc))
                code, data = receive(conn, frame, "ascii")
                assert (code, data) == (EndCode.OK, b"1")


@pytest.mark.parametrize("address", [b"000008", b"000009", b"000018", b"00001A"])
def test_fx5_octal_rejects_non_octal_x_y_digits(address):
    with Server(ascii_numbering="fx5-octal") as plc:
        with socket.create_connection(plc.address, timeout=2) as conn:
            conn.settimeout(2)
            conn.sendall(packet("3E", "ascii", 0x0401, 1, b"X*" + address + b"0001"))
            assert receive(conn, "3E", "ascii")[0] == EndCode.REQUEST_DATA_ERROR


def test_fx5_octal_keeps_w_hex_and_d_decimal():
    memory = Memory("Q")
    memory.write_words("W", 266, [0xBEEF])
    memory.write_words("D", 10, [0x1234])
    with Server(memory=memory, ascii_numbering="fx5-octal") as plc:
        with socket.create_connection(plc.address, timeout=2) as conn:
            conn.settimeout(2)
            conn.sendall(packet("3E", "ascii", 0x0401, 0, b"W*00010A0001"))
            assert receive(conn, "3E", "ascii") == (EndCode.OK, b"BEEF")
            conn.sendall(packet("3E", "ascii", 0x0401, 0, b"D*0000100001"))
            assert receive(conn, "3E", "ascii") == (EndCode.OK, b"1234")


def test_fx5_octal_binary_wire_is_not_changed():
    memory = Memory("Q")
    memory.write_bits("X", 8, [1])
    with Server(memory=memory, ascii_numbering="fx5-octal") as plc:
        with socket.create_connection(plc.address, timeout=2) as conn:
            conn.settimeout(2)
            conn.sendall(packet("3E", "binary", 0x0401, 1,
                                b"\x08\x00\x00\x9c\x01\x00"))
            assert receive(conn, "3E", "binary") == (EndCode.OK, b"\x10")


def test_fx5_octal_udp_frame_uses_same_policy():
    memory = Memory("Q")
    memory.write_bits("X", 8, [1])
    with Server(memory=memory, ascii_numbering="fx5-octal",
                listeners=[("udp", 0)]) as plc:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(1)
            udp.sendto(packet("3E", "ascii", 0x0401, 1, b"X*0000100001"), plc.address)
            result, _ = udp.recvfrom(8192)
            assert result.startswith(b"D000")
            assert result.endswith(b"1")


def test_fx5_octal_is_not_a_hardware_compatibility_claim():
    from virtual_plc.ethernet import reference_catalog, model_catalog
    assert "fx5_enet" not in model_catalog()
    assert reference_catalog()["fx5_enet"]["implementation"] == "research_only"
