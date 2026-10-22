"""Public defaults, CLI configuration and connection failure isolation."""

import socket
import threading
from types import SimpleNamespace

import pytest

from test_m1_server_raw import device_data, exchange, request


def test_default_connections_have_no_idle_timeout(server_factory):
    from virtual_plc.server import Server
    import inspect

    assert inspect.signature(Server).parameters["idle_timeout"].default is None
    server = server_factory()
    with socket.create_connection(server.address, timeout=1) as connection:
        assert exchange(connection, request(data=device_data())) == (0, b"\x00\x00")
        with server._clients_lock:
            assert all(sock.gettimeout() is None for sock in server._clients)


def test_stop_joins_worker_with_buffered_partial_frame(server_factory):
    server = server_factory()
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(b"\x50")
        stopper = threading.Thread(target=server.stop, daemon=True)
        stopper.start()
        try:
            stopper.join(timeout=1)
            assert not stopper.is_alive()
        finally:
            connection.close()
            stopper.join(timeout=1)


def test_stop_closes_socket_before_joining_worker():
    from virtual_plc.server import Server

    closed = threading.Event()
    class Socket:
        def shutdown(self, how):
            pass
        def close(self):
            closed.set()
    worker = threading.Thread(target=closed.wait, daemon=True)
    server = Server()
    server._acceptor = SimpleNamespace(join=lambda: None)
    server._listener = SimpleNamespace(close=lambda: None)
    server._clients = {Socket(): worker}
    worker.start()
    stopper = threading.Thread(target=server.stop, daemon=True)
    stopper.start()
    try:
        assert closed.wait(0.5), "close must precede the worker join"
    finally:
        closed.set()
        stopper.join(timeout=1)
        worker.join(timeout=1)


@pytest.mark.parametrize("where", ["handler", "hook"])
@pytest.mark.parametrize("error_type", [RuntimeError, ValueError, OSError])
def test_unexpected_worker_error_is_logged_and_isolated(server_factory, monkeypatch, capsys, where, error_type):
    from virtual_plc import server as module

    def broken(*args):
        raise error_type("unexpected test failure")

    server = server_factory(response_hook=broken if where == "hook" else None)
    with monkeypatch.context() as patch:
        if where == "handler":
            patch.setattr(module, "dispatch", broken)
        with socket.create_connection(server.address, timeout=1) as connection:
            connection.sendall(request(data=device_data()))
            assert connection.recv(1) == b""
    server._hook = None
    with socket.create_connection(server.address, timeout=1) as connection:
        assert exchange(connection, request(data=device_data())) == (0, b"\x00\x00")
    log = capsys.readouterr().err
    assert error_type.__name__ in log and "unexpected test failure" in log


@pytest.mark.parametrize("host", ["127.0.0.1", "0.0.0.0"])
def test_cli_configuration_and_stderr_banner(monkeypatch, capsys, host):
    from virtual_plc import __main__ as cli

    seen = {}
    class FakeServer:
        def __init__(self, host, port, **options):
            self.address = (host, 12345)
            seen.update(options)
        def start(self):
            pass
        def stop(self):
            seen["stopped"] = True
    def interrupt():
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, "Server", FakeServer)
    monkeypatch.setattr(cli.threading, "Event", lambda: SimpleNamespace(wait=interrupt))
    cli.main(["--host", host, "--port", "0", "--profile", "iQ-R", "--password", "abcdef",
              "--initial-state", "STOP", "--max-points", "128", "--idle-timeout", "0.05"])
    assert seen == dict(profile="iQ-R", password="abcdef", initial_state="STOP", max_points=128,
                        idle_timeout=0.05, fault_plan=None, ascii_dword_order="swapped", stopped=True)
    output = capsys.readouterr()
    assert output.out == ""
    assert len(output.err.splitlines()) == 1
    assert f"{host}:12345" in output.err and "iQ-R" in output.err
    assert ("localhost-only" in output.err) == (host != "127.0.0.1")
