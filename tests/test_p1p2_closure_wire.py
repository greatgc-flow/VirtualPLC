"""P1/P2 review closure: 3E/4E wire end codes (echo length, LCN two-word writes, provenance)."""

import pytest

from virtual_plc.codec import Request
from virtual_plc.commands import ERROR_CODES, dispatch
from virtual_plc.memory import Memory

ROUTE = (0, 0xFF, 0x03FF, 0)


def _request(command, subcommand, data, wire, frame="3E"):
    return Request(ROUTE, 0, command, subcommand, data, frame, wire)


# F1: malformed echo payloads are length errors (C057) on both wires.
@pytest.mark.parametrize("frame", ["3E", "4E"])
@pytest.mark.parametrize("binary, ascii", [
    (b"\x05\x00ABC", b"0005ABC"),        # declared length longer than text
    (b"\x03\x00ABCDE", b"0003ABCDE"),    # trailing text after declared length
    (b"\x05", b"0"),                     # truncated length field
])
@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_malformed_echo_length_is_c057_on_both_wires(frame, binary, ascii, wire):
    data = binary if wire == "binary" else ascii
    code, payload = dispatch(_request(0x0619, 0, data, wire, frame), Memory("Q"), None)
    assert (code, payload) == (0xC057, b"")


@pytest.mark.parametrize("wire, data", [("binary", b"\x03\x00ABC"), ("ascii", b"0003ABC")])
def test_wellformed_echo_still_succeeds(wire, data):
    code, payload = dispatch(_request(0x0619, 0, data, wire), Memory("Q"), None)
    assert code == 0 and payload == b"\x03\x00ABC"


# F3: SH-081257 3.5 (p.453) C051H: long-counter write points not in two-word units.
def _lcn_write(wire, points, head=0):
    if wire == "binary":
        descriptor = head.to_bytes(4, "little") + (0x56).to_bytes(2, "little")
        return descriptor + points.to_bytes(2, "little") + b"".join(
            (0x1111 * (i + 1)).to_bytes(2, "little") for i in range(points))
    return (b"LCN*" + f"{head:08d}".encode() + f"{points:04X}".encode()
            + b"".join(f"{0x1111 * (i + 1):04X}".encode() for i in range(points)))


@pytest.mark.parametrize("frame", ["3E", "4E"])
@pytest.mark.parametrize("wire", ["binary", "ascii"])
@pytest.mark.parametrize("points", [1, 3, 5])
def test_odd_lcn_batch_word_write_is_c051_and_mutates_nothing(frame, wire, points):
    memory = Memory("iQ-R")
    memory.write_words("LCN", 0, [0xAAAA, 0xBBBB, 0xCCCC, 0xDDDD, 0xEEEE, 0xFFFF])
    before = memory.dump()
    code, _ = dispatch(_request(0x1401, 2, _lcn_write(wire, points), wire, frame), memory, None)
    assert code == 0xC051
    assert memory.dump() == before


@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_even_lcn_batch_word_write_still_accepted(wire):
    memory = Memory("iQ-R")
    code, _ = dispatch(_request(0x1401, 2, _lcn_write(wire, 2), wire), memory, None)
    assert code == 0
    assert memory.read_words("LCN", 0, 2) == [0x1111, 0x2222]


@pytest.mark.parametrize("device, code", [("LTN", 0x52), ("LSTN", 0x5A), ("LZ", 0x62)])
def test_odd_word_write_to_other_native_dwords_keeps_half_word_policy(device, code):
    memory = Memory("iQ-R")
    memory.write_words(device, 0, [0x1234, 0x5678])
    data = (0).to_bytes(4, "little") + code.to_bytes(2, "little") + b"\x01\x00\x09\x00"
    assert dispatch(_request(0x1401, 2, data, "binary"), memory, None)[0] == 0
    assert memory.read_words(device, 0, 2) == [9, 0x5678]


# F7: C056/C057/C059/C05C are listed in SH-081257 3.5 (p.453); 0055 comes from
# the QJ71E71/iQ-R SLMP/MC error lists (ETHERNET_MODEL_SETTINGS.md).
@pytest.mark.parametrize("code, name", [
    (0x0055, "RUN_WRITE_DISABLED"), (0xC056, "ADDRESS_OUT_OF_RANGE"), (0xC057, "DATA_LENGTH_MISMATCH"),
    (0xC059, "UNSUPPORTED_COMMAND"), (0xC05C, "REQUEST_DATA_ERROR"),
])
def test_manual_listed_end_codes_have_manual_source(code, name):
    assert ERROR_CODES[code] == {"name": name, "source": "manual", "status": "unverified"}
