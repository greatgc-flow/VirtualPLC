"""Integration contract for UDP terminal warning + listener health (#13).

Run only on local loopback. This branch combines source proposals #58/#60
after tests-first RED; neither original PR nor main is merged.
No real PLC, external network, auto-restart or Windows socket policy change.
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
    """Error originates in a real registered worker, not a standalone fake.

    Synthetic errno proves the cross-platform contract; it is NOT native
    Windows ICMP proof. The actual TCP sibling must stay healthy.
    """
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

            # Reinvoking start alone does not recreate registered sockets.
            old_endpoint = server._listener
            server.start()
            assert server._listener is old_endpoint
            assert server.get_listener_health()["healthy"] is False

            # Explicit recovery closes/rebinds the pack, with new port-0
            # addresses; remove the scripted fault for the new worker.
            server.stop()
            assert server.get_listener_health() == EMPTY
            server._udp_loop = original_loop
            server.start()
            assert server.get_listener_health()["healthy"] is True
            _udp_read(server, index)
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


def test_shutdown_during_callback_health_does_not_deadlock(caplog):
    """End-to-end hook/stop race, including the eventual no-warning outcome."""
    entered = threading.Event()
    resume = threading.Event()
    observed = []

    def hook(response):
        entered.set()
        assert resume.wait(4), "test gate was not released"
        observed.append(server.get_listener_health())
        return response

    server = Server(listeners=[("udp", 0)], response_hook=hook)
    stopper = None
    try:
        with caplog.at_level(logging.WARNING, logger=LOG_NAME):
            server.start()
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.sendto(packet("3E", "binary"), server.address)
            assert entered.wait(3), "UDP hook never entered"
            stopper = threading.Thread(target=server.stop, daemon=True)
            stopper.start()
            assert server._stopping.wait(3), "shutdown flag not set"
            resume.set()
            stopper.join(3)
            assert not stopper.is_alive(), "stop->join->health lock inversion"
            assert observed == [EMPTY]
            assert server.get_listener_health() == EMPTY
            assert not any("UDP receive failed" in r.getMessage()
                           for r in caplog.records if r.name == LOG_NAME)
    finally:
        resume.set()
        if stopper is None:
            server.stop()


@pytest.mark.skipif(sys.platform != "win32",
                    reason="native WSAECONNRESET requires Windows Winsock")
def test_native_windows_10054_is_logged_unhealthy_then_recoverable(caplog):
    """Genuine local Windows ICMP after reply to closed UDP client port.

    Not a synthetic OSError; the wrapper forwards a REGISTERED real
    socket to the normal server worker and observes actual recvfrom.
    """
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
            client.close()  # real closed local source port
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
