"""No-behavior-change UDP transport/dispatch separation contract.

Pre-refactor tests intentionally fail on the absent internal dispatch seam.
Real transport regression remains in test_multi_listener_udp and 1E suites;
these tests isolate deterministic processing without opening any socket.
"""
import pytest

from test_m1_server_raw import device_data
from test_m3_m4_raw import packet
from test_slmp_1e import READ_D100, READ_D100_ASCII, RESP_D100, RESP_D100_ASCII
from test_slmp_1e_remote_control import RUN, DENIED_RUN
from virtual_plc import Server
from virtual_plc.codec import decode_request, encode_response
from virtual_plc.server import MAX_UDP_DATAGRAM


@pytest.mark.parametrize("frame,wire", [
    ("3E", "binary"), ("3E", "ascii"), ("4E", "binary"), ("4E", "ascii"),
])
def test_standard_udp_dispatch_reuses_same_memory_without_socket(frame, wire):
    seen = []
    server = Server(listeners=[("udp", 0)], response_hook=lambda data: (
        seen.append(data) or data
    ))
    original = packet(frame, wire)
    expected = encode_response(decode_request(original), data=b"\x00\x00")
    assert server._udp_response(original) == expected
    assert seen == [expected]


@pytest.mark.parametrize("frame,wire", [
    ("3E", "binary"), ("3E", "ascii"), ("4E", "binary"), ("4E", "ascii"),
])
def test_standard_udp_dispatch_write_commits_once(frame, wire):
    seen = []
    server = Server(listeners=[("udp", 0)], response_hook=lambda data: (
        seen.append(data) or data
    ))
    data = (b"D*00000000011234" if wire == "ascii"
            else device_data(payload=b"\x34\x12"))
    raw = packet(frame, wire, 0x1401, data=data)
    expected = encode_response(decode_request(raw))
    assert server._udp_response(raw) == expected
    assert seen == [expected]
    assert server.memory.read_words("D", 0, 1) == [0x1234]


@pytest.mark.parametrize("frame_bytes,expected", [
    (READ_D100, RESP_D100), (READ_D100_ASCII, RESP_D100_ASCII),
])
def test_1e_udp_dispatch_has_one_hook_and_raw_reply(frame_bytes, expected):
    seen = []
    server = Server(slmp_1e=True, listeners=[("udp", 0)],
                    response_hook=lambda data: (seen.append(data) or data))
    server.memory.write_words("D", 100, [0x1234, 5, 0x6789])
    assert server._udp_response(frame_bytes) == expected
    assert seen == [expected]


def test_1e_udp_control_identity_stays_unowned_and_cannot_run():
    server = Server(slmp_1e=True, listeners=[("udp", 0)])
    assert server._udp_response(RUN) == DENIED_RUN
    assert server.state == "RUN"
    assert server.get_1e_remote_control_status()["owned"] is False


@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_ethernet_data_code_mismatch_is_dropped_before_hook(wire):
    seen = []
    server = Server(ethernet_model="qj71e71", listeners=[("udp", 0)],
                    response_hook=lambda data: (seen.append(data) or data))
    raw = packet("3E", wire)
    response = server._udp_response(raw)
    if wire == "ascii":
        assert response is None
        assert seen == []
    else:
        expected = encode_response(decode_request(raw), data=b"\x00\x00")
        assert response == expected
        assert seen == [expected]


@pytest.mark.parametrize("slmp_1e,raw", [
    (False, packet("3E", "binary")[:-1]),
    (False, packet("3E", "binary") + packet("3E", "binary")),
    (True, READ_D100[:-1]),
    (True, READ_D100 + READ_D100),
    (False, b""),
    (True, b""),
])
def test_invalid_or_combined_datagram_produces_no_response_or_mutation(slmp_1e, raw):
    server = Server(slmp_1e=slmp_1e, listeners=[("udp", 0)])
    assert server._udp_response(raw) is None
    assert server.memory.read_words("D", 0, 1) == [0]


@pytest.mark.parametrize("slmp_1e,raw", [
    (False, b"this-is-not-MC"), (True, b"this-is-not-1E"),
])
def test_unknown_subheader_is_not_reinterpreted(slmp_1e, raw):
    server = Server(slmp_1e=slmp_1e, listeners=[("udp", 0)])
    with pytest.raises(ValueError):
        server._udp_response(raw)
    assert server.memory.read_words("D", 0, 1) == [0]


@pytest.mark.parametrize("slmp_1e,raw", [
    (False, packet("3E", "binary")), (True, READ_D100),
])
def test_oversized_response_hook_is_dropped_not_sent(slmp_1e, raw):
    server = Server(slmp_1e=slmp_1e, listeners=[("udp", 0)],
                    response_hook=lambda data: b"Z" * (MAX_UDP_DATAGRAM + 1))
    assert server._udp_response(raw) is None


def test_post_dispatch_hook_is_not_called_for_incomplete_frame():
    count = []
    server = Server(listeners=[("udp", 0)], response_hook=lambda data: count.append(data))
    assert server._udp_response(b"\x50") is None
    assert count == []
