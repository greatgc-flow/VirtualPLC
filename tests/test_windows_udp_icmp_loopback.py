"""Windows UDP ICMP loopback evidence and explicit restart contract (#13).

No external addresses, raw ICMP sockets, firewall changes, device connections,
or production traffic. The OS-specific case sends one valid simulator reply
to a deliberately closed local UDP client port. A genuine Windows 10054
is evidence from Winsock, NOT an injected errno and NOT a PLC fidelity claim.

Windows loopback firewalls/providers can suppress ICMP: mark the native
probe SKIPPED with its reason rather than fabricate an observation.
"""

import socket
import sys
import threading

import pytest

from test_m3_m4_raw import packet
from virtual_plc import Server
from virtual_plc.codec import decode_request, encode_response


def _verify_manual_restart(server, frame):
    """An explicit stop/start restores an ordinary loopback UDP listener."""
    server.start()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(frame, server.address)
            response, peer = client.recvfrom(8192)
        assert peer[0] == "127.0.0.1"
        assert response == encode_response(decode_request(frame),
                                           data=b"\x00\x00")
    finally:
        server.stop()


def test_terminal_udp_receive_failure_allows_explicit_manual_restart():
    """Document that start alone is a no-op until stop releases endpoints."""
    server = Server(listeners=[("udp", 0)])
    attempts = []

    class TerminalReceiver:
        def recvfrom(self, size):
            assert size == 65535
            attempts.append(1)
            raise OSError(10054, "synthetic terminal recvfrom error")

    server._udp_loop(TerminalReceiver())
    assert attempts == [1]  # no retry loop
    assert server._listener is None
    _verify_manual_restart(server, packet("3E", "binary"))


@pytest.mark.skipif(sys.platform != "win32",
                    reason="real Winsock ICMP receipt requires native Windows")
def test_real_windows_loopback_icmp_10054_and_explicit_recovery():
    """Reproduce UDP Port Unreachable without faking a socket exception.

    1. A virtual PLC receives a valid local request and pauses its reply.
    2. That client's bound UDP port is actually closed before reply sendto.
    3. Windows can return ICMP Port Unreachable as recvfrom error 10054.
    4. Stop and restart the very same Server; verify a fresh real UDP reply.

    If a runner suppresses ICMP, skip with explicit evidence. Do not force
    OS-level SIO_UDP_CONNRESET flags or assume all Windows policies match.
    """
    frame = packet("3E", "binary")
    entered = threading.Event()
    release = threading.Event()
    failures = []

    def pause_response(response):
        entered.set()
        assert release.wait(4), "response gate was not released"
        return response

    server = Server(listeners=[("udp", 0)], response_hook=pause_response)
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener.bind(("127.0.0.1", 0))
    listener.settimeout(0.05)
    target = listener.getsockname()

    class ObserveRealSocket:
        def recvfrom(self, size):
            try:
                return listener.recvfrom(size)
            except socket.timeout:
                raise
            except OSError as error:
                failures.append(getattr(error, "winerror", None)
                                or error.errno)
                raise

        def sendto(self, data, peer):
            return listener.sendto(data, peer)

    worker = threading.Thread(target=server._udp_loop,
                              args=(ObserveRealSocket(),), daemon=True)
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind(("127.0.0.1", 0))
    try:
        worker.start()
        client.sendto(frame, target)
        assert entered.wait(3), "real UDP request never reached response hook"
        # Port Unreachable is produced by the host's real UDP/IP stack.
        client.close()
        release.set()
        worker.join(2.5)
    finally:
        release.set()
        client.close()
        server._stopping.set()
        listener.close()
        worker.join(3)

    assert not worker.is_alive(), "UDP worker did not stop after explicit shutdown"
    # Even an ICMP-suppressed host must preserve explicit manual recovery.
    _verify_manual_restart(server, frame)

    if not failures:
        pytest.skip("Windows runner did not deliver UDP ICMP Port Unreachable "
                    "to recvfrom within the bounded probe window; "
                    "SIO_UDP_CONNRESET/host policy may affect observation")
    assert failures == [10054], (
        "Unexpected native Windows UDP recvfrom failure, not 10054: "
        + repr(failures))


def test_dead_udp_worker_does_not_rebind_until_explicit_stop():
    """A dead worker is not repaired by another start() on a bound Server.

    An OS-level socket failure is simulated by closing a real loopback
    socket while its worker is polling. The public recovery operation
    is an explicit stop() followed by start(); never create a second
    worker just because start() was called twice.
    """
    server = Server(listeners=[("udp", 0)])
    try:
        server.start()
        stale_socket = server._listener
        stale_worker = server._listener_threads[0]
        stale_socket.close()
        stale_worker.join(3)
        assert not stale_worker.is_alive(), "closed UDP socket worker still active"
        server.start()  # no-op while Server still owns the old listener
        assert server._listener is stale_socket
        assert server._listener_threads == [stale_worker]
        server.stop()
        _verify_manual_restart(server, packet("3E", "binary"))
    finally:
        server.stop()
