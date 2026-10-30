"""T17 manual-derived vectors, independent of production, tables, and client.

Protocol claims remain unverified against an authoritative PLC manual.
"""

import pytest


pytestmark = pytest.mark.unverified

# Literal arithmetic: length 12 = timer 2 + command 2 + subcommand 2 + data 6.
READ_D100 = bytes.fromhex("50 00 00 ff ff 03 00 0c 00 04 00 01 04 00 00 64 00 00 a8 03 00")
WRITE_D100 = bytes.fromhex("50 00 00 ff ff 03 00 12 00 04 00 01 14 00 00 64 00 00 a8 03 00 95 19 02 12 30 11")
WRITE_M10 = bytes.fromhex("50 00 00 ff ff 03 00 0f 00 04 00 01 14 01 00 0a 00 00 90 05 00 10 10 10")


@pytest.mark.parametrize("frame, command, subcommand, data", [
    (READ_D100, 0x0401, 0, bytes.fromhex("64 00 00 a8 03 00")),
    (WRITE_D100, 0x1401, 0, bytes.fromhex("64 00 00 a8 03 00 95 19 02 12 30 11")),
    (WRITE_M10, 0x1401, 1, bytes.fromhex("0a 00 00 90 05 00 10 10 10")),
])
def test_decode_literal_requests(codec, frame, command, subcommand, data):
    request = codec.decode_request(frame)
    assert request.route == (0, 255, 0x03FF, 0)
    assert request.timer == 4
    assert (request.command, request.subcommand, request.data) == (command, subcommand, data)


@pytest.mark.parametrize("request_bytes, end_code, data, expected", [
    (READ_D100, 0, bytes.fromhex("95 19 02 12 30 11"),
     "d0 00 00 ff ff 03 00 08 00 00 00 95 19 02 12 30 11"),
    (WRITE_M10, 0, b"", "d0 00 00 ff ff 03 00 02 00 00 00"),
    (READ_D100, 0xC059, b"", "d0 00 00 ff ff 03 00 0b 00 59 c0 00 ff ff 03 00 01 04 00 00"),
    (bytes.fromhex("50 00 12 34 78 56 9a 06 00 04 00 01 01 00 00"),
     0, b"", "d0 00 12 34 78 56 9a 02 00 00 00"),
])
def test_encode_literal_responses(codec, request_bytes, end_code, data, expected):
    assert codec.encode_response(codec.decode_request(request_bytes), end_code, data) == bytes.fromhex(expected)


@pytest.mark.parametrize("values, encoded", [
    ([0, 65535, 0x1234, 0x8000], "00 00 ff ff 34 12 00 80"),
    ([0x1995, 0x1202, 0x1130], "95 19 02 12 30 11"),
])
def test_unsigned_word_codec(codec, values, encoded):
    assert codec.pack_words(values) == bytes.fromhex(encoded)
    assert codec.unpack_words(bytes.fromhex(encoded)) == values


@pytest.mark.parametrize("values, encoded", [([1], "10"), ([0, 1], "01"), ([1, 0, 1, 0, 1], "10 10 10")])
def test_bit_codec_high_nibble_first(codec, values, encoded):
    assert codec.pack_bits(values) == bytes.fromhex(encoded)
    assert codec.unpack_bits(bytes.fromhex(encoded), len(values)) == values


@pytest.mark.parametrize("bad", [b"", READ_D100[:8], READ_D100[:-1], READ_D100 + b"\x00",
    b"\x51" + READ_D100[1:], bytes.fromhex("50 00 00 ff ff 03 00 05 00 04 00 01 04 00")])
def test_bad_frame_rejected(codec, bad):
    with pytest.raises(ValueError):
        codec.decode_request(bad)


@pytest.mark.parametrize("method, args", [
    ("pack_words", ([-1],)), ("pack_words", ([65536],)),
    ("unpack_words", (b"\x00",)), ("pack_bits", ([2],)),
    ("unpack_bits", (b"\x20", 2)), ("unpack_bits", (b"\x1f", 2)),
    ("unpack_bits", (b"\x11", 1)), ("unpack_bits", (b"", 1)),
    ("unpack_bits", (b"\x10\x00", 1)),
])
def test_bad_payload_rejected(codec, method, args):
    with pytest.raises(ValueError):
        getattr(codec, method)(*args)
