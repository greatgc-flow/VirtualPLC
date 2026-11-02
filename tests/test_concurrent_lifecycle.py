"""Deterministic multi-listener lifecycle races (#13).

A socket creation barrier holds start() mid-bind while an independent thread
calls stop() or start(). No sleep-based race assumption is needed to control
the first bind; all sockets are localhost/ephemeral.
"""

import socket
import threading

from test_m1_server_raw import device_data, exchange, request
from virtual_plc import Server
from virtual_plc import server as server_module


def _run(action, errors, completed=None):
    try:
        action()
    except BaseException as error:
        errors.append(error)
    finally:
        if completed is not None:
            completed.set()


def test_stop_during_tcp_udp_start_waits_and_closes_all_endpoints(monkeypatch):
    server = Server(listeners=[("tcp", 0), ("udp", 0)])
    original_create_server = socket.create_server
    first_bound = threading.Event()
    release_first_bind = threading.Event()
    stop_entered = threading.Event()
    stop_done = threading.Event()
    created = []
    errors = []

    def held_first_bind(*args, **kwargs):
        listener = original_create_server(*args, **kwargs)
        created.append(listener)
        first_bound.set()
        if not release_first_bind.wait(5):
            raise RuntimeError("test bind was never released")
        return listener

    def stop_action():
        stop_entered.set()
        server.stop()

    start_thread = threading.Thread(target=_run, args=(server.start, errors))
    stop_thread = threading.Thread(target=_run,
                                   args=(stop_action, errors, stop_done))
    try:
        with monkeypatch.context() as patch:
            patch.setattr(server_module.socket, "create_server", held_first_bind)
            start_thread.start()
            assert first_bound.wait(3), "start must reach a bound TCP endpoint"
            stop_thread.start()
            assert stop_entered.wait(3)
            # While start is held inside create_server, stop must not report
            # success before it has closed the in-flight listener pack.
            assert not stop_done.wait(0.2), "stop returned before start finished binding"
            release_first_bind.set()
            start_thread.join(4)
            stop_thread.join(4)
        assert not start_thread.is_alive() and not stop_thread.is_alive()
        assert errors == []
        assert created[0].fileno() == -1
        assert server._listener is None
        assert server._listeners == []
        assert server._listener_threads == []
        assert server._stopping.is_set()
    finally:
        release_first_bind.set()
        if start_thread.ident is not None:
            start_thread.join(4)
        if stop_thread.ident is not None:
            stop_thread.join(4)
        server.stop()
        for listener in created:
            listener.close()


def test_overlapping_tcp_udp_starts_do_not_double_bind_or_leak(monkeypatch):
    server = Server(listeners=[("tcp", 0), ("udp", 0)])
    original_create_server = socket.create_server
    first_bound = threading.Event()
    release_first_bind = threading.Event()
    second_entered = threading.Event()
    second_done = threading.Event()
    created = []
    errors = []

    def held_first_bind(*args, **kwargs):
        listener = original_create_server(*args, **kwargs)
        created.append(listener)
        if len(created) == 1:
            first_bound.set()
            if not release_first_bind.wait(5):
                raise RuntimeError("test bind was never released")
        return listener

    def second_start():
        second_entered.set()
        server.start()

    first_thread = threading.Thread(target=_run, args=(server.start, errors))
    second_thread = threading.Thread(target=_run,
                                     args=(second_start, errors, second_done))
    try:
        with monkeypatch.context() as patch:
            patch.setattr(server_module.socket, "create_server", held_first_bind)
            first_thread.start()
            assert first_bound.wait(3), "first start must bind TCP"
            second_thread.start()
            assert second_entered.wait(3)
            assert not second_done.wait(0.2), "second start bound before first completed"
            release_first_bind.set()
            first_thread.join(4)
            second_thread.join(4)
        assert not first_thread.is_alive() and not second_thread.is_alive()
        assert errors == []
        assert len(created) == 1, "concurrent start must create one TCP socket"
        assert [transport for transport, _, _ in server.addresses] == ["tcp", "udp"]
        with socket.create_connection(server.address, timeout=2) as client:
            assert exchange(client, request(data=device_data())) == (
                0, b"\x00\x00")
    finally:
        release_first_bind.set()
        if first_thread.ident is not None:
            first_thread.join(4)
        if second_thread.ident is not None:
            second_thread.join(4)
        server.stop()
        for listener in created:
            listener.close()
    assert created[0].fileno() == -1
    assert server._listener is None
    assert server._listeners == []
    assert server._listener_threads == []
