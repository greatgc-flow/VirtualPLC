"""UDP receive/dispatch shutdown race regressions (#13).

Loopback-only. No external PLC, hardware claims or sleep-based timing to
induce a race: a fake datagram receiver and a real UDP listener blocked
inside protocol parsing control the exact shutdown boundary.
"""

import socket
import threading

import pytest

from test_m1_server_raw import device_data
from test_m3_m4_raw import packet
from test_slmp_1e import req as one_e_request
from virtual_plc import Server
from virtual_plc import server as server_module
from virtual_plc.codec import decode_request, encode_response


@pytest.mark.parametrize("slmp_1e,frame", [
    (False, packet("3E", "binary", 0x1401,
                   data=device_data(payload=b"\x34\x12"))),
    (False, packet("3E", "ascii", 0x1401,
                   data=b"D*00000000011234")),
    (False, packet("4E", "binary", 0x1401,
                   data=device_data(payload=b"\x34\x12"), serial=0x3344)),
    (False, packet("4E", "ascii", 0x1401,
                   data=b"D*00000000011234", serial=0x3344)),
    (True, one_e_request(3, head=0, count=1, payload=b"\x34\x12")),
], ids=["3e-binary", "3e-ascii", "4e-binary", "4e-ascii", "1e-binary"])
def test_udp_recv_returning_during_shutdown_does_not_dispatch_write(
        slmp_1e, frame):
    """Even a complete datagram from recvfrom may arrive after stop begins."""
    server = Server(slmp_1e=slmp_1e, listeners=[("udp", 0)])
    sent = []

    class InterruptedReceive:
        def __init__(self):
            self.receives = 0

        def recvfrom(self, size):
            self.receives += 1
            assert size == 65535
            server._stopping.set()
            return frame, ("127.0.0.1", 12345)

        def sendto(self, *args):
            sent.append(args)

    listener = InterruptedReceive()
    server._udp_loop(listener)
    assert listener.receives == 1
    assert server.memory.read_words("D", 0, 1) == [0]
    assert sent == []


@pytest.mark.parametrize("slmp_1e", [False, True], ids=["3e-4e", "1e"])
def test_udp_shutdown_during_parse_skips_write_then_restart_serves(
        monkeypatch, slmp_1e):
    """A datagram parsed during stop must not initiate a new dispatch.

    Uses a genuine loopback UDP worker. Pausing *before* the request lock
    means stop can begin before the write would otherwise execute.
    """
    entered = threading.Event()
    release = threading.Event()
    stopped = threading.Event()
    errors = []
    target_write = (one_e_request(3, head=0, count=1,
                                  payload=b"\x78\x56") if slmp_1e
                    else packet("4E", "binary", 0x1401,
                                data=device_data(payload=b"\x78\x56"),
                                serial=0x4A55))
    server = Server(slmp_1e=slmp_1e,
                    listeners=[("tcp", 0), ("udp", 0)])

    def pause_parser(value):
        entered.set()
        if not release.wait(4):
            raise RuntimeError("UDP parse barrier never released")
        return original_parser(value)

    def shutdown():
        try:
            server.stop()
        except BaseException as error:
            errors.append(error)
        finally:
            stopped.set()

    stopping = threading.Thread(target=shutdown)
    server.start()
    try:
        _, host, port = server.addresses[1]
        with monkeypatch.context() as patch:
            if slmp_1e:
                original_parser = server_module.frame_size_1e
                patch.setattr(server_module, "frame_size_1e", pause_parser)
            else:
                original_parser = server_module.decode_request
                patch.setattr(server_module, "decode_request", pause_parser)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.sendto(target_write, (host, port))
                assert entered.wait(3), "UDP worker did not reach parser"
                stopping.start()
                assert server._stopping.wait(3), "stop event not set"
                assert not stopped.wait(0.05), "stop must join parsing UDP worker"
                release.set()
                stopping.join(4)
                assert not stopping.is_alive()
                assert errors == []
                client.settimeout(0.06)
                with pytest.raises(socket.timeout):
                    client.recvfrom(8192)

        assert stopped.is_set()
        assert server.memory.read_words("D", 0, 1) == [0]
        assert server._listeners == [] and server._listener_threads == []

        server.start()
        _, new_host, new_port = server.addresses[1]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(target_write, (new_host, new_port))
            reply, source = client.recvfrom(8192)
        assert source[1] == new_port
        if not slmp_1e:
            assert reply == encode_response(decode_request(target_write))
        else:
            assert reply == b"\x83\x00"
        assert server.memory.read_words("D", 0, 1) == [0x5678]
    finally:
        release.set()
        if stopping.ident is not None:
            stopping.join(4)
        server.stop()
