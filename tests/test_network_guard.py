"""Default-local network safety and bounded client resources (#7)."""

import socket
import time

import pytest

from test_m1_server_raw import device_data, exchange, request
from virtual_plc import Server
from virtual_plc.__main__ import main


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.0.2.11", "", "example.com"])
def test_non_loopback_is_rejected_before_bind(host):
    with pytest.raises(ValueError, match="allow_nonlocal"):
        Server(host=host, port=0)


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "::1", "localhost"])
def test_loopback_hosts_remain_valid(host):
    assert Server(host=host).address[0] == host


@pytest.mark.parametrize("kwargs", [
    {"host": "0.0.0.0", "allow_nonlocal": True},
    {"host": "::", "allow_nonlocal": True},
])
def test_external_override_requires_explicit_timeout(kwargs):
    with pytest.raises(ValueError, match="idle_timeout"):
        Server(**kwargs)


def test_external_override_is_explicit_and_does_not_bind_during_construction():
    server = Server(host="0.0.0.0", allow_nonlocal=True, idle_timeout=30, max_clients=2)
    assert server._listener is None
    assert server._max_clients == 2


@pytest.mark.parametrize("value", [0, -1, True, False, 0.5, None, "5"])
def test_invalid_max_clients_is_rejected(value):
    with pytest.raises(ValueError, match="max_clients"):
        Server(max_clients=value)


def test_invalid_nonlocal_flag_type_is_rejected():
    with pytest.raises(ValueError, match="allow_nonlocal"):
        Server(allow_nonlocal=1)


def test_cli_refuses_external_bind_by_default(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--host", "0.0.0.0", "--port", "0"])
    assert exc.value.code == 2
    assert "--allow-nonlocal" in capsys.readouterr().err


def test_connection_limit_refuses_extra_client_but_preserves_existing_client():
    with Server(port=0, max_clients=1, idle_timeout=3) as server:
        with socket.create_connection(server.address, timeout=2) as first:
            first.settimeout(2)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                with server._clients_lock:
                    count = len(server._clients)
                if count == 1:
                    break
                time.sleep(0.005)
            assert count == 1
            with socket.create_connection(server.address, timeout=2) as extra:
                extra.settimeout(2)
                try:
                    assert extra.recv(1) == b""
                except ConnectionResetError:
                    pass  # Windows may report an abortive close instead of EOF.
            assert exchange(first, request(data=device_data())) == (0, b"\x00\x00")
