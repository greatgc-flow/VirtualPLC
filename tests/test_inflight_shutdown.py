"""Deterministic in-flight request vs stop/restart regressions (#13).

These tests use only ephemeral loopback endpoints and event-controlled
request handlers. A stop cannot undo an already executing dispatch, but
it must not begin the next buffered TCP request after shutdown starts.
"""

import socket
import threading

import pytest

from test_m1_server_raw import device_data, exchange, request
from test_m3_m4_raw import packet
from virtual_plc import Server
from virtual_plc import server as server_module
from virtual_plc.codec import decode_request, encode_response


def test_stop_discards_queued_tcp_write_after_inflight_read(monkeypatch):
    """TCP pipelined requests must not dispatch a later write after stop.

    A scripted recv supplies both frames in one read, independent of TCP
    segmentation, while real localhost TCP/UDP listeners exercise shutdown.
    """
    first_dispatch = threading.Event()
    release_first_dispatch = threading.Event()
    stopped = threading.Event()
    errors = []
    received_responses = []
    first_read = request(data=device_data())
    queued_write = request(0x1401, data=device_data(payload=b"\x34\x12"))

    class ScriptedConnection:
        def __init__(self):
            self.read_once = False
            self.closed = False

        def recv(self, size):
            if not self.read_once:
                self.read_once = True
                return first_read + queued_write
            return b""

        def sendall(self, payload):
            received_responses.append(payload)

        def shutdown(self, how):
            pass

        def close(self):
            self.closed = True

    server = Server(listeners=[("tcp", 0), ("udp", 0)])
    connection = ScriptedConnection()
    original_dispatch = server_module.dispatch

    def block_first(decoded, memory, max_points, control):
        if decoded.command == 0x0401:
            first_dispatch.set()
            if not release_first_dispatch.wait(4):
                raise RuntimeError("read dispatch was not released")
        return original_dispatch(decoded, memory, max_points, control)

    def serve():
        try:
            server._serve_frames(connection, 17)
        except BaseException as error:
            errors.append(error)
        finally:
            # Mirror _serve's "with connection" lifecycle: an exited
            # worker closes its own socket even if stop has not snapped it.
            connection.close()
            with server._clients_lock:
                server._clients.pop(connection, None)

    def shutdown():
        try:
            server.stop()
        except BaseException as error:
            errors.append(error)
        finally:
            stopped.set()

    serving = threading.Thread(target=serve)
    stopping = threading.Thread(target=shutdown)
    try:
        server.start()
        with monkeypatch.context() as patch:
            patch.setattr(server_module, "dispatch", block_first)
            with server._clients_lock:
                server._clients[connection] = serving
            serving.start()
            assert first_dispatch.wait(3), "first TCP read must enter dispatch"
            stopping.start()
            assert server._stopping.wait(3), "stop must set shutdown flag"
            assert not stopped.wait(0.05), "stop must join the in-flight client"
            release_first_dispatch.set()
            serving.join(4)
            stopping.join(4)

        assert not serving.is_alive() and not stopping.is_alive()
        assert errors == []
        assert stopped.is_set()
        assert connection.closed
        assert server._listener is None
        assert server._listeners == []
        assert server._listener_threads == []
        with server._clients_lock:
            assert server._clients == {}
        # Only the in-flight read is allowed to finish. An already-buffered
        # TCP write must not mutate memory after stop was signaled.
        assert server.memory.read_words("D", 0, 1) == [0]

        # A fresh lifecycle still serves both TCP and UDP and uses one Memory.
        server.start()
        with socket.create_connection(server.address, timeout=2) as tcp:
            assert exchange(tcp, request(data=device_data())) == (0, b"\x00\x00")
        _, host, port = server.addresses[1]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(2)
            data = packet("3E", "binary")
            udp.sendto(data, (host, port))
            assert udp.recvfrom(8192)[0] == encode_response(
                decode_request(data), data=b"\x00\x00")
    finally:
        release_first_dispatch.set()
        if serving.ident is not None:
            serving.join(4)
        if stopping.ident is not None:
            stopping.join(4)
        server.stop()


def test_udp_inflight_response_not_sent_after_stop_and_restart():
    """An in-flight UDP response is suppressed once shutdown is requested."""
    hook_entered = threading.Event()
    release_hook = threading.Event()
    stopped = threading.Event()
    errors = []

    def held_hook(response):
        hook_entered.set()
        if not release_hook.wait(4):
            raise RuntimeError("UDP hook was not released")
        return response

    server = Server(listeners=[("tcp", 0), ("udp", 0)],
                    response_hook=held_hook)
    data = packet("4E", "binary", serial=0x2345)

    def shutdown():
        try:
            server.stop()
        except BaseException as error:
            errors.append(error)
        finally:
            stopped.set()

    stopping = threading.Thread(target=shutdown)
    try:
        server.start()
        _, host, port = server.addresses[1]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.sendto(data, (host, port))
            assert hook_entered.wait(3), "UDP packet must reach response hook"
            stopping.start()
            assert server._stopping.wait(3)
            assert not stopped.wait(0.05), "stop must join the UDP worker"
            release_hook.set()
            stopping.join(4)
            assert not stopping.is_alive()
            assert errors == []
            assert stopped.is_set()
            udp.settimeout(0.08)
            with pytest.raises(socket.timeout):
                udp.recvfrom(8192)
        assert server._listener_threads == []
        assert server._listeners == []
        server._hook = None
        server.start()
        _, new_host, new_port = server.addresses[1]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(2)
            udp.sendto(data, (new_host, new_port))
            assert udp.recvfrom(8192)[0] == encode_response(
                decode_request(data), data=b"\x00\x00")
    finally:
        release_hook.set()
        if stopping.ident is not None:
            stopping.join(4)
        server.stop()
