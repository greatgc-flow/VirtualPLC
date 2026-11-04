"""Cross-feature IPv6 loopback characterization for opt-in UDP metrics / Health.

Extends the independent #56 transport coverage against the #62 combined
implementation; no changes to wire protocol, real PLC or nonlocal traffic.
"""
import socket
import threading

import pytest

from test_ipv6_loopback_transport import ipv6_loopback
from test_m3_m4_raw import packet
from virtual_plc import Server, UdpFaultPlan
from virtual_plc.codec import decode_request, encode_response


EMPTY_METRICS = {
    "received": 0,
    "rejected": 0,
    "sent": 0,
    "fault_dropped": 0,
    "send_errors": 0,
}
STOPPED = {"started": False, "healthy": False, "listeners": []}


@pytest.mark.parametrize("frame,wire", [("3E", "binary"), ("4E", "ascii")])
def test_ipv6_udp_metrics_and_mixed_listener_health_survive_manual_restart(
        ipv6_loopback, frame, wire):
    """Real IPv6 reply, TCP sibling Health and opt-in counters across restart."""
    server = Server(host="::1", listeners=[("tcp", 0), ("udp", 0)],
                    udp_metrics=True)
    sent = threading.Event()
    original_count = server._count_udp

    def watch_count(key):
        original_count(key)
        if key == "sent":
            sent.set()

    server._count_udp = watch_count
    raw = packet(frame, wire, serial=0xBEEF)
    reply_expected = encode_response(decode_request(raw), data=b"\x00\x00")
    try:
        assert server.get_udp_metrics() == EMPTY_METRICS
        assert server.get_listener_health() == STOPPED
        for count in (1, 2):
            sent.clear()
            server.start()
            endpoints = server.get_listener_health()
            assert endpoints["started"] is True
            assert endpoints["healthy"] is True
            assert len(endpoints["listeners"]) == 2
            assert [x["transport"] for x in endpoints["listeners"]] == ["tcp", "udp"]
            assert all(x["host"] == "::1" and x["healthy"]
                       for x in endpoints["listeners"])
            _, host, port = server.addresses[1]
            with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as client:
                client.settimeout(2)
                client.sendto(raw, (host, port))
                actual, origin = client.recvfrom(8192)
            assert actual == reply_expected
            assert origin[0] == "::1" and origin[1] == port
            assert sent.wait(3), "successful reply was not accounted"
            assert server.get_udp_metrics() == {
                **EMPTY_METRICS, "received": count, "sent": count,
            }
            assert server.get_listener_health()["healthy"] is True
            server.stop()
            assert server.get_listener_health() == STOPPED
        assert server.get_udp_metrics() == {
            **EMPTY_METRICS, "received": 2, "sent": 2,
        }
    finally:
        server.stop()


def test_ipv6_fault_drop_counts_once_and_keeps_listener_healthy(ipv6_loopback):
    """IPv6 source selector is applied after dispatch; drop is not rejection."""
    plan = UdpFaultPlan([{
        "match": {"command": "0x0401", "nth": 1, "peer": "::1"},
        "action": {"type": "drop"},
    }])
    server = Server(host="::1", listeners=[("udp", 0)],
                    udp_metrics=True, udp_fault_plan=plan)
    dropped = threading.Event()
    sent = threading.Event()
    original_count = server._count_udp

    def watch_count(key):
        original_count(key)
        if key == "fault_dropped":
            dropped.set()
        if key == "sent":
            sent.set()

    server._count_udp = watch_count
    frame = packet("3E", "binary")
    expected = encode_response(decode_request(frame), data=b"\x00\x00")
    try:
        server.start()
        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as client:
            client.settimeout(0.2)
            client.sendto(frame, server.address)
            assert dropped.wait(3), "IPv6 fault selector was not exercised"
            with pytest.raises(socket.timeout):
                client.recvfrom(8192)
            client.settimeout(2)
            client.sendto(frame, server.address)
            reply, origin = client.recvfrom(8192)
        assert reply == expected
        assert origin[0] == "::1" and origin[1] == server.address[1]
        assert sent.wait(3), "second reply was not counted"
        assert server.get_udp_metrics() == {
            **EMPTY_METRICS,
            "received": 2,
            "fault_dropped": 1,
            "sent": 1,
        }
        health = server.get_listener_health()
        assert health["healthy"] is True
        assert health["listeners"][0]["transport"] == "udp"
        assert health["listeners"][0]["host"] == "::1"
    finally:
        server.stop()
        assert server.get_listener_health() == STOPPED
