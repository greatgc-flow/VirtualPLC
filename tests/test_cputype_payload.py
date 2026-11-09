"""CPU type requests have an empty payload on every 3E/4E transport."""

import socket

import pytest

from test_m3_m4_raw import packet, receive


@pytest.mark.parametrize("frame", ["3E", "4E"])
@pytest.mark.parametrize("wire", ["binary", "ascii"])
@pytest.mark.parametrize("data", [b"", b"0", b"0000", b"GG"])
def test_cputype_payload_length(server, frame, wire, data):
    with socket.create_connection(server.address, timeout=2) as connection:
        connection.sendall(packet(frame, wire, 0x0101, data=data))
        assert receive(connection, frame, wire)[0] == (0xC057 if data else 0)
