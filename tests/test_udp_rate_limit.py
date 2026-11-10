"""Opt-in per-source-IP UDP rate limit (#13 narrowed scope point 2).

A token bucket per peer IP drops over-limit datagrams before parsing or
dispatch, so a UDP flood never takes the shared request lock that TCP clients
need. Clocks are injected (no sleeps); real sockets bind loopback port 0.
"""
import re
import socket
import struct
import threading
from types import SimpleNamespace

import pytest

import virtual_plc.__main__ as cli
from test_ipv6_loopback_transport import ipv6_loopback
from test_m3_m4_raw import packet
from virtual_plc import Server, UdpFaultPlan
from virtual_plc.codec import decode_request, encode_response
from virtual_plc.udp_rate_limit import MAX_TRACKED_PEERS, UdpRateLimiter


class Clock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


def scripted(*times):
    """One reading per datagram, independent of thread timing."""
    readings = iter(times)
    return lambda: next(readings)


# --- limiter unit behaviour -------------------------------------------------

def test_bucket_starts_full_then_drops_until_refilled():
    clock = Clock()
    limiter = UdpRateLimiter(3, 1.5, clock=clock)
    assert [limiter.allow("10.0.0.1") for _ in range(4)] == [True, True, True, False]
    clock.now = 0.25  # half a token: still short of one
    assert limiter.allow("10.0.0.1") is False
    clock.now = 0.5   # exactly one token (3 per 1.5 s)
    assert limiter.allow("10.0.0.1") is True
    assert limiter.allow("10.0.0.1") is False


def test_refill_is_capped_at_burst_size():
    clock = Clock()
    limiter = UdpRateLimiter(2, 1, clock=clock)
    assert limiter.allow("a") and limiter.allow("a")
    clock.now = 1000.0
    assert [limiter.allow("a") for _ in range(3)] == [True, True, False]


def test_dropped_datagrams_do_not_consume_tokens():
    clock = Clock()
    limiter = UdpRateLimiter(1, 1, clock=clock)
    assert limiter.allow("a")
    for _ in range(50):
        assert not limiter.allow("a")
    clock.now = 1.0
    assert limiter.allow("a")


def test_buckets_are_independent_per_ip():
    limiter = UdpRateLimiter(1, 60, clock=Clock())
    assert limiter.allow("127.0.0.1") and not limiter.allow("127.0.0.1")
    assert limiter.allow("::1") and limiter.allow("127.0.0.2")


def test_tracked_peers_are_bounded_with_lru_eviction():
    limiter = UdpRateLimiter(1, 60, clock=Clock(), max_peers=2)
    assert limiter.allow("a") and limiter.allow("b")
    assert not limiter.allow("a")          # a is now most recently used
    assert limiter.allow("c")              # evicts b, the least recently used
    assert len(limiter) == 2
    assert not limiter.allow("a") and not limiter.allow("c")
    assert limiter.allow("b")              # evicted peer returns with a full bucket
    assert len(limiter) == 2


def test_default_peer_cap_bounds_memory_under_many_sources():
    limiter = UdpRateLimiter(1, 60, clock=Clock())
    for index in range(MAX_TRACKED_PEERS + 500):
        limiter.allow(f"10.{index >> 16 & 255}.{index >> 8 & 255}.{index & 255}")
    assert len(limiter) == MAX_TRACKED_PEERS == 1024


def test_tiny_window_with_zero_elapsed_is_well_defined():
    limiter = UdpRateLimiter(1, 1e-300, clock=Clock())
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False  # same instant: no refill, no NaN


# --- Server validation ------------------------------------------------------

def test_disabled_by_default():
    server = Server(listeners=[("udp", 0)])
    assert server._udp_rate_limiter is None


@pytest.mark.parametrize("value", [(1, 1), [5, 0.25], (1_000_000_000, 3600)])
def test_valid_rate_limits_are_accepted(value):
    server = Server(listeners=[("udp", 0)], udp_rate_limit=value)
    assert isinstance(server._udp_rate_limiter, UdpRateLimiter)


@pytest.mark.parametrize("bad", [
    5, "5/1", (5,), (5, 1, 2), {5: 1}, (0, 1), (-1, 1), (True, 1), (1.5, 1),
    (1_000_000_001, 1), (5, 0), (5, -1), (5, float("nan")), (5, float("inf")),
    (5, True), (5, "1"), (5, None), (5, 10 ** 400),
])
def test_invalid_rate_limits_raise_before_bind(bad):
    with pytest.raises(ValueError, match="udp_rate_limit"):
        Server(listeners=[("udp", 0)], udp_rate_limit=bad)


def test_rate_limit_requires_udp_listener():
    with pytest.raises(ValueError, match="UDP listener"):
        Server(listeners=[("tcp", 0)], udp_rate_limit=(5, 1))
    with pytest.raises(ValueError, match="UDP listener"):
        Server(udp_rate_limit=(5, 1))


# --- real loopback datagrams ------------------------------------------------

def serial_of(reply):
    return struct.unpack_from("<H", reply, 2)[0]


def test_over_limit_datagrams_get_no_reply_and_are_counted():
    with Server(listeners=[("udp", 0)], udp_metrics=True,
                udp_rate_limit=(2, 60)) as server:
        server._udp_rate_limiter._clock = scripted(0, 0, 0, 0, 30)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            for serial in range(1, 6):
                client.sendto(packet("4E", "binary", serial=serial), server.address)
            replies = [client.recvfrom(8192)[0] for _ in range(3)]
        assert [serial_of(reply) for reply in replies] == [1, 2, 5]
        expected = packet("4E", "binary", serial=5)
        assert replies[-1] == encode_response(decode_request(expected), data=b"\x00\x00")
    assert server.get_udp_metrics() == {
        "received": 5, "rejected": 0, "sent": 3, "fault_dropped": 0,
        "send_errors": 0, "receive_resets": 0, "rate_limited": 2,
    }


def test_limit_is_per_ip_not_per_source_port():
    with Server(listeners=[("udp", 0)], udp_metrics=True,
                udp_rate_limit=(1, 60)) as server:
        server._udp_rate_limiter._clock = scripted(0, 0, 60)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as first, \
                socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as second:
            first.settimeout(2)
            second.settimeout(2)
            first.sendto(packet("4E", "binary", serial=1), server.address)
            assert serial_of(first.recvfrom(8192)[0]) == 1
            second.sendto(packet("4E", "binary", serial=2), server.address)  # same IP: dropped
            second.sendto(packet("4E", "binary", serial=3), server.address)  # refilled
            assert serial_of(second.recvfrom(8192)[0]) == 3
    assert server.get_udp_metrics()["rate_limited"] == 1


def test_bucket_is_shared_across_udp_listeners():
    with Server(listeners=[("udp", 0), ("udp", 0)], udp_metrics=True,
                udp_rate_limit=(1, 60)) as server:
        server._udp_rate_limiter._clock = scripted(0, 0, 60)
        (_, host, port_a), (_, _, port_b) = server.addresses
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(packet("4E", "binary", serial=1), (host, port_a))
            assert serial_of(client.recvfrom(8192)[0]) == 1
            # Both to listener B, so one worker reads the clock in send order.
            client.sendto(packet("4E", "binary", serial=2), (host, port_b))
            client.sendto(packet("4E", "binary", serial=3), (host, port_b))
            assert serial_of(client.recvfrom(8192)[0]) == 3
    assert server.get_udp_metrics()["rate_limited"] == 1


class CountingLock:
    def __init__(self, lock):
        self.lock = lock
        self.acquired = 0

    def __enter__(self):
        self.acquired += 1
        return self.lock.__enter__()

    def __exit__(self, *exc):
        return self.lock.__exit__(*exc)


def test_rate_limited_datagrams_never_take_the_request_lock():
    server = Server(listeners=[("udp", 0), ("tcp", 0)], udp_rate_limit=(1, 60))
    lock = CountingLock(server._request_lock)
    server._request_lock = lock
    server._udp_rate_limiter._clock = scripted(*([0] * 51), 60)
    with server:
        target = server.addresses[0][1:]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(packet("4E", "binary", serial=1), target)
            assert serial_of(client.recvfrom(8192)[0]) == 1
            per_request = lock.acquired
            assert per_request >= 1
            for serial in range(2, 52):  # flood: 50 over-limit datagrams
                client.sendto(packet("4E", "binary", serial=serial), target)
            client.sendto(packet("4E", "binary", serial=99), target)
            assert serial_of(client.recvfrom(8192)[0]) == 99
        assert lock.acquired == 2 * per_request
        with socket.create_connection(server.addresses[1][1:], timeout=2) as tcp:
            frame = packet("3E", "binary")
            expected = encode_response(decode_request(frame), data=b"\x00\x00")
            tcp.sendall(frame)
            reply = b""
            while len(reply) < len(expected):
                chunk = tcp.recv(64)
                assert chunk
                reply += chunk
            assert reply == expected


def test_over_limit_drop_happens_before_size_and_parse_checks():
    with Server(listeners=[("udp", 0)], udp_metrics=True,
                udp_rate_limit=(1, 60)) as server:
        server._udp_rate_limiter._clock = scripted(0, 0, 0, 60)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(b"nonsense", server.address)     # consumes the token, rejected
            client.sendto(b"Z" * 9000, server.address)     # over limit
            client.sendto(b"nonsense", server.address)     # over limit
            client.sendto(packet("4E", "binary", serial=7), server.address)
            assert serial_of(client.recvfrom(8192)[0]) == 7
    assert server.get_udp_metrics() == {
        "received": 4, "rejected": 1, "sent": 1, "fault_dropped": 0,
        "send_errors": 0, "receive_resets": 0, "rate_limited": 2,
    }


def test_metrics_without_rate_limit_report_zero_rate_limited():
    with Server(listeners=[("udp", 0)], udp_metrics=True) as server:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            for serial in range(1, 4):
                client.sendto(packet("4E", "binary", serial=serial), server.address)
                assert serial_of(client.recvfrom(8192)[0]) == serial
    assert server.get_udp_metrics()["rate_limited"] == 0


# --- CLI ----------------------------------------------------------------------

def _exit_code(arguments):
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    return error.value.code


@pytest.mark.parametrize("value", ["5", "5/", "/1", "0/1", "-1/1", "5/0", "5/-1", "x/1",
                                   "5/nan", "5/inf", "1.5/1", "5/1/2", "", "1000000001/1",
                                   "100/1_0", "5/1e3", "5/ 1", "5/1 ", " 5/1", "5/.5", "5/1.",
                                   "5/+1", "5/0x10", "5/infinity"])
def test_cli_rejects_malformed_rate_limit(capsys, value):
    assert _exit_code(["--listen", "udp:0", "--udp-rate-limit", value]) == 2
    assert "--udp-rate-limit" in capsys.readouterr().err


def test_cli_rate_limit_requires_udp_listener(monkeypatch, capsys):
    monkeypatch.setattr(cli.Server, "start", lambda self: pytest.fail("must not bind"))
    assert _exit_code(["--port", "0", "--udp-rate-limit", "5/1"]) == 2
    assert "UDP listener" in capsys.readouterr().err


@pytest.mark.parametrize("value, expected", [("100/1", (100, 1.0)), ("5/0.25", (5, 0.25))])
def test_cli_rate_limit_reaches_server(monkeypatch, capsys, value, expected):
    seen = []

    def start(self):
        seen.append(self._udp_rate_limiter)
        raise OSError("stop here")

    monkeypatch.setattr(cli.Server, "start", start)
    assert cli.main(["--listen", "udp:0", "--udp-rate-limit", value]) == 1
    assert (seen[0].requests, seen[0].per_seconds) == expected


def test_cli_without_flag_keeps_limiter_off(monkeypatch):
    seen = []

    def start(self):
        seen.append(self._udp_rate_limiter)
        raise OSError("stop here")

    monkeypatch.setattr(cli.Server, "start", start)
    assert cli.main(["--listen", "udp:0"]) == 1
    assert seen == [None]


@pytest.mark.parametrize("arguments, shown", [
    ([], "udp_rate_limit=None "),
    (["--udp-rate-limit", "100/2"], "udp_rate_limit=100/2.0 "),
    (["--udp-rate-limit", "5/1234567.5"], "udp_rate_limit=5/1234567.5 "),
])
def test_banner_shows_rate_limit(monkeypatch, capsys, arguments, shown):
    def interrupt(timeout):
        raise KeyboardInterrupt

    # Replace only the CLI's view of threading; the real Server still needs Event.
    monkeypatch.setattr(cli, "threading", SimpleNamespace(Event=lambda: SimpleNamespace(wait=interrupt)))
    assert cli.main(["--listen", "udp:0", *arguments]) == 0
    assert shown in capsys.readouterr().err


def test_cli_window_above_timeout_max_names_the_bound(capsys):
    too_long = f"5/{int(threading.TIMEOUT_MAX) + 1}"
    assert _exit_code(["--listen", "udp:0", "--udp-rate-limit", too_long]) == 2
    error = capsys.readouterr().err
    assert "--udp-rate-limit" in error and "threading.TIMEOUT_MAX" in error
    assert repr(threading.TIMEOUT_MAX) in error


def test_server_window_error_names_the_platform_bound():
    with pytest.raises(ValueError, match=re.escape(repr(threading.TIMEOUT_MAX))):
        Server(listeners=[("udp", 0)], udp_rate_limit=(5, threading.TIMEOUT_MAX * 2))


def test_buckets_persist_across_stop_and_start():
    server = Server(listeners=[("udp", 0)], udp_metrics=True, udp_rate_limit=(1, 60))
    server._udp_rate_limiter._clock = scripted(0, 0, 0, 60)
    try:
        server.start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(packet("4E", "binary", serial=1), server.address)
            assert serial_of(client.recvfrom(8192)[0]) == 1
        server.stop()
        server.start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(packet("4E", "binary", serial=2), server.address)  # still exhausted
            client.sendto(packet("4E", "binary", serial=3), server.address)  # still exhausted
            client.sendto(packet("4E", "binary", serial=4), server.address)  # refilled at 60 s
            assert serial_of(client.recvfrom(8192)[0]) == 4
    finally:
        server.stop()
    metrics = server.get_udp_metrics()
    assert (metrics["rate_limited"], metrics["sent"]) == (2, 2)


def test_rate_limited_datagrams_leave_fault_plan_nth_unconsumed():
    faults = UdpFaultPlan([{"match": {"command": "0x0401", "nth": 2},
                            "action": {"type": "drop"}}])
    with Server(listeners=[("udp", 0)], udp_metrics=True, udp_fault_plan=faults,
                udp_rate_limit=(1, 60)) as server:
        server._udp_rate_limiter._clock = scripted(0, 0, 60, 120)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            for serial in range(1, 5):
                client.sendto(packet("4E", "binary", serial=serial), server.address)
            # 1 replies (plan nth 1); 2 is rate limited and must not count;
            # 3 is the plan's nth 2 and is dropped; 4 replies.
            assert [serial_of(client.recvfrom(8192)[0]) for _ in range(2)] == [1, 4]
    assert server.get_udp_metrics() == {
        "received": 4, "rejected": 0, "sent": 2, "fault_dropped": 1,
        "send_errors": 0, "receive_resets": 0, "rate_limited": 1,
    }


def test_ipv6_loopback_peer_is_limited_by_its_address(ipv6_loopback):
    with Server(host="::1", listeners=[("udp", 0)], udp_metrics=True,
                udp_rate_limit=(1, 60)) as server:
        server._udp_rate_limiter._clock = scripted(0, 0, 60)
        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            for serial in range(1, 4):
                client.sendto(packet("4E", "binary", serial=serial), server.address)
            assert [serial_of(client.recvfrom(8192)[0]) for _ in range(2)] == [1, 3]
        assert list(server._udp_rate_limiter._buckets) == ["::1"]
    assert server.get_udp_metrics()["rate_limited"] == 1
