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


# --- round-6 closure (C2): documented-but-unpinned counter branches -----------------

import errno

from virtual_plc import FaultPlan


@pytest.mark.parametrize("action", ["rst", "close_before_response", "close_after_response"])
def test_tcp_metrics_fault_close_counts_accepted_and_closed(action):
    plan = FaultPlan([{"action": {"type": action}}])
    with Server(port=0, tcp_metrics=True, fault_plan=plan) as server:
        with socket.create_connection(server.address, timeout=5) as client:
            client.sendall(READ)
            try:
                while client.recv(4096):
                    pass
            except OSError:
                pass  # rst surfaces as a reset
        wait_for(lambda: server.get_tcp_metrics()["closed"] == 1)
        assert server.get_tcp_metrics() == dict(EMPTY, accepted=1, closed=1)


def test_tcp_metrics_silent_hold_session_is_closed_by_stop():
    plan = FaultPlan([{"action": {"type": "silent_hold"}}])
    server = Server(port=0, tcp_metrics=True, fault_plan=plan)
    server.start()
    with socket.create_connection(server.address, timeout=5) as client:
        client.sendall(READ)
        wait_for(lambda: server.get_tcp_metrics()["accepted"] == 1)
        server.stop()
    assert server.get_tcp_metrics() == dict(EMPTY, accepted=1, closed=1)


def _scripted(server, make_connection):
    """Run the real accept loop over a fake listener that yields one connection."""
    original = server._accept_loop
    done = threading.Event()

    def scripted(_real_listener):
        class Once:
            served = False

            def accept(self):
                if Once.served:
                    raise OSError(errno.EBADF, "scripted listener exhausted")
                Once.served = True
                return make_connection(), ("127.0.0.1", 1)

        try:
            return original(Once())
        finally:
            done.set()

    server._accept_loop = scripted
    return done


def test_tcp_metrics_counts_rejection_while_stopping():
    server = Server(port=0, tcp_metrics=True)
    peers = []

    def connection_seen_while_stopping():
        left, right = socket.socketpair()
        peers.append(right)
        server._stopping.set()  # the stop flag is raised between accept() and admission
        return left

    done = _scripted(server, connection_seen_while_stopping)
    server.start()
    try:
        assert done.wait(5)
        assert server.get_tcp_metrics() == dict(EMPTY, rejected=1)
    finally:
        server.stop()
        for peer in peers:
            peer.close()


def test_tcp_metrics_ignore_sockets_that_fail_setup_before_admission():
    class BrokenSetup:
        closed = False

        def setsockopt(self, *args):
            raise OSError(errno.EINVAL, "synthetic TCP_NODELAY failure")

        def close(self):
            BrokenSetup.closed = True

    server = Server(port=0, tcp_metrics=True)
    done = _scripted(server, BrokenSetup)
    with server:
        assert done.wait(5)
        assert BrokenSetup.closed
        assert server.get_tcp_metrics() == EMPTY


def test_tcp_metrics_worker_start_failure_keeps_accepted_equal_closed(monkeypatch):
    server = Server(port=0, tcp_metrics=True)
    peers = []
    gate = threading.Event()  # hold accept() until the patch below is in place

    def connection():
        assert gate.wait(5)
        left, right = socket.socketpair()
        peers.append(right)
        return left

    done = _scripted(server, connection)
    original_start = threading.Thread.start

    def failing_start(thread):
        if getattr(thread, "_target", None) == server._serve:
            raise RuntimeError("can't start new thread")
        return original_start(thread)

    server.start()
    monkeypatch.setattr(threading.Thread, "start", failing_start)
    gate.set()
    try:
        assert done.wait(5)
        assert server.get_tcp_metrics() == dict(EMPTY, accepted=1, closed=1)
        assert not server._clients
    finally:
        monkeypatch.undo()
        server.stop()
        for peer in peers:
            peer.close()
