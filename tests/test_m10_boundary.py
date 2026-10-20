"""M10: independent 3E TCP boundary observations (not vendor certification)."""
from contextlib import contextmanager
import socket
import struct
import threading

import pytest

from suite.support.wire import request, transact, assert_success, assert_protocol_error
from virtual_plc.server import Server


@contextmanager
def isolated_server():
    with Server(('127.0.0.1', 0)) as server:
        worker = threading.Thread(target=server.serve_forever,
                                  kwargs={'poll_interval': 0.01}, daemon=True)
        worker.start()
        try:
            yield server
        finally:
            server.shutdown()
            worker.join(timeout=3)
            assert not worker.is_alive()


def exchange(port, **kw):
    with socket.create_connection(('127.0.0.1', port), timeout=2) as conn:
        conn.settimeout(2)
        return transact(conn, request(**kw))


def test_case_0089_last_valid_d_word(record_property):
    """Exactly D9999 is legal when the configured D capacity is 10000."""
    record_property('case_id', 'CASE-0089')
    with isolated_server() as server:
        port = server.server_address[1]
        assert_success(exchange(port, cmd=0x1401, head=9999,
                                payload=struct.pack('<H', 0xAA55)))
        assert_success(exchange(port, head=9999), struct.pack('<H', 0xAA55))
        assert server.memory.read_words(9999, 1) == [0xAA55]
        assert server.memory.read_words(9998, 1) == [0]


def test_case_0092_zero_address_d_and_m(record_property):
    """Address zero is not confused with absent/null addresses."""
    record_property('case_id', 'CASE-0092')
    with isolated_server() as server:
        port = server.server_address[1]
        assert_success(exchange(port, cmd=0x1401, head=0, points=1,
                                payload=struct.pack('<H', 0x1234)))
        assert_success(exchange(port, head=0, points=1), struct.pack('<H', 0x1234))
        assert_success(exchange(port, cmd=0x1401, head=0, device=0x90,
                                sub=1, points=1, payload=b'\x10'))
        assert_success(exchange(port, head=0, device=0x90, sub=1, points=1), b'\x10')
        assert server.memory.read_bits(0, 1) == [1]


def test_out_of_range_atomicity_and_error_shape_unattested():
    """Observed simulator behavior only: manufacturer end-code remains OPEN."""
    with isolated_server() as server:
        port = server.server_address[1]
        before = server.memory.snapshot()
        result = exchange(port, cmd=0x1401, head=9999, points=2,
                          payload=struct.pack('<HH', 111, 222))
        assert_protocol_error(result, 0x1401, 0)
        assert server.memory.snapshot() == before
        assert_success(exchange(port, head=9999), b'\0\0')


def test_rejected_address_10000_never_wraps_to_d0():
    with isolated_server() as server:
        port = server.server_address[1]
        before = server.memory.snapshot()
        error = exchange(port, cmd=0x1401, head=10000,
                         payload=struct.pack('<H', 777))
        assert_protocol_error(error, 0x1401, 0)
        assert server.memory.snapshot() == before
        assert_success(exchange(port, head=0), b'\0\0')


@pytest.mark.parametrize('raw,signed', [(0xFFFF, -1), (0x8000, -32768),
                                      (0x7FFF, 32767), (0x0000, 0)])
def test_signed_word_codec_is_client_interpretation(raw, signed):
    """MC wire stores 16-bit patterns; a client may decode as signed int16."""
    with isolated_server() as server:
        port = server.server_address[1]
        payload = struct.pack('<H', raw)
        assert_success(exchange(port, cmd=0x1401, head=123,
                                payload=payload))
        res = exchange(port, head=123)
        assert_success(res, payload)
        assert struct.unpack('<h', res['data'])[0] == signed
