"""Opt-in, bounded UDP health counters for local simulator diagnostics (#13).

Counters describe observable socket/response events, not PLC transactions.
All real sockets bind loopback port 0. They must not change the wire protocol.
"""
import socket
import threading

import pytest

from test_ipv6_loopback_transport import ipv6_loopback
from test_m1_server_raw import device_data
from test_m3_m4_raw import packet
from virtual_plc import Server, UdpFaultPlan
from virtual_plc.codec import decode_request, encode_response


EMPTY = {
    "received": 0,
    "rejected": 0,
    "sent": 0,
    "fault_dropped": 0,
    "send_errors": 0,
    "receive_resets": 0,
}
STOPPED = {"started": False, "healthy": False, "listeners": []}


def udp_exchange(client, frame, target):
    client.sendto(frame, target)
    return client.recvfrom(8192)[0]


def test_udp_metrics_disabled_by_default_and_no_network():
    server = Server(listeners=[("udp", 0)])
    assert server.get_udp_metrics() is None
    assert server._udp_metrics is None


@pytest.mark.parametrize("bad", [None, 0, 1, "yes", [], {}])
def test_udp_metrics_requires_literal_boolean(bad):
    with pytest.raises(ValueError, match="udp_metrics"):
        Server(listeners=[("udp", 0)], udp_metrics=bad)


def test_udp_metrics_requires_udp_listener():
    with pytest.raises(ValueError, match="UDP listener"):
        Server(listeners=[("tcp", 0)], udp_metrics=True)


def test_udp_metrics_empty_and_defensive_snapshot():
    server = Server(listeners=[("udp", 0)], udp_metrics=True)
    first = server.get_udp_metrics()
    assert first == EMPTY
    first["received"] = 100
    first["unknown"] = 500
    assert server.get_udp_metrics() == EMPTY


def test_udp_metrics_count_valid_invalid_and_oversized_on_real_loopback():
    with Server(listeners=[("udp", 0)], udp_metrics=True) as server:
        good = packet("3E", "binary")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(b"nonsense", server.address)
            client.sendto(b"Z" * 9000, server.address)
            assert udp_exchange(client, good, server.address) == encode_response(
                decode_request(good), data=b"\x00\x00")
        assert server.get_udp_metrics() == {
            **EMPTY, "received": 3, "rejected": 2, "sent": 1,
        }


def test_udp_metrics_fault_drop_is_postdispatch_not_rejected():
    faults = UdpFaultPlan([
        {"match": {"command": "0x1401", "nth": 1},
         "action": {"type": "drop"}}
    ])
    with Server(listeners=[("udp", 0)], udp_metrics=True,
                udp_fault_plan=faults) as server:
        write = packet("3E", "binary", 0x1401,
                       data=device_data(payload=b"\x34\x12"))
        read = packet("4E", "binary", serial=0x1234)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(write, server.address)
            assert udp_exchange(client, read, server.address) == encode_response(
                decode_request(read), data=b"\x34\x12")
        assert server.memory.read_words("D", 0, 1) == [0x1234]
        assert server.get_udp_metrics() == {
            **EMPTY, "received": 2, "sent": 1, "fault_dropped": 1,
        }


def test_udp_metrics_two_listeners_aggregate_per_instance():
    with Server(listeners=[("udp", 0), ("udp", 0)],
                udp_metrics=True) as server:
        read = packet("3E", "binary")
        for _, host, port in server.addresses:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.settimeout(2)
                assert udp_exchange(client, read, (host, port)) == encode_response(
                    decode_request(read), data=b"\x00\x00")
        assert server.get_udp_metrics() == {
            **EMPTY, "received": 2, "sent": 2,
        }


def test_udp_metrics_restart_retains_cumulative_counts():
    server = Server(listeners=[("udp", 0)], udp_metrics=True)
    raw = packet("3E", "binary")
    try:
        for expected in (1, 2):
            server.start()
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.settimeout(2)
                assert udp_exchange(client, raw, server.address) == encode_response(
                    decode_request(raw), data=b"\x00\x00")
            server.stop()
            assert server.get_udp_metrics() == {
                **EMPTY, "received": expected, "sent": expected,
            }
    finally:
        server.stop()


def test_udp_metrics_send_error_does_not_kill_worker_or_miscount():
    """Script send failure deterministically; no platform packet loss assumptions."""
    server = Server(listeners=[("udp", 0)], udp_metrics=True)
    read = packet("3E", "binary")
    successful = []
    class Listener:
        def __init__(self):
            self.n = 0
            self.sends = 0
        def recvfrom(self, size):
            assert size == 65535
            self.n += 1
            if self.n <= 2:
                return read, ("127.0.0.1", 54321)
            server._stopping.set()
            raise OSError("script finished")
        def sendto(self, response, peer):
            self.sends += 1
            if self.sends == 1:
                raise OSError("injected UDP send failure")
            successful.append((response, peer))
            return len(response)

    listener = Listener()
    server._udp_loop(listener)
    assert successful == [(encode_response(decode_request(read),
                                          data=b"\x00\x00"), ("127.0.0.1", 54321))]
    assert server.get_udp_metrics() == {
        **EMPTY, "received": 2, "sent": 1, "send_errors": 1,
    }


def test_udp_metrics_late_shutdown_receive_is_not_rejected():
    """Data returned during stop cannot execute and is not a bad MC frame."""
    server = Server(listeners=[("udp", 0)], udp_metrics=True)
    raw = packet("3E", "binary", command=0x1401,
                 data=device_data(payload=b"\x34\x12"))
    class Listener:
        def recvfrom(self, size):
            assert size == 65535
            server._stopping.set()
            return raw, ("127.0.0.1", 50000)
        def sendto(self, *_):
            raise AssertionError("must not send after stop")

    server._udp_loop(Listener())
    assert server.memory.read_words("D", 0, 1) == [0]
    assert server.get_udp_metrics() == {**EMPTY, "received": 1}


@pytest.mark.parametrize("invalid_reply", [None, "not bytes", 123])
def test_udp_metrics_invalid_hook_reply_is_rejected_but_next_request_works(
        invalid_reply):
    """A bad user callback must not vanish from diagnostic counters."""
    frame = packet("3E", "binary")
    normal = encode_response(decode_request(frame), data=b"\x00\x00")
    calls = []
    deliveries = []

    def callback(encoded):
        calls.append(encoded)
        return invalid_reply if len(calls) == 1 else encoded

    server = Server(listeners=[("udp", 0)], udp_metrics=True,
                    response_hook=callback)

    class ScriptedListener:
        def __init__(self):
            self.received = 0

        def recvfrom(self, limit):
            assert limit == 65535
            self.received += 1
            if self.received <= 2:
                return frame, ("127.0.0.1", 55432)
            server._stopping.set()
            raise OSError("script ended")

        def sendto(self, response, peer):
            if not isinstance(response, (bytes, bytearray, memoryview)):
                raise TypeError("sendto requires bytes-like data")
            deliveries.append((bytes(response), peer))
            return len(response)

    server._udp_loop(ScriptedListener())
    assert calls == [normal, normal]
    assert deliveries == [(normal, ("127.0.0.1", 55432))]
    assert server.get_udp_metrics() == {
        **EMPTY, "received": 2, "rejected": 1, "sent": 1,
    }


@pytest.mark.parametrize("wrapper", [bytearray, memoryview])
def test_udp_metrics_preserves_existing_bytes_like_response_hooks(wrapper):
    """Do not break buffers already accepted by UDP sendto."""
    frame = packet("3E", "binary")
    expected = encode_response(decode_request(frame), data=b"\x00\x00")
    with Server(listeners=[("udp", 0)], udp_metrics=True,
                response_hook=lambda data: wrapper(data)) as server:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            assert udp_exchange(client, frame, server.address) == expected
        assert server.get_udp_metrics() == {
            **EMPTY, "received": 1, "sent": 1,
        }


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
        assert server.get_udp_metrics() == EMPTY
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
                **EMPTY, "received": count, "sent": count,
            }
            assert server.get_listener_health()["healthy"] is True
            server.stop()
            assert server.get_listener_health() == STOPPED
        assert server.get_udp_metrics() == {
            **EMPTY, "received": 2, "sent": 2,
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
            **EMPTY,
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
