"""P1/P2 review closure: 1E C060/C05B emission and X,Y HEX ASCII numbering."""

import pytest

from virtual_plc import Server
from virtual_plc.memory import Memory
from virtual_plc.one_e import dispatch_1e


def _name_binary(name):
    return name.ljust(2).encode()[::-1]


def _name_ascii(name):
    return name.ljust(2).encode().hex().upper().encode()


def _batch(wire, command, name, head, count, data):
    if wire == "binary":
        return (bytes((command, 0xFF, 0, 0)) + head.to_bytes(4, "little") + _name_binary(name)
                + bytes((count, 0)) + data)
    return (f"{command:02X}FF0000".encode() + _name_ascii(name) + f"{head:08X}{count:02X}00".encode()
            + data)


def _random(wire, command, records):
    width = 1 if command == 4 else 2
    if wire == "binary":
        body = b"".join(head.to_bytes(4, "little") + _name_binary(name) + value.to_bytes(width, "little")
                        for name, head, value in records)
        return bytes((command, 0xFF, 0, 0, len(records), 0)) + body
    body = b"".join(_name_ascii(name) + f"{head:08X}{value:0{2 * width}X}".encode()
                    for name, head, value in records)
    return f"{command:02X}FF0000{len(records):02X}00".encode() + body


def _error(wire, command, code):
    if wire == "binary":
        return bytes((command | 0x80, 0x5B)) + code.to_bytes(2, "little")
    return f"{command | 0x80:02X}5B{code:04X}".encode()


@pytest.mark.parametrize("wire, data", [
    ("binary", b"\x20"),   # first nibble is 2, not a bit value
    ("binary", b"\x12"),   # second nibble is 2
    ("ascii", b"20"),
    ("ascii", b"12"),
])
def test_1e_batch_bit_write_bad_value_is_c060(wire, data):
    memory = Memory("Q")
    assert dispatch_1e(_batch(wire, 2, "M", 0, 2, data), memory) == _error(wire, 2, 0xC060)
    assert memory.dump() == {}


@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_1e_random_bit_write_value_two_is_c060_and_atomic(wire):
    memory = Memory("Q")
    frame = _random(wire, 4, [("M", 0, 1), ("M", 1, 2)])
    assert dispatch_1e(frame, memory) == _error(wire, 4, 0xC060)
    assert memory.dump() == {}


@pytest.mark.parametrize("command, value", [(4, 1), (5, 7)])
@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_1e_random_write_unknown_device_is_c05b_and_atomic(wire, command, value):
    memory = Memory("Q")
    first = ("M", 0, 1) if command == 4 else ("D", 0, 7)
    frame = _random(wire, command, [first, ("ZZ", 0, value)])
    assert dispatch_1e(frame, memory) == _error(wire, command, 0xC05B)
    assert memory.dump() == {}


@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_1e_x_head_is_hexadecimal_on_both_wires(wire):
    memory = Memory("Q")
    memory.write_bits("X", 0x10, [1])  # X20 octal == X10 hex == point 16
    response = dispatch_1e(_batch(wire, 0, "X", 0x10, 1, b""), memory)
    assert response == (b"\x80\x00\x10" if wire == "binary" else b"80001")


def test_1e_rejects_fx5_octal_ascii_numbering():
    with pytest.raises(ValueError, match="X,Y HEX"):
        Server(slmp_1e=True, ascii_numbering="fx5-octal")
    Server(slmp_1e=True, ascii_numbering="compat")  # unaffected default
