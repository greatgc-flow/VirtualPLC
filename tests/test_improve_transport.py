"""Transport resilience (improvement ballot B2: I7a, I7b, D3, F04). Loopback only."""

import errno
import logging
import socket

import pytest

from test_ipv6_loopback_transport import ipv6_loopback  # noqa: F401 (fixture)
from test_m3_m4_raw import packet
from test_udp_client_example import example
from virtual_plc import Memory, Server
from virtual_plc import server as server_module
from virtual_plc.codec import decode_request, encode_response

LOG_NAME = "virtual_plc.server"


def test_udp_receive_reset_is_counted_and_the_worker_keeps_serving(caplog):
    """I7a: ConnectionResetError (Windows ICMP 10054) does not stop the UDP worker."""
    server = Server(listeners=[("udp", 0)], udp_metrics=True)
    original_loop = server._udp_loop
    resets = [2]

    def scripted(real_socket):
        class ResetTwiceThenReal:
            def recvfrom(self, length):
                if resets[0]:
                    resets[0] -= 1
                    raise ConnectionResetError(errno.ECONNRESET, "synthetic receive reset")
                return real_socket.recvfrom(length)

            def sendto(self, data, peer):
                return real_socket.sendto(data, peer)

        return original_loop(ResetTwiceThenReal())

    server._udp_loop = scripted
    frame = packet("3E", "binary")
    with caplog.at_level(logging.WARNING, logger=LOG_NAME):
        with server:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.settimeout(2)
                client.sendto(frame, server.address)
                assert client.recvfrom(8192)[0] == encode_response(decode_request(frame), data=b"\x00\x00")
            assert server.get_listener_health()["healthy"] is True
    metrics = server.get_udp_metrics()
    assert metrics["receive_resets"] == 2
    assert (metrics["received"], metrics["rejected"], metrics["sent"]) == (1, 0, 1)
    warnings = [r for r in caplog.records if r.name == LOG_NAME and "reset" in r.getMessage()]
    assert len(warnings) == 1, "repeated resets must not flood warnings"


@pytest.mark.parametrize("error", [
    ConnectionResetError(errno.ECONNRESET, "synthetic accept reset"),
    ConnectionAbortedError(errno.ECONNABORTED, "synthetic accept abort"),
])
def test_tcp_accept_reset_or_abort_keeps_accepting(error):
    """I7b: a transient accept() failure skips that peer only."""
    server = Server()
    original_loop = server._accept_loop

    def scripted(real_socket):
        class FailOnceThenReal:
            failed = False

            def accept(self):
                if not FailOnceThenReal.failed:
                    FailOnceThenReal.failed = True
                    raise error
                return real_socket.accept()

        return original_loop(FailOnceThenReal())

    server._accept_loop = scripted
    with server:
        with socket.create_connection(server.address, timeout=2) as client:
            client.settimeout(2)
            frame = packet("3E", "binary")
            client.sendall(frame)
            assert client.recv(64) == encode_response(decode_request(frame), data=b"\x00\x00")
        assert server.get_listener_health()["healthy"] is True


def test_tcp_terminal_accept_error_logs_one_warning(caplog):
    """I7b: a terminal accept() failure outside shutdown is logged, like UDP."""
    server = Server()
    original_loop = server._accept_loop

    def scripted(real_socket):
        class Terminal:
            def accept(self):
                raise OSError(errno.EBADF, "synthetic terminal accept failure")

        return original_loop(Terminal())

    server._accept_loop = scripted
    with caplog.at_level(logging.WARNING, logger=LOG_NAME):
        with server:
            # Join the worker itself: an Event set inside the loop's thread
            # fires before Thread.is_alive() turns False, so health could
            # still see a live worker (observed ~4% in repeated runs).
            worker = server._listener_threads[0]
            worker.join(3)
            assert not worker.is_alive()
            assert server.get_listener_health()["healthy"] is False
    warnings = [r for r in caplog.records
                if r.name == LOG_NAME and "TCP accept failed" in r.getMessage()]
    assert len(warnings) == 1


@pytest.mark.parametrize("transport", ["tcp", "udp"])
def test_bound_address_must_be_loopback_unless_allowed(monkeypatch, transport):
    """D3: a name like 'localhost' that resolves off-loopback is closed before workers start."""
    created = []

    class OffLoopback:
        def __init__(self, real):
            self.real = real
            created.append(self)

        def getsockname(self):
            return ("192.0.2.10", 5000)

        def __getattr__(self, name):
            return getattr(self.real, name)

    real_create_server = socket.create_server
    real_socket = socket.socket
    if transport == "tcp":
        monkeypatch.setattr(server_module.socket, "create_server",
                            lambda address, family: OffLoopback(real_create_server(("127.0.0.1", 0), family=family)))
    else:
        monkeypatch.setattr(server_module.socket, "socket",
                            lambda *args: OffLoopback(real_socket(*args)))
    server = Server(host="localhost", listeners=[(transport, 0)])
    with pytest.raises(OSError, match="loopback"):
        server.start()
    assert created and all(item.real.fileno() == -1 for item in created)
    assert server._listener is None and server._listener_threads == []


def test_example_reads_d0_over_ipv6_loopback(ipv6_loopback):  # noqa: F811
    """F04: the standalone UDP example accepts the IPv6 loopback literal."""
    memory = Memory()
    memory.write_words("D", 0, [0x0BEE])
    with Server(host="::1", listeners=[("udp", 0)], memory=memory) as plc:
        assert example().read_d0(plc.address[1], host="::1") == 0x0BEE


@pytest.mark.parametrize("host", ["192.0.2.1", "localhost", "::", "0.0.0.0"])
def test_example_still_refuses_non_literal_or_non_loopback(host):
    with pytest.raises(ValueError):
        example().read_d0(5000, host=host)
