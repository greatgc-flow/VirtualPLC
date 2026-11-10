"""Opt-in TCP session counters for local simulator diagnostics (#13).

Mirrors the UDP counters: disabled by default, local Python API only,
cumulative across stop()/start(). All real sockets bind loopback port 0.
"""
import socket
import threading
import time

import pytest

from test_m1_server_raw import receive_exact
from test_m3_m4_raw import packet
from virtual_plc import Server
from virtual_plc.codec import decode_request, encode_response


EMPTY = {"accepted": 0, "rejected": 0, "idle_closed": 0, "closed": 0}
READ = packet("3E", "binary")
REPLY = encode_response(decode_request(READ), data=b"\x00\x00")


def wait_for(predicate, timeout=5.0):
    """Poll a condition; fail only if it never becomes true."""
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition not reached"
        time.sleep(0.005)


def roundtrip(address):
    with socket.create_connection(address, timeout=5) as client:
        client.sendall(READ)
        assert receive_exact(client, len(REPLY)) == REPLY


def test_tcp_metrics_disabled_by_default_and_no_network():
    server = Server()
    assert server.get_tcp_metrics() is None
    assert server._tcp_metrics is None


def test_tcp_metrics_disabled_session_still_served():
    with Server() as server:
        roundtrip(server.address)
    assert server.get_tcp_metrics() is None


@pytest.mark.parametrize("bad", [None, 0, 1, "yes", [], {}])
def test_tcp_metrics_requires_literal_boolean(bad):
    with pytest.raises(ValueError, match="tcp_metrics"):
        Server(tcp_metrics=bad)


def test_tcp_metrics_requires_tcp_listener():
    with pytest.raises(ValueError, match="TCP listener"):
        Server(listeners=[("udp", 0)], tcp_metrics=True)


def test_tcp_metrics_empty_and_defensive_snapshot():
    server = Server(tcp_metrics=True)
    first = server.get_tcp_metrics()
    assert first == EMPTY
    first["accepted"] = 100
    first["unknown"] = 500
    assert server.get_tcp_metrics() == EMPTY


def test_tcp_metrics_accepted_and_closed_on_real_loopback():
    with Server(tcp_metrics=True) as server:
        roundtrip(server.address)
        wait_for(lambda: server.get_tcp_metrics()["closed"] == 1)
        assert server.get_tcp_metrics() == {**EMPTY, "accepted": 1, "closed": 1}
        # A session still open at stop() is closed and counted by stop().
        client = socket.create_connection(server.address, timeout=5)
        wait_for(lambda: server.get_tcp_metrics()["accepted"] == 2)
    client.close()
    assert server.get_tcp_metrics() == {**EMPTY, "accepted": 2, "closed": 2}


def test_tcp_metrics_rejected_at_max_clients_is_not_accepted_or_closed():
    with Server(tcp_metrics=True, max_clients=1) as server:
        with socket.create_connection(server.address, timeout=5) as holder:
            holder.sendall(READ)
            assert receive_exact(holder, len(REPLY)) == REPLY
            with socket.create_connection(server.address, timeout=5) as refused:
                wait_for(lambda: server.get_tcp_metrics()["rejected"] == 1)
                try:
                    assert refused.recv(1) == b""
                except ConnectionResetError:
                    pass
            assert server.get_tcp_metrics() == {**EMPTY, "accepted": 1, "rejected": 1}
        wait_for(lambda: server.get_tcp_metrics()["closed"] == 1)
    assert server.get_tcp_metrics() == {**EMPTY, "accepted": 1, "rejected": 1, "closed": 1}


def test_tcp_metrics_idle_timeout_close_counts_idle_and_closed():
    with Server(tcp_metrics=True, idle_timeout=0.2) as server:
        with socket.create_connection(server.address, timeout=5) as idle:
            assert idle.recv(1) == b""  # server closed the idle session
            wait_for(lambda: server.get_tcp_metrics()["closed"] == 1)
        roundtrip(server.address)  # an EOF close is not an idle close
        wait_for(lambda: server.get_tcp_metrics()["closed"] == 2)
    assert server.get_tcp_metrics() == {**EMPTY, "accepted": 2, "idle_closed": 1, "closed": 2}


def test_tcp_metrics_restart_retains_cumulative_counts():
    server = Server(tcp_metrics=True)
    try:
        for expected in (1, 2):
            server.start()
            roundtrip(server.address)
            server.stop()
            assert server.get_tcp_metrics() == {**EMPTY, "accepted": expected, "closed": expected}
    finally:
        server.stop()


def test_tcp_metrics_exact_under_concurrent_sessions_across_listeners():
    clients = 24
    with Server(listeners=[("tcp", 0), ("tcp", 0), ("udp", 0)],
                tcp_metrics=True, udp_metrics=True) as server:
        targets = [(host, port) for transport, host, port in server.addresses
                   if transport == "tcp"]
        barrier = threading.Barrier(clients)
        errors = []

        def run(index):
            try:
                barrier.wait(timeout=5)
                roundtrip(targets[index % len(targets)])
            except BaseException as error:  # surfaced below
                errors.append(error)

        workers = [threading.Thread(target=run, args=(i,)) for i in range(clients)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        assert errors == []
    assert server.get_tcp_metrics() == {**EMPTY, "accepted": clients, "closed": clients}
    assert server.get_udp_metrics()["received"] == 0
