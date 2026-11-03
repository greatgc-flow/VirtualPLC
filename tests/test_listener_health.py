"""Read-only TCP/UDP listener health snapshots for embedded operators (#13).

Run real sockets only on 127.0.0.1 with ephemeral port 0. No background
health probe, monitor thread, automatic rebind, network endpoint or PLC I/O
side effects. An OS socket/thread check cannot certify protocol reachability.
"""
import socket

import pytest

from test_m3_m4_raw import packet
from virtual_plc import Server
from virtual_plc.codec import decode_request, encode_response


EMPTY = {"started": False, "healthy": False, "listeners": []}


@pytest.mark.parametrize("specs", [
    [("tcp", 0)],
    [("udp", 0)],
    [("tcp", 0), ("udp", 0), ("udp", 0)],
])
def test_listener_health_before_start_and_after_stop(specs):
    server = Server(listeners=specs)
    assert server.get_listener_health() == EMPTY
    with server:
        assert server.get_listener_health()["started"] is True
    assert server.get_listener_health() == EMPTY
    server.stop()
    assert server.get_listener_health() == EMPTY


@pytest.mark.parametrize("specs", [
    [("tcp", 0)],
    [("udp", 0)],
    [("tcp", 0), ("udp", 0), ("udp", 0)],
])
def test_listener_health_reports_all_real_bound_endpoints_in_order(specs):
    with Server(listeners=specs) as server:
        status = server.get_listener_health()
        assert status["started"] is True
        assert status["healthy"] is True
        assert len(status["listeners"]) == len(specs)
        for row, (transport, host, port) in zip(status["listeners"],
                                                server.addresses):
            assert row == {
                "transport": transport,
                "host": host,
                "port": port,
                "socket_open": True,
                "worker_alive": True,
                "healthy": True,
            }
            assert host == "127.0.0.1"
            assert port > 0


def test_listener_health_snapshot_is_defensive_and_creates_no_workers():
    server = Server(listeners=[("udp", 0)])
    with server:
        listener_before = server._listener
        workers_before = list(server._listener_threads)
        first = server.get_listener_health()
        first["healthy"] = False
        first["listeners"][0]["healthy"] = False
        first["listeners"].clear()
        second = server.get_listener_health()
        assert second["healthy"] is True
        assert len(second["listeners"]) == 1
        assert second["listeners"][0]["healthy"] is True
        assert server._listener is listener_before
        assert server._listener_threads == workers_before


def test_listener_health_detects_terminated_udp_worker_without_rebind():
    server = Server(listeners=[("udp", 0)])
    try:
        server.start()
        stale = server._listener
        worker = server._listener_threads[0]
        stale.close()
        worker.join(3)
        assert not worker.is_alive(), "closed UDP listener worker did not exit"
        status = server.get_listener_health()
        assert status == {
            "started": True,
            "healthy": False,
            "listeners": [{
                "transport": "udp",
                "host": server.addresses[0][1],
                "port": server.addresses[0][2],
                "socket_open": False,
                "worker_alive": False,
                "healthy": False,
            }],
        }
        server.start()  # intentionally not an automatic restart
        assert server.get_listener_health()["healthy"] is False
        assert server._listener is stale
        server.stop()
        assert server.get_listener_health() == EMPTY
        server.start()
        assert server.get_listener_health()["healthy"] is True
    finally:
        server.stop()


def test_listener_health_isolates_failed_udp_port_in_mixed_transport():
    server = Server(listeners=[("tcp", 0), ("udp", 0)])
    frame = packet("3E", "binary")
    try:
        server.start()
        failed_socket = server._listeners[1][1]
        failed_socket.close()
        failed_worker = server._listener_threads[1]
        failed_worker.join(3)
        assert not failed_worker.is_alive()
        status = server.get_listener_health()
        assert status["started"] is True
        assert status["healthy"] is False
        assert [row["healthy"] for row in status["listeners"]] == [True, False]
        assert [row["transport"] for row in status["listeners"]] == ["tcp", "udp"]
        server.stop()
        server.start()
        assert server.get_listener_health()["healthy"] is True

        # This is still a socket/thread snapshot, so verify an actual
        # response after explicit recovery with a separate real UDP client.
        address = server.addresses[1][1:]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(frame, address)
            actual, peer = client.recvfrom(8192)
        assert peer[0] == "127.0.0.1"
        assert actual == encode_response(decode_request(frame),
                                         data=b"\x00\x00")
    finally:
        server.stop()


def test_listener_health_called_by_udp_hook_during_stop_never_deadlocks():
    """stop() joins workers while holding the lifecycle RLock.

    A UDP response hook can call the public health API from its own
    worker. If health waits for the lifecycle lock after stop begins,
    stop waits for that worker forever. A bounded event handshake
    reproduces this exact order with no arbitrary sleeps.
    """
    import threading

    entered_hook = threading.Event()
    resume_hook = threading.Event()
    observed = []

    def callback(response):
        entered_hook.set()
        assert resume_hook.wait(3), "test did not release response hook"
        observed.append(server.get_listener_health())
        return response

    server = Server(listeners=[("udp", 0)], response_hook=callback)
    stopper = None
    server.start()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(packet("3E", "binary"), server.address)
        assert entered_hook.wait(3), "UDP worker did not enter response hook"
        stopper = threading.Thread(target=server.stop, daemon=True)
        stopper.start()
        assert server._stopping.wait(3), "stop() never signaled shutdown"
        resume_hook.set()
        stopper.join(3)
        assert not stopper.is_alive(), (
            "deadlock: stop() is joining the UDP worker while its "
            "response_hook waits to acquire the lifecycle lock")
        assert observed == [EMPTY], (
            "contended lifecycle snapshot must fail closed, not "
            "pretend a transitioning listener is healthy")
        assert server.get_listener_health() == EMPTY
    finally:
        resume_hook.set()
        # The RED build intentionally reproduces a daemon-thread deadlock.
        # In GREEN, stop() always completes and no resources remain.
        if stopper is None:
            server.stop()
