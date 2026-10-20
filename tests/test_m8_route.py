"""M8 TDD: route support is opt-in and never forwards traffic to a PLC."""
import socket
import threading
from contextlib import contextmanager

import pytest

from virtual_plc.server import DEFAULT_ROUTE, Server
from virtual_plc.config import validate_options
from suite.support.wire import request, recv_response

OTHER_ROUTE = bytes.fromhex('02 FF FF 03 00')

@contextmanager
def run_server(**kw):
    with Server(('127.0.0.1', 0), **kw) as server:
        worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        worker.start()
        try:
            yield server
        finally:
            server.shutdown()
            worker.join(timeout=3)
            assert not worker.is_alive()


def exchange(port, route, *, expect_response=True):
    with socket.create_connection(('127.0.0.1', port), timeout=2) as sock:
        sock.settimeout(2)
        sock.sendall(request(route=route))
        if expect_response:
            return recv_response(sock)
        try:
            assert sock.recv(1) == b''
        except ConnectionResetError:
            pass


def test_case_0121_nondefault_explicit_route(record_property):
    record_property('case_id', 'CASE-0121')
    # A simulated route identifier never triggers upstream connection.
    with run_server(allowed_routes=[DEFAULT_ROUTE, OTHER_ROUTE]) as server:
        for route in (DEFAULT_ROUTE, OTHER_ROUTE):
            reply = exchange(server.server_address[1], route)
            assert reply['endcode'] == 0
            assert reply['route'] == route
            assert reply['data'] == b'\0\0'


def test_unknown_route_rejected_by_default_and_opt_in():
    with run_server() as server:
        exchange(server.server_address[1], OTHER_ROUTE, expect_response=False)
    with run_server(allowed_routes=[DEFAULT_ROUTE, OTHER_ROUTE]) as server:
        exchange(server.server_address[1], bytes.fromhex('03 FF FF 03 00'), expect_response=False)


@pytest.mark.parametrize('routes', [[], [OTHER_ROUTE], [DEFAULT_ROUTE, DEFAULT_ROUTE],
    [DEFAULT_ROUTE, b'\0'], ['00FFFF0300'], [DEFAULT_ROUTE, bytes.fromhex('FF FF FF FF FF')],
    [DEFAULT_ROUTE] * 17])
def test_bad_route_table_is_rejected(routes):
    with pytest.raises((ValueError, TypeError)):
        Server(('127.0.0.1', 0), allowed_routes=routes)


def test_nondefault_route_via_config():
    config = validate_options({'routes': ['00FFFF0300', '02FFFF0300']})
    assert config['routes'] == ['00FFFF0300', '02FFFF0300']
    with run_server(allowed_routes=[bytes.fromhex(x) for x in config['routes']]) as server:
        assert exchange(server.server_address[1], OTHER_ROUTE)['route'] == OTHER_ROUTE


@pytest.mark.parametrize('routes', [None, [], ['00FFFF0300', '00FFFF0300'],
    ['02FFFF0300'], ['ABCDEF'], [123], ['ZZFFFF0300'],
    ['00FFFF0300', 'FFFFFFFFFF'], ['00FFFF0300'] * 17])
def test_config_route_rejects_bad_table(routes):
    if routes is None:
        assert validate_options({})['routes'] == ['00FFFF0300']
    else:
        with pytest.raises(ValueError):
            validate_options({'routes': routes})
