"""Pinned unverified simulator policy, see issue #2.

Pins current simulator policies that await physical PLC verification:
- echo (0x0619) accepts 0-9, A-F, a-f only; rejects non-hex with REQUEST_DATA_ERROR (unverified (case))
- Remote STOP (0x1002) rejects mode 0 and accepts mode 1
"""

import struct

import pytest

from test_m1_server_raw import exchange, request
from virtual_plc.commands import EndCode

pytestmark = pytest.mark.unverified


def test_echo_rejects_non_hex_and_accepts_hex(raw_socket):
    """Echo (0x0619) rejects non-hex payload with REQUEST_DATA_ERROR and accepts 0-9, A-F, a-f.

    unverified simulator policy, see issue #2; unverified (case)
    """
    # Hex payloads (0-9, A-F, a-f) are accepted with OK (0x0000)
    for text in [b"0Aa9", b"ABCDEF", b"0123456789", b"abcdef"]:
        data = struct.pack("<H", len(text)) + text
        status, body = exchange(raw_socket, request(command=0x0619, data=data))
        assert status == EndCode.OK
        assert body == data

    # Non-hex payloads are rejected with REQUEST_DATA_ERROR (0xC05C)
    for text in [b"xyz", b"OK", b"a b", b"foo!", b"test@123", b"line\nbreak", b"\x00\x01"]:
        data = struct.pack("<H", len(text)) + text
        status, _ = exchange(raw_socket, request(command=0x0619, data=data))
        assert status == EndCode.REQUEST_DATA_ERROR


def test_remote_stop_rejects_mode_0_and_accepts_mode_1(raw_socket, server):
    """Remote STOP (0x1002) rejects mode 0 and accepts mode 1.

    unverified simulator policy, see issue #2
    """
    server.set_state("RUN")
    assert server.state == "RUN"

    # Mode 0 is rejected with REQUEST_DATA_ERROR (0xC05C) - unverified simulator policy, see issue #2
    status, _ = exchange(raw_socket, request(command=0x1002, data=struct.pack("<H", 0)))
    assert status == EndCode.REQUEST_DATA_ERROR
    assert server.state == "RUN"

    # Mode 1 is accepted with OK (0x0000) - unverified simulator policy, see issue #2
    status, _ = exchange(raw_socket, request(command=0x1002, data=struct.pack("<H", 1)))
    assert status == EndCode.OK
    assert server.state == "STOP"


def test_client_pinned_echo_and_remote_stop(client, server):
    """Client-level verification of pinned policies.

    unverified simulator policy, see issue #2; unverified (case)
    """
    assert client.echo_test("0E1") == (3, "0E1")
    assert client.echo_test("0Aa9") == (4, "0Aa9")
    with pytest.raises(Exception):
        client.echo_test("xyz")
    with pytest.raises(Exception):
        client.echo_test("hello world")

    server.set_state("RUN")
    client.remote_stop()
    assert server.state == "STOP"
