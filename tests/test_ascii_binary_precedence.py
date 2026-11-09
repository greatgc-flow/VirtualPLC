"""Paired 3E validation order; simulator policy, not physical PLC evidence."""

import pytest

from test_m3_m4_raw import packet
from virtual_plc.codec import decode_request
from virtual_plc.commands import dispatch
from virtual_plc.memory import Memory
from virtual_plc.profiles import PROFILES


OPERATIONS = [pytest.param(command, bit, id=f"{command:04X}-{'bit' if bit else 'word'}")
              for command, bit in [(0x0401, False), (0x0401, True), (0x1401, False),
                                   (0x1401, True), (0x0403, False), (0x1402, False), (0x1402, True)]]
CASES = ["zero", "zero-extra", "zero-bad-device", "over-short", "over-extra",
         "over-bad-device", "short", "extra", "bad-device", "bad-device-short",
         "bad-device-extra"]


def payload(profile, wire, command, bit, case, group="words"):
    spec = PROFILES[profile].wire
    batch = command in (0x0401, 0x1401)
    write = command in (0x1401, 0x1402)
    cap = (PROFILES[profile].batch_max[wire, "bit" if bit else "word"] if batch else
           spec.random_bit_max if bit else
           spec.random_read_max // (2 if group == "mixed" else 1) if not write else
           spec.random_write_weight_max // {"words": 12, "dwords": 14, "mixed": 26}[group])
    count = 0 if case.startswith("zero") else cap + 1 if case.startswith("over") else 1
    counts_by_group = (count, 0) if group == "words" else (0, count) if group == "dwords" else (count, count)
    bad = "bad-device" in case
    if wire == "ascii":
        code = "?" * spec.ascii_code_size if bad else ("M" if bit else "D").ljust(spec.ascii_code_size, "*")
        descriptor = (code + "0" * spec.ascii_address_size).encode()
        counts = (f"{count:04X}".encode() if batch else f"{count:02X}".encode() if bit else
                  f"{counts_by_group[0]:02X}{counts_by_group[1]:02X}".encode())
        value = b"1" if batch and bit else b"0" * (spec.bit_value_size * 2 if bit else 4)
    else:
        descriptor = bytes(spec.address_size) + ((1 << (8 * spec.code_size)) - 1 if bad else 0x90 if bit else 0xA8).to_bytes(spec.code_size, "little")
        counts = count.to_bytes(2, "little") if batch else bytes([count]) if bit else bytes(counts_by_group)
        value = b"\x10" if batch and bit else bytes(spec.bit_value_size if bit else 2)
    if batch:
        data = descriptor + counts
        if write:
            data += (value * count if not bit or wire == "ascii" else bytes((count + 1) // 2))
    else:
        if bit:
            data = counts + (descriptor + value) * count
        else:
            parts = [counts]
            for size, width in zip(counts_by_group, (2, 4)):
                value = bytes(width) if wire == "binary" else b"0" * (width * 2)
                parts.append((descriptor + (value if write else b"")) * size)
            data = b"".join(parts)
        if case == "zero-bad-device":
            data += descriptor
    if case.endswith("short"):
        data = data[:len(descriptor) + len(counts)] if batch else counts
        # Read requests have no values to truncate: remove part of the count.
        if batch and not write and not case.startswith("over"):
            data = data[:-1]
    if case.endswith("extra"):
        data += b"0"
    return data


@pytest.mark.parametrize("profile", ["Q", "iQ-R"])
@pytest.mark.parametrize("wire", ["binary", "ascii"])
@pytest.mark.parametrize("command,bit", OPERATIONS)
@pytest.mark.parametrize("case", CASES)
def test_paired_precedence_table(profile, wire, command, bit, case):
    spec = PROFILES[profile].wire
    data = payload(profile, wire, command, bit, case)
    request = decode_request(packet("3E", wire, command, spec.bit_subcommand if bit else spec.word_subcommand, data))
    if case in ("zero-extra", "zero-bad-device") and command not in (0x0401, 0x1401):
        # Established binary contract (test_m2_raw): a zero random count with
        # trailing data is a length error; ASCII now matches it.
        expected = 0xC057
    elif case.startswith(("zero", "over")):
        expected = (0xC052 if bit else 0xC051) if command in (0x0401, 0x1401) else (0xC053 if bit else 0xC054)
    elif case == "bad-device":
        expected = 0xC05C
    else:
        # Incomplete fixed batch headers retain C05C; no complete count exists.
        expected = 0xC05C if command == 0x0401 and case.endswith("short") else 0xC057
    assert dispatch(request, Memory(profile=profile), None)[0] == expected


@pytest.mark.parametrize("profile", ["Q", "iQ-R"])
@pytest.mark.parametrize("wire", ["binary", "ascii"])
@pytest.mark.parametrize("command", [0x0403, 0x1402])
@pytest.mark.parametrize("group", ["dwords", "mixed"])
@pytest.mark.parametrize("case", CASES)
def test_random_dword_and_mixed_precedence(profile, wire, command, group, case):
    spec = PROFILES[profile].wire
    data = payload(profile, wire, command, False, case, group)
    request = decode_request(packet("3E", wire, command, spec.word_subcommand, data))
    if case in ("zero-extra", "zero-bad-device"):
        expected = 0xC057  # zero random count with trailing data (established binary rule)
    else:
        expected = 0xC054 if case.startswith(("zero", "over")) else 0xC05C if case == "bad-device" else 0xC057
    assert dispatch(request, Memory(profile=profile), None)[0] == expected


@pytest.mark.parametrize("profile", ["Q", "iQ-R"])
@pytest.mark.parametrize("command,bit", [(0x1401, False), (0x1401, True), (0x1402, False), (0x1402, True)])
def test_nonhex_ascii_value_keeps_request_data_error(profile, command, bit):
    spec = PROFILES[profile].wire
    data = payload(profile, "ascii", command, bit, "valid")
    request = decode_request(packet("3E", "ascii", command, spec.bit_subcommand if bit else spec.word_subcommand, data[:-1] + b"G"))
    assert dispatch(request, Memory(profile=profile), None)[0] == 0xC05C


@pytest.mark.parametrize("wire", ["binary", "ascii"])
@pytest.mark.parametrize("command,bit", OPERATIONS)
def test_incomplete_count_header(wire, command, bit):
    request = decode_request(packet("3E", wire, command, int(bit), b""))
    assert dispatch(request, Memory(), None)[0] == (0xC05C if command in (0x0401, 0x1401) else 0xC057)
