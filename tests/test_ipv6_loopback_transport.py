"""IPv6 loopback TCP/UDP transport parity (no physical PLC/network).

Exercise the actual OS sockets on Ubuntu and Windows. Skip only when the
runner cannot bind BOTH loopback socket types; do not infer physical MC parity.
"""
import socket

import pytest

from test_m1_server_raw import device_data, exchange, request
from test_m3_m4_raw import packet, receive
from virtual_plc import Memory, Server, UdpFaultPlan
from virtual_plc.codec import decode_request, encode_response


@pytest.fixture(scope="module")
def ipv6_loopback():
    """Test real IPv6 availability, not only the sometimes-optimistic flag."""
    if not socket.has_ipv6:
        pytest.skip("IPv6 sockets unavailable on this runner")
    for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
        try:
            with socket.socket(socket.AF_INET6, kind) as probe:
                probe.bind(("::1", 0))
        except OSError as error:
            pytest.skip("IPv6 ::1 bind unavailable: %s" % error)


@pytest.mark.parametrize("transport", ["tcp", "udp"])
@pytest.mark.parametrize("frame,wire", [
    ("3E", "binary"), ("3E", "ascii"),
    ("4E", "binary"), ("4E", "ascii"),
])
def test_ipv6_loopback_read_frame_and_sender(ipv6_loopback, transport, frame, wire):
    """3E/4E data and 4E serial survive either real IPv6 transport."""
    memory = Memory()
    memory.write_words("D", 0, [0x1234])
    with Server(host="::1", listeners=[(transport, 0)], memory=memory) as server:
        host, port = server.address
        assert (host, port) == ("::1", server.addresses[0][2])
        assert server.addresses[0][0] == transport
        raw = packet(frame, wire, serial=0xBEEF)
        if transport == "tcp":
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as client:
                client.settimeout(2)
                client.connect((host, port))
                client.sendall(raw)
                expected_data = b"1234" if wire == "ascii" else b"\x34\x12"
                assert receive(client, frame, wire, serial=0xBEEF) == (0, expected_data)
        else:
            with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as client:
                client.settimeout(2)
                client.sendto(raw, (host, port))
                reply, source = client.recvfrom(8192)
                assert source[0] == "::1" and source[1] == port
                assert reply == encode_response(decode_request(raw), data=b"\x34\x12")


def test_ipv6_tcp_udp_share_one_plc_and_request_lock(ipv6_loopback):
    """Writing over UDP is visible to TCP; writing over TCP is visible to UDP."""
    with Server(host="::1", listeners=[("tcp", 0), ("udp", 0)]) as server:
        _, tcp_host, tcp_port = server.addresses[0]
        _, udp_host, udp_port = server.addresses[1]
        udp_write = packet("4E", "ascii", command=0x1401,
                           data=b"D*00000000011234")
        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as udp:
            udp.settimeout(2)
            udp.sendto(udp_write, (udp_host, udp_port))
            reply, source = udp.recvfrom(8192)
            assert source[0] == "::1" and source[1] == udp_port
            assert reply == encode_response(decode_request(udp_write))
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as tcp:
                tcp.settimeout(2)
                tcp.connect((tcp_host, tcp_port))
                assert exchange(tcp, request(data=device_data())) == (0, b"\x34\x12")
                assert exchange(tcp, request(0x1401, data=device_data(
                    payload=b"\x78\x56"))) == (0, b"")
            udp_read = packet("3E", "binary")
            udp.sendto(udp_read, (udp_host, udp_port))
            reply, source = udp.recvfrom(8192)
            assert source[0] == "::1" and source[1] == udp_port
            assert reply == encode_response(decode_request(udp_read), data=b"\x78\x56")


@pytest.mark.parametrize("transport", ["tcp", "udp"])
def test_ipv6_listener_stop_and_restart(ipv6_loopback, transport):
    """The same Server can rebind an IPv6 loopback endpoint after stop."""
    server = Server(host="::1", listeners=[(transport, 0)])
    try:
        for _ in range(2):
            server.start()
            host, port = server.address
            assert host == "::1" and 1 <= port <= 65535
            raw = packet("3E", "binary")
            if transport == "tcp":
                with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as client:
                    client.settimeout(2)
                    client.connect((host, port))
                    client.sendall(raw)
                    assert receive(client, "3E", "binary") == (0, b"\x00\x00")
            else:
                with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as client:
                    client.settimeout(2)
                    client.sendto(raw, (host, port))
                    assert client.recvfrom(8192)[0] == encode_response(
                        decode_request(raw), data=b"\x00\x00")
            server.stop()
            assert server._listeners == []
    finally:
        server.stop()


@pytest.mark.parametrize("frame", ["3E", "4E"])
def test_ipv6_udp_oversized_malformed_then_valid(ipv6_loopback, frame):
    """Windows Winsock must recover after dropped >8192B datagrams."""
    with Server(host="::1", listeners=[("udp", 0)]) as server:
        target = server.address
        good = packet(frame, "binary")
        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as client:
            client.settimeout(0.08)
            for bad in (b"invalid", good[:-1], good + good, b"x" * 9000):
                client.sendto(bad, target)
                with pytest.raises(socket.timeout):
                    client.recvfrom(8192)
            client.settimeout(2)
            client.sendto(good, target)
            reply, sender = client.recvfrom(8192)
            assert sender[0] == "::1" and sender[1] == target[1]
            assert reply == encode_response(decode_request(good), data=b"\x00\x00")


def test_ipv6_udp_fault_selector_uses_numeric_ipv6_peer(ipv6_loopback):
    """Post-dispatch IPv6 peer selection drops once, then serves normally."""
    plan = UdpFaultPlan([{
        "match": {"command": "0x0401", "nth": 1, "peer": "::1"},
        "action": {"type": "drop"},
    }])
    with Server(host="::1", listeners=[("udp", 0)],
                udp_fault_plan=plan) as server:
        raw = packet("3E", "binary")
        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as client:
            client.settimeout(0.08)
            client.sendto(raw, server.address)
            with pytest.raises(socket.timeout):
                client.recvfrom(8192)
            client.settimeout(2)
            client.sendto(raw, server.address)
            reply, sender = client.recvfrom(8192)
            assert sender[0] == "::1" and sender[1] == server.address[1]
            assert reply == encode_response(decode_request(raw), data=b"\x00\x00")


def test_ipv6_loopback_is_local_but_wildcard_is_not():
    """IPv6 wildcard remains guarded even if IPv6 support is absent."""
    assert Server(host="::1", listeners=[("udp", 0)]).address[0] == "::1"
    with pytest.raises(ValueError, match="non-loopback"):
        Server(host="::", listeners=[("udp", 0)])
