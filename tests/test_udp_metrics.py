"""Opt-in, bounded UDP health counters for local simulator diagnostics (#13).

Counters describe observable socket/response events, not PLC transactions.
All real sockets bind loopback port 0. They must not change the wire protocol.
"""
import socket

import pytest

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
}


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
