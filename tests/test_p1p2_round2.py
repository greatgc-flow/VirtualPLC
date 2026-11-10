"""P1/P2 review round 2: 1E device-code exact match and ASCII non-hex field policy."""

import pytest

from virtual_plc.memory import Memory
from virtual_plc.one_e import dispatch_1e


def _error(wire, command, code):
    if wire == "binary":
        return bytes((command | 0x80, 0x5B)) + code.to_bytes(2, "little")
    return f"{command | 0x80:02X}5B{code:04X}".encode()


def _batch(wire, command, code, head=0, count=1, data=b""):
    """code = raw logical 2-byte device code (binary wire sends it reversed)."""
    if wire == "binary":
        return (bytes((command, 0xFF, 0, 0)) + head.to_bytes(4, "little") + code[::-1]
                + bytes((count, 0)) + data)
    return (f"{command:02X}FF0000".encode() + code.hex().upper().encode()
            + f"{head:08X}{count:02X}00".encode() + data)


def _random(wire, command, code):
    width = 1 if command == 4 else 2
    if wire == "binary":
        return (bytes((command, 0xFF, 0, 0, 1, 0)) + (0).to_bytes(4, "little") + code[::-1]
                + bytes(width))
    return (f"{command:02X}FF00000100".encode() + code.hex().upper().encode()
            + b"00000000" + b"0" * (2 * width))


_DATA = {("binary", 2): b"\x10", ("binary", 3): b"\x01\x00",
         ("ascii", 2): b"1", ("ascii", 3): b"0001"}


# F2: manual device code 4D20H (M + trailing space) must match exactly; the
# byte-swapped / leading-space forms (binary wire 4D 20, ASCII "204D") are C05B.
@pytest.mark.parametrize("code", [b" M", b" D", b"  "])
@pytest.mark.parametrize("command", [0, 1, 2, 3, 4, 5])
@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_1e_leading_space_device_code_is_refused_with_c05b(wire, command, code):
    memory = Memory("Q")
    if command in (4, 5):
        frame = _random(wire, command, code)
    else:
        frame = _batch(wire, command, code, data=_DATA.get((wire, command), b""))
    assert dispatch_1e(frame, memory) == _error(wire, command, 0xC05B)
    assert memory.read_bits("M", 0, 16) == [0] * 16
    assert memory.read_words("D", 0, 1) == [0]


@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_1e_trailing_space_device_code_still_reads_m(wire):
    memory = Memory("Q")
    memory.write_bits("M", 0, [1])
    expected = b"80001" if wire == "ascii" else b"\x80\x00\x10"
    assert dispatch_1e(_batch(wire, 0, b"M "), memory) == expected


# F3: once the frame size is valid, any non-hex numeric ASCII field (device
# code, head, word data, random value) returns the 1E error reply C05C and
# nothing is written.
NONHEX_ASCII = [
    (0, b"00FF00004D2000000G000100"),                     # 00H head
    (0, b"00FF00004G20000000000100"),                     # 00H device code
    (0, b"00FF0000 4D 000000000100"),                     # 00H whitespace in device code
    (1, b"01FF00004420000000G00100"),                     # 01H head
    (2, b"02FF00004D20000000G001001"),                    # 02H head
    (3, b"03FF00004420000000000200" + b"0001000G"),       # 03H word data (2nd word)
    (3, b"03FF0000442000000000010000G1"),                 # 03H word data
    (3, b"03FF000044200000000G01000001"),                 # 03H head
    (4, b"04FF00000200" + b"4D20000000000" + b"1" + b"4D2000000001" + b"0G"),  # 04H value
    (4, b"04FF00000100" + b"4D200000000G" + b"01"),       # 04H head
    (5, b"05FF00000100" + b"442000000000" + b"0G01"),     # 05H value
    (5, b"05FF000002004420000000000001" + b"44G0000000010002"),  # 05H device code
    (5, b"05FF000001004420+0000000" + b"0001"),           # 05H head sign
]


@pytest.mark.parametrize("command, frame", NONHEX_ASCII)
def test_1e_ascii_nonhex_numeric_field_returns_c05c_without_write(command, frame):
    memory = Memory("Q")
    assert dispatch_1e(frame, memory) == _error("ascii", command, 0xC05C)
    assert memory.read_bits("M", 0, 16) == [0] * 16
    assert memory.read_words("D", 0, 2) == [0, 0]


@pytest.mark.parametrize("frame", [
    b"00FF000G4D20000000000100",  # monitoring timer (header field)
    b"00FG00004D20000000000100",  # PC number (header field)
    b"00FF00004D200000000001G0",  # fixed byte
    b"00FF00004D20000000000G00",  # count: sizes the frame
    b"04FF00000G00",              # random count: sizes the frame
])
def test_1e_ascii_nonhex_header_and_framing_fields_still_close(frame):
    with pytest.raises(ValueError):
        dispatch_1e(frame, Memory("Q"))
