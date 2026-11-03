"""Terminal UDP recvfrom diagnostics for local-only simulator (#13).

A Windows UDP recvfrom may surface WSAECONNRESET/10054 after an ICMP Port
Unreachable on an earlier send. This does NOT establish a safe recovery
strategy: document why the worker terminates instead of busy retrying.

Scripted listeners make the failure deterministic on every CI runner, and
never contact a real PLC or non-loopback network.
"""

import logging
import socket

import pytest

from virtual_plc import Server


@pytest.mark.parametrize("error_code", [10054, 10038])
def test_unexpected_udp_receive_error_is_reported_once_and_worker_stops(
        caplog, error_code):
    """Terminal receive errors must not silently strand a dead UDP worker."""
    server = Server(listeners=[("udp", 0)])
    seen = []

    class BrokenListener:
        def recvfrom(self, size):
            assert size == 65535
            seen.append("recvfrom")
            raise OSError(error_code, "synthetic Windows receive failure")

        def sendto(self, *_):
            raise AssertionError("must not send after recvfrom failure")

    with caplog.at_level(logging.WARNING, logger="virtual_plc.server"):
        server._udp_loop(BrokenListener())

    assert seen == ["recvfrom"]  # no unbounded retry on a possibly unusable socket
    assert server.memory.read_words("D", 0, 1) == [0]
    matching = [record for record in caplog.records
                if record.name == "virtual_plc.server"
                and "UDP receive failed; listener worker stopped" in record.message]
    assert len(matching) == 1
    assert str(error_code) in matching[0].getMessage()


def test_udp_receive_error_after_orderly_shutdown_has_no_spurious_warning(caplog):
    """stop() closes the socket; its receive error is expected, not a fault."""
    server = Server(listeners=[("udp", 0)])

    class StoppingListener:
        def recvfrom(self, size):
            assert size == 65535
            server._stopping.set()
            raise OSError(10038, "synthetic closed socket")

    with caplog.at_level(logging.WARNING, logger="virtual_plc.server"):
        server._udp_loop(StoppingListener())
    assert not any(record.name == "virtual_plc.server"
                   and "UDP receive failed" in record.getMessage()
                   for record in caplog.records)


def test_udp_receive_timeout_is_normal_polling_not_terminal_warning(caplog):
    """Normal timeout poll does not flood logs or dispatch any command."""
    server = Server(listeners=[("udp", 0)])
    calls = []

    class TimedListener:
        def recvfrom(self, size):
            assert size == 65535
            calls.append("poll")
            if len(calls) == 1:
                raise socket.timeout("normal polling")
            server._stopping.set()
            raise OSError(10038, "simulated stop")

    with caplog.at_level(logging.WARNING, logger="virtual_plc.server"):
        server._udp_loop(TimedListener())
    assert len(calls) == 2
    assert not any(record.name == "virtual_plc.server"
                   and "UDP receive failed" in record.getMessage()
                   for record in caplog.records)
