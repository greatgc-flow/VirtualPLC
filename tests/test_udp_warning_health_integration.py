"""Integration contract for UDP terminal warning, metrics and listener health (#13).

Run only on local loopback. Combines registered-worker terminal receive warning,
listener health degradation, multi-listener sibling isolation, opt-in UDP metrics
and native Windows Winsock 10054 verification.
"""
import logging
import socket
import sys
import threading

import pytest

from test_m3_m4_raw import packet
from virtual_plc import Server
from virtual_plc.codec import decode_request, encode_response

LOG_NAME = "virtual_plc.server"
EMPTY = {"started": False, "healthy": False, "listeners": []}
EMPTY_METRICS = {
    "received": 0, "rejected": 0, "sent": 0,
    "fault_dropped": 0, "send_errors": 0,
}


def _udp_read(server, index):
    frame = packet("3E", "binary")
    transport, host, port = server.addresses[index]
    assert transport == "udp"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(2)
        client.sendto(frame, (host, port))
        reply, peer = client.recvfrom(8192)
    assert peer[0] == "127.0.0.1"
    assert reply == encode_response(decode_request(frame), data=b"\x00\x00")


@pytest.mark.parametrize("listeners", [
    [("udp", 0)],
    [("tcp", 0), ("udp", 0)],
])
def test_terminal_error_emits_one_warning_and_degrades_registered_udp_health(
        caplog, listeners):
    """Error originates in a real registered worker; TCP sibling stays healthy."""
    server = Server(listeners=listeners)
    original_loop = server._udp_loop
    entered = threading.Event()
    release = threading.Event()
    receives = []

    def instrumented_loop(real_socket):
        class FailingReceive:
            def recvfrom(self, length):
                assert length == 65535
                receives.append(length)
                entered.set()
                assert release.wait(4), "UDP receive gate timed out"
                raise OSError(10054, "synthetic ICMP-like receive failure")

        return original_loop(FailingReceive())

    server._udp_loop = instrumented_loop
    index = next(i for i, spec in enumerate(listeners) if spec[0] == "udp")
    try:
        with caplog.at_level(logging.WARNING, logger=LOG_NAME):
            server.start()
            assert entered.wait(3), "registered UDP worker did not start"
            release.set()
            udp_worker = server._listener_threads[index]
            udp_worker.join(3)
            assert not udp_worker.is_alive(), "terminal UDP worker kept running"
            assert receives == [65535], "unexpected busy retry after terminal error"

            report = server.get_listener_health()
            assert report["started"] is True
            assert report["healthy"] is False
            assert len(report["listeners"]) == len(listeners)
            udp = report["listeners"][index]
            assert udp["transport"] == "udp"
            assert udp["socket_open"] is True
            assert udp["worker_alive"] is False
            assert udp["healthy"] is False
            if index:
                tcp = report["listeners"][0]
                assert tcp["transport"] == "tcp"
                assert tcp["socket_open"] is True
                assert tcp["worker_alive"] is True
                assert tcp["healthy"] is True

            warnings = [record for record in caplog.records
                        if record.name == LOG_NAME
                        and "UDP receive failed; listener worker stopped"
                        in record.getMessage()]
            assert len(warnings) == 1
            assert "10054" in warnings[0].getMessage()

            old_endpoint = server._listener
            server.start()
            assert server._listener is old_endpoint
            assert server.get_listener_health()["healthy"] is False

            server.stop()
            assert server.get_listener_health() == EMPTY
            server._udp_loop = original_loop
            server.start()
            assert server.get_listener_health()["healthy"] is True
            _udp_read(server, index)
    finally:
        release.set()
        server.stop()


def test_metrics_and_terminal_warning_are_both_preserved_in_registered_worker(caplog):
    """One successful datagram then 10054; no retry/error counting or replay."""
    server = Server(listeners=[("udp", 0)], udp_metrics=True)
    original_loop = server._udp_loop
    frame = packet("3E", "binary")
    expected = encode_response(decode_request(frame), data=b"\x00\x00")
    operations = []

    def scripted_loop(real_socket):
        class SocketAdapter:
            def recvfrom(self, size):
                assert size == 65535
                operations.append("receive")
                if operations.count("receive") == 1:
                    return frame, ("127.0.0.1", 54321)
                raise OSError(10054, "synthetic terminal UDP receive")

            def sendto(self, payload, peer):
                assert bytes(payload) == expected
                assert peer == ("127.0.0.1", 54321)
                operations.append("send")
                return len(payload)

        return original_loop(SocketAdapter())

    server._udp_loop = scripted_loop
    try:
        with caplog.at_level(logging.WARNING, logger=LOG_NAME):
            server.start()
            worker = server._listener_threads[0]
            worker.join(3)
        assert not worker.is_alive()
        assert operations == ["receive", "send", "receive"]
        warnings = [r for r in caplog.records
                    if r.name == LOG_NAME
                    and "UDP receive failed; listener worker stopped" in r.getMessage()]
        assert len(warnings) == 1
        assert "10054" in warnings[0].getMessage()
        health = server.get_listener_health()
        assert health["started"] is True
        assert health["healthy"] is False
        assert health["listeners"][0]["socket_open"] is True
        assert health["listeners"][0]["worker_alive"] is False
        assert server.get_udp_metrics() == {**EMPTY_METRICS, "received": 1, "sent": 1}

        server.stop()
        server._udp_loop = original_loop
        server.start()
        assert server.get_listener_health()["healthy"] is True
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(frame, server.address)
            assert client.recvfrom(8192)[0] == expected
        assert server.get_udp_metrics() == {**EMPTY_METRICS, "received": 2, "sent": 2}
    finally:
        server.stop()


def test_one_terminal_udp_worker_preserves_other_udp_port_and_metrics(caplog):
    """One warning/degraded aggregate Health, surviving sibling and recovery."""
    server = Server(listeners=[("udp", 0), ("udp", 0)], udp_metrics=True)
    original_loop = server._udp_loop
    original_count = server._count_udp
    blocked = threading.Event()
    release = threading.Event()
    sent = threading.Event()
    first_receives = []

    def count_and_signal(kind):
        original_count(kind)
        if kind == "sent":
            sent.set()

    def scripted_first_worker(real_socket):
        if real_socket is not server._listeners[0][1]:
            return original_loop(real_socket)

        class TerminalReceive:
            def recvfrom(self, length):
                assert length == 65535
                first_receives.append(length)
                blocked.set()
                assert release.wait(4), "terminal receive gate timed out"
                raise OSError(10054, "synthetic terminal UDP error")

            def sendto(self, *_):
                raise AssertionError("failed UDP worker must not send")

        return original_loop(TerminalReceive())

    server._udp_loop = scripted_first_worker
    server._count_udp = count_and_signal
    frame = packet("3E", "binary")
    expected = encode_response(decode_request(frame), data=b"\x00\x00")

    def healthy_read(index):
        sent.clear()
        transport, host, port = server.addresses[index]
        assert transport == "udp" and host == "127.0.0.1"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(frame, (host, port))
            response, origin = client.recvfrom(8192)
        assert response == expected
        assert origin == (host, port)
        assert sent.wait(3), "successful reply not reflected in metrics"

    try:
        with caplog.at_level(logging.WARNING, logger=LOG_NAME):
            server.start()
            assert blocked.wait(3), "registered failing worker did not start"
            release.set()
            failing_worker = server._listener_threads[0]
            failing_worker.join(3)
            assert not failing_worker.is_alive()
            assert first_receives == [65535], "terminal recvfrom was retried"

            health = server.get_listener_health()
            assert health["started"] is True
            assert health["healthy"] is False
            assert len(health["listeners"]) == 2
            assert [entry["healthy"] for entry in health["listeners"]] == [False, True]
            assert [entry["socket_open"] for entry in health["listeners"]] == [True, True]
            assert [entry["worker_alive"] for entry in health["listeners"]] == [False, True]
            healthy_read(1)
            assert server.get_udp_metrics() == {
                **EMPTY_METRICS, "received": 1, "sent": 1,
            }
            warnings = [
                item for item in caplog.records
                if item.name == LOG_NAME
                and "UDP receive failed; listener worker stopped" in item.getMessage()
            ]
            assert len(warnings) == 1
            assert "10054" in warnings[0].getMessage()

            server.start()
            assert server.get_listener_health()["healthy"] is False

            server.stop()
            assert server.get_listener_health() == EMPTY
            server._udp_loop = original_loop
            server.start()
            assert server.get_listener_health()["healthy"] is True
            healthy_read(0)
            healthy_read(1)
            assert server.get_udp_metrics() == {
                **EMPTY_METRICS, "received": 3, "sent": 3,
            }
    finally:
        release.set()
        server.stop()


def test_normal_udp_stop_is_quiet_and_health_clears(caplog):
    server = Server(listeners=[("udp", 0)])
    with caplog.at_level(logging.WARNING, logger=LOG_NAME):
        server.start()
        assert server.get_listener_health()["healthy"] is True
        server.stop()
    assert server.get_listener_health() == EMPTY
    assert not any("UDP receive failed" in r.getMessage()
                   for r in caplog.records if r.name == LOG_NAME)


def test_metrics_and_nonblocking_health_from_hook_while_stop_joins(caplog):
    """End-to-end hook/stop race with metrics and no-warning outcome."""
    entered = threading.Event()
    release = threading.Event()
    snapshots = []

    def hook(response):
        entered.set()
        assert release.wait(4)
        snapshots.append((server.get_udp_metrics(), server.get_listener_health()))
        return response

    server = Server(listeners=[("udp", 0)], udp_metrics=True, response_hook=hook)
    stopper = None
    try:
        with caplog.at_level(logging.WARNING, logger=LOG_NAME):
            server.start()
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.sendto(packet("3E", "binary"), server.address)
            assert entered.wait(3)
            stopper = threading.Thread(target=server.stop, daemon=True)
            stopper.start()
            assert server._stopping.wait(3)
            release.set()
            stopper.join(3)
            assert not stopper.is_alive(), "stop/join/hook deadlocked"
            assert snapshots == [({**EMPTY_METRICS, "received": 1}, EMPTY)]
            assert server.get_udp_metrics() == {**EMPTY_METRICS, "received": 1}
            assert server.get_listener_health() == EMPTY
            assert not any("UDP receive failed" in r.getMessage()
                           for r in caplog.records if r.name == LOG_NAME)
    finally:
        release.set()
        if stopper is None:
            server.stop()


@pytest.mark.skipif(sys.platform != "win32",
                    reason="native WSAECONNRESET requires Windows Winsock")
def test_native_windows_10054_is_logged_unhealthy_then_recoverable(caplog):
    """Genuine local Windows ICMP after reply to closed UDP client port."""
    entered = threading.Event()
    release = threading.Event()
    observed_socket_errors = []

    def hook(response):
        entered.set()
        assert release.wait(4), "response gate was not released"
        return response

    server = Server(listeners=[("udp", 0)], response_hook=hook)
    original_loop = server._udp_loop

    def traced_loop(real_socket):
        class TraceSocket:
            def recvfrom(self, length):
                try:
                    return real_socket.recvfrom(length)
                except socket.timeout:
                    raise
                except OSError as error:
                    observed_socket_errors.append(
                        getattr(error, "winerror", None) or error.errno)
                    raise

            def sendto(self, data, peer):
                return real_socket.sendto(data, peer)

        return original_loop(TraceSocket())

    server._udp_loop = traced_loop
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind(("127.0.0.1", 0))
    try:
        with caplog.at_level(logging.WARNING, logger=LOG_NAME):
            server.start()
            client.sendto(packet("3E", "binary"), server.address)
            assert entered.wait(3), "native Windows UDP request not handled"
            client.close()
            release.set()
            worker = server._listener_threads[0]
            worker.join(3)
            if worker.is_alive() and not observed_socket_errors:
                pytest.skip("Windows runner suppressed ICMP Port Unreachable "
                            "to recvfrom; native 10054 not reproduced")
            assert not worker.is_alive()
            assert observed_socket_errors == [10054]
            report = server.get_listener_health()
            assert report["started"] is True
            assert report["healthy"] is False
            assert report["listeners"][0]["socket_open"] is True
            assert report["listeners"][0]["worker_alive"] is False

            warnings = [record for record in caplog.records
                        if record.name == LOG_NAME
                        and "UDP receive failed; listener worker stopped"
                        in record.getMessage()]
            assert len(warnings) == 1
            assert "10054" in warnings[0].getMessage()

            server.stop()
            assert server.get_listener_health() == EMPTY
            server._udp_loop = original_loop
            server.start()
            assert server.get_listener_health()["healthy"] is True
            _udp_read(server, 0)
    finally:
        release.set()
        client.close()
        server.stop()
