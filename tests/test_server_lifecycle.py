"""Tests for Server lifecycle (restart, double stop, listener closure) and range validation."""

import socket

import pymcprotocol
import pytest

from virtual_plc.memory import Memory
from virtual_plc.server import Server


def test_server_restart_accepts_connections():
    server = Server("127.0.0.1", port=0)
    server.start()
    try:
        client = pymcprotocol.Type3E(plctype="Q")
        client.soc_timeout = 2
        client.connect(*server.address)
        assert client.batchread_wordunits("D0", 1) == [0]
        client.close()

        server.stop()
        server.start()

        client2 = pymcprotocol.Type3E(plctype="Q")
        client2.soc_timeout = 2
        client2.connect(*server.address)
        assert client2.batchread_wordunits("D0", 1) == [0]
        client2.close()
    finally:
        server.stop()


def test_server_second_start_without_stop_does_not_leak_listener():
    server = Server("127.0.0.1", port=0)
    server.start()
    listener = server._listener
    try:
        try:
            server.start()
        except RuntimeError:
            pass
        assert server._listener is listener
    finally:
        server.stop()


def test_server_double_stop_is_safe():
    server = Server("127.0.0.1", port=0)
    server.start()
    server.stop()
    server.stop()

    unstarted = Server("127.0.0.1", port=0)
    unstarted.stop()
    unstarted.stop()


def test_server_stop_without_acceptor_closes_listener():
    server = Server("127.0.0.1", port=0)
    listener = socket.create_server(("127.0.0.1", 0))
    server._listener = listener
    assert server._acceptor is None
    server.stop()
    assert listener.fileno() == -1
    assert server._listener is None


@pytest.mark.parametrize("point", [True, False])
def test_latch_range_rejects_bool(point):
    with pytest.raises(ValueError, match="invalid latch range"):
        Server(latch_ranges={"D": [(point, 10)]})
    with pytest.raises(ValueError, match="invalid latch range"):
        Server(latch_ranges={"D": [(0, point)]})


def test_latch_range_rejects_int_subclass():
    class IntSubclass(int):
        pass

    with pytest.raises(ValueError, match="invalid latch range"):
        Server(latch_ranges={"D": [(IntSubclass(0), 10)]})
    with pytest.raises(ValueError, match="invalid latch range"):
        Server(latch_ranges={"D": [(0, IntSubclass(10))]})


@pytest.mark.parametrize("point", [True, False])
def test_memory_limit_rejects_bool(point):
    with pytest.raises(ValueError, match="invalid memory limit"):
        Memory(limits={"D": (point, 10)})
    with pytest.raises(ValueError, match="invalid memory limit"):
        Memory(limits={"D": (0, point)})
