"""Manual-derived header vectors; independent of production and test tables."""

import pytest
import pymcprotocol


pytestmark = pytest.mark.unverified

# Request body length 0018 is 24 ASCII characters (timer+cmd+sub+descriptor+count).
ASCII_3E = b"5000" b"00FF03FF00" b"0018" b"0004" b"04010000" b"D*0001000003"
ASCII_4E = b"5400" b"BEEF0000" b"00FF03FF00" b"0018" b"0004" b"04010000" b"D*0001000003"
BINARY_4E = bytes.fromhex("54 00 ef be 00 00 00 ff ff 03 00 0c 00 04 00 01 04 00 00 64 00 00 a8 03 00")
VECTORS = [
    ("3E", "ascii", ASCII_3E, b"D000" b"00FF03FF00" b"0010" b"0000" b"199512021130"),
    ("4E", "ascii", ASCII_4E, b"D400" b"BEEF0000" b"00FF03FF00" b"0010" b"0000" b"199512021130"),
    ("4E", "binary", BINARY_4E, bytes.fromhex("d4 00 ef be 00 00 00 ff ff 03 00 08 00 00 00 95 19 02 12 30 11")),
]


@pytest.mark.parametrize("frame,wire,packet,expected", VECTORS)
def test_decode_and_encode_header_vectors(codec, frame, wire, packet, expected):
    parsed = codec.decode_request(packet)
    assert (parsed.frame, parsed.wire) == (frame, wire)
    assert parsed.serial == (0xBEEF if frame == "4E" else 0)
    assert parsed.route == (0, 255, 0x03FF, 0)
    assert (parsed.timer, parsed.command, parsed.subcommand) == (4, 0x0401, 0)
    assert codec.encode_response(parsed, 0, bytes.fromhex("95 19 02 12 30 11")) == expected


@pytest.mark.parametrize("frame,wire,packet,expected", VECTORS)
def test_real_client_encoder_matches_literal_headers(monkeypatch, frame, wire, packet, expected):
    client = (pymcprotocol.Type4E if frame == "4E" else pymcprotocol.Type3E)()
    client.setaccessopt(commtype=wire)
    if frame == "4E":
        client.set_subheaderserial(0xBEEF)
    sent = []
    monkeypatch.setattr(client, "_send", sent.append)
    monkeypatch.setattr(client, "_recv", lambda: expected)
    assert client.batchread_wordunits("D100", 3) == [0x1995, 0x1202, 0x1130]
    assert sent == [packet]


@pytest.mark.parametrize("packet", [ASCII_3E, ASCII_4E, BINARY_4E])
def test_frame_size_waits_for_complete_header(codec, packet):
    header_size = 13 if packet == BINARY_4E else (26 if packet == ASCII_4E else 18)
    for size in range(header_size):
        assert codec.frame_size(packet[:size]) is None
    assert codec.frame_size(packet[:header_size]) == len(packet)


@pytest.mark.parametrize("packet", [ASCII_3E[:-1], ASCII_3E + b"0", ASCII_3E.replace(b"0018", b"00G8"),
    ASCII_4E.replace(b"BEEF0000", b"BEEF0001"), BINARY_4E[:4] + b"\x01\x00" + BINARY_4E[6:]])
def test_malformed_frame_or_reserved_fields_rejected(codec, packet):
    with pytest.raises(ValueError):
        codec.decode_request(packet)
