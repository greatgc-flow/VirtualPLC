"""Multi-port shared PLC and UDP framing tests (transport extension)."""

import socket
import time

import pytest

from test_m1_server_raw import device_data, exchange, request
from test_m3_m4_raw import packet
from virtual_plc import Server
from virtual_plc.codec import decode_request, encode_response
from virtual_plc.faults import FaultPlan
from virtual_plc.__main__ import listener_spec, main


def endpoints(server):
    return {(transport, index): (host, port)
            for index, (transport, host, port) in enumerate(server.addresses)}


@pytest.mark.parametrize("bad", [
    [], [("tcp", 5000), ("tcp", 5000)], [("udp", 5000), ("udp", 5000)],
    [("sctp", 5000)], [("tcp", True)], [("udp", -1)], [("udp", 65536)],
    [("tcp", "5000")], ["tcp:5000"], [("tcp", 1, "extra")],
])
def test_listener_specs_fail_before_binding(bad):
    with pytest.raises(ValueError, match="listener"):
        Server(listeners=bad)


def test_legacy_server_uses_one_tcp_address_and_same_context():
    with Server(port=0) as server:
        assert server.addresses == [("tcp", *server.address)]
        assert server.address[1] > 0


def test_multiple_tcp_and_udp_bind_and_restart():
    server = Server(listeners=[("tcp", 0), ("tcp", 0), ("udp", 0)])
    try:
        server.start()
        assert [proto for proto, _, _ in server.addresses] == ["tcp", "tcp", "udp"]
        assert all(host == "127.0.0.1" and port > 0 for _, host, port in server.addresses)
        old = list(server.addresses)
        server.start()
        assert server.addresses == old
        server.stop()
        server.stop()
        server.start()
        assert len(server.addresses) == 3
    finally:
        server.stop()


@pytest.mark.parametrize("frame,wire", [("3E", "binary"), ("3E", "ascii"),
                                        ("4E", "binary"), ("4E", "ascii")])
def test_udp_frames_share_tcp_memory(frame, wire):
    with Server(listeners=[("tcp", 0), ("udp", 0)]) as server:
        _, tcp_host, tcp_port = server.addresses[0]
        _, udp_host, udp_port = server.addresses[1]
        payload = (b"D*00000000011234" if wire == "ascii"
                   else device_data(payload=b"\x34\x12"))
        write = packet(frame, wire, 0x1401, data=payload, serial=0x1204)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(2)
            udp.sendto(write, (udp_host, udp_port))
            reply, source = udp.recvfrom(8192)
            assert source[1] == udp_port
            assert reply == encode_response(decode_request(write))
            with socket.create_connection((tcp_host, tcp_port), timeout=2) as tcp:
                assert exchange(tcp, request(data=device_data())) == (0, b"\x34\x12")
                assert exchange(tcp, request(0x1401, data=device_data(payload=b"\x78\x56")))[0] == 0
            read = packet(frame, wire, serial=0x1234)
            udp.sendto(read, (udp_host, udp_port))
            reply, source = udp.recvfrom(8192)
            assert source[1] == udp_port
            assert reply == encode_response(decode_request(read), data=b"\x78\x56")


def test_udp_cpu_control_is_shared_across_tcp_and_udp():
    with Server(listeners=[("tcp", 0), ("udp", 0)]) as server:
        _, host, port = server.addresses[1]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(2)
            stop = packet("3E", "binary", command=0x1002, data=b"\x01\x00")
            udp.sendto(stop, (host, port))
            assert udp.recvfrom(8192)[0] == encode_response(decode_request(stop))
            assert server.state == "STOP"
            with socket.create_connection(server.address, timeout=2) as tcp:
                assert exchange(tcp, request(data=device_data(head=203, code=0xA9))) == (0, b"\x00\x00")
                assert exchange(tcp, request(0x1001, data=b"\x01\x00\x00\x00"))[0] == 0
            assert server.state == "RUN"


def test_malformed_and_combined_udp_packets_are_ignored_and_next_valid_responds():
    with Server(listeners=[("udp", 0)]) as server:
        assert server.addresses[0][0] == "udp"
        target = server.address
        good = packet("3E", "binary")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(0.04)
            for malformed in (b"invalid", good[:-1], good + good, b"X" * 9000):
                udp.sendto(malformed, target)
                with pytest.raises(socket.timeout):
                    udp.recvfrom(8192)
            udp.settimeout(2)
            udp.sendto(good, target)
            assert udp.recvfrom(8192)[0] == encode_response(decode_request(good), data=b"\x00\x00")


def test_two_tcp_ports_share_memory_and_enforce_global_client_limit():
    with Server(listeners=[("tcp", 0), ("tcp", 0)], max_clients=1) as server:
        first, second = server.addresses
        with socket.create_connection(first[1:], timeout=2) as connection:
            connection.settimeout(2)
            deadline = time.monotonic() + 2
            count = 0
            while time.monotonic() < deadline:
                with server._clients_lock:
                    count = len(server._clients)
                if count == 1:
                    break
                time.sleep(0.005)
            assert count == 1
            with socket.create_connection(second[1:], timeout=2) as other:
                other.settimeout(2)
                try:
                    assert other.recv(1) == b""
                except ConnectionResetError:
                    pass
            assert exchange(connection, request(data=device_data())) == (0, b"\x00\x00")
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with server._clients_lock:
                remaining = len(server._clients)
            if remaining == 0:
                break
            time.sleep(0.005)
        assert remaining == 0
        with socket.create_connection(second[1:], timeout=2) as after_close:
            assert exchange(after_close, request(data=device_data())) == (0, b"\x00\x00")


def test_partial_bind_failure_closes_every_created_socket():
    with socket.create_server(("127.0.0.1", 0)) as blocked:
        port = blocked.getsockname()[1]
        server = Server(listeners=[("tcp", 0), ("tcp", port)])
        with pytest.raises(OSError):
            server.start()
        assert not server._listeners and server._listener is None
        server.stop()


def test_udp_and_fault_plan_are_rejected_explicitly():
    with pytest.raises(ValueError, match="UDP.*fault"):
        Server(listeners=[("udp", 0)], fault_plan=FaultPlan([]))


@pytest.mark.parametrize("value,expected", [
    ("tcp:5000", ("tcp", 5000)), ("udp:0", ("udp", 0)),
    ("udp:5000", ("udp", 5000)),
])
def test_cli_listener_spec(value, expected):
    assert listener_spec(value) == expected


@pytest.mark.parametrize("value", ["tcp", "tcp:abc", "tcp:-1", "udp:65536", "http:5000",
                                   "tcp:1:2", "UDP:1", "tcp:"])
def test_cli_listener_spec_rejects_bad_values(value):
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        listener_spec(value)


def test_cli_multi_uses_one_server_and_reports_each_bound_port(monkeypatch, capsys):
    from virtual_plc import __main__ as cli
    from types import SimpleNamespace
    seen = []
    class DummyServer:
        def __init__(self, host, port, **options):
            seen.append((host, port, options))
            self.address = (host, 1111)
            self.addresses = [("tcp", host, 1111), ("udp", host, 2222)]
        def start(self):
            pass
        def stop(self):
            pass
    def interrupt(_):
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, "Server", DummyServer)
    monkeypatch.setattr(cli.threading, "Event", lambda: SimpleNamespace(wait=interrupt))
    assert main(["--listen", "tcp:0", "--listen", "udp:0"]) == 0
    assert seen[0][0:2] == ("127.0.0.1", 0)
    assert seen[0][2]["listeners"] == [("tcp", 0), ("udp", 0)]
    stderr = capsys.readouterr().err
    assert "tcp:127.0.0.1:1111" in stderr
    assert "udp:127.0.0.1:2222" in stderr
