"""Mixed UDP listener failure with opt-in metrics and Health (#13).

Characterization only: one real registered UDP worker receives a scripted
terminal OSError while another UDP worker continues real loopback I/O.
No nonloopback traffic, PLC equipment, retries or new runtime behavior.
"""
import logging
import socket
import threading

from test_m3_m4_raw import packet
from virtual_plc import Server
from virtual_plc.codec import decode_request, encode_response


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
        with caplog.at_level(logging.WARNING, logger="virtual_plc.server"):
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
            assert [entry["healthy"] for entry in health["listeners"]] == [
                False, True,
            ]
            assert [entry["socket_open"] for entry in health["listeners"]] == [
                True, True,
            ]
            assert [entry["worker_alive"] for entry in health["listeners"]] == [
                False, True,
            ]
            healthy_read(1)  # real response on the surviving independent port
            assert server.get_udp_metrics() == {
                "received": 1,
                "rejected": 0,
                "sent": 1,
                "fault_dropped": 0,
                "send_errors": 0,
            }
            warnings = [
                item for item in caplog.records
                if item.name == "virtual_plc.server"
                and "UDP receive failed; listener worker stopped"
                    in item.getMessage()
            ]
            assert len(warnings) == 1
            assert "10054" in warnings[0].getMessage()

            # start() is not implicit repair while stale sockets registered.
            server.start()
            assert server.get_listener_health()["healthy"] is False

            server.stop()
            assert server.get_listener_health() == {
                "started": False, "healthy": False, "listeners": [],
            }
            server._udp_loop = original_loop
            server.start()
            assert server.get_listener_health()["healthy"] is True
            healthy_read(0)
            healthy_read(1)
            assert server.get_udp_metrics() == {
                "received": 3,
                "rejected": 0,
                "sent": 3,
                "fault_dropped": 0,
                "send_errors": 0,
            }
    finally:
        release.set()
        server.stop()
