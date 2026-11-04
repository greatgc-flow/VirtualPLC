"""Cross-PR tests-first contract: #57 metrics + #61 terminal WARNING / Health.

Use loopback and registered UDP workers; never a physical or external PLC.
These tests intentionally run RED on PR61 until metrics is composed safely.
"""
import logging
import socket
import threading

from test_m3_m4_raw import packet
from virtual_plc import Server
from virtual_plc.codec import decode_request, encode_response


EMPTY_METRICS = {
    "received": 0, "rejected": 0, "sent": 0,
    "fault_dropped": 0, "send_errors": 0,
}


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
        with caplog.at_level(logging.WARNING, logger="virtual_plc.server"):
            server.start()
            worker = server._listener_threads[0]
            worker.join(3)
        assert not worker.is_alive()
        assert operations == ["receive", "send", "receive"]
        warnings = [r for r in caplog.records
                    if r.name == "virtual_plc.server"
                    and "UDP receive failed; listener worker stopped" in r.getMessage()]
        assert len(warnings) == 1
        assert "10054" in warnings[0].getMessage()
        health = server.get_listener_health()
        assert health["started"] is True
        assert health["healthy"] is False
        assert health["listeners"][0]["socket_open"] is True
        assert health["listeners"][0]["worker_alive"] is False
        assert server.get_udp_metrics() == {**EMPTY_METRICS, "received": 1, "sent": 1}

        # No implicit rebind. Explicit restart restores a real loopback read.
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


def test_metrics_and_nonblocking_health_from_hook_while_stop_joins():
    """No lock inversion and no sent/rejected counter for canceled response."""
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
        assert snapshots == [(
            {**EMPTY_METRICS, "received": 1},
            {"started": False, "healthy": False, "listeners": []}
        )]
        assert server.get_udp_metrics() == {**EMPTY_METRICS, "received": 1}
        assert server.get_listener_health() == {
            "started": False, "healthy": False, "listeners": []
        }
    finally:
        release.set()
        if stopper is None:
            server.stop()
