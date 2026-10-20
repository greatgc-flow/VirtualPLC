"""M7 distinct P0 CASE-ID oracles; all network access is IPv4 loopback.

CASE-0068 uses an adversarial socket shim to make blocked send deterministic.
CASE-0126 tests real TCP buffer pressure and concurrent client responsiveness.
"""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import socket
import struct
import threading
import time
from types import SimpleNamespace
import pytest
from suite.support.wire import request
from virtual_plc.memory import Memory
from virtual_plc.server import Handler, Server, IDLE_TIMEOUT, DEFAULT_ROUTE
from virtual_plc.telemetry import Telemetry

ROOT = Path(__file__).resolve().parents[1]
CATALOG = {row['id']: row for line in (ROOT/'suite/catalog/test_cases.jsonl').read_text().splitlines()
           if (row := json.loads(line))}
IDS = ('CASE-0054', 'CASE-0068', 'CASE-0126')
assert all(CATALOG[x]['runner'] == 'runtime_adapter' and CATALOG[x]['phase'] == 'P0' for x in IDS)

@contextmanager
def server_scope(*, telemetry=None):
    with Server(('127.0.0.1', 0), telemetry=telemetry) as srv:
        th = threading.Thread(target=srv.serve_forever, kwargs={'poll_interval': 0.005}, daemon=True)
        th.start()
        try:
            yield srv
        finally:
            srv.shutdown()
            th.join(timeout=3)
            assert not th.is_alive()

def read_reply(sock):
    def exact(n):
        buf = bytearray()
        while len(buf) < n:
            block = sock.recv(n-len(buf))
            if not block:
                raise EOFError('server closed before valid reply')
            buf.extend(block)
        return bytes(buf)
    header = exact(9)
    return header+exact(int.from_bytes(header[7:9], 'little'))

def wait_for(predicate, seconds=4):
    end = time.monotonic()+seconds
    while time.monotonic() < end:
        if predicate(): return
        time.sleep(0.02)
    assert predicate(), 'expected bounded event did not occur'

class BlockedReceiverSocket:
    """Deterministic sendall TimeoutError, no reliance on platform buffers."""
    def __init__(self, packet):
        self.buffer = bytearray(packet)
        self.deadlines = []
        self.send_calls = 0
    def settimeout(self, timeout):
        self.deadlines.append(timeout)
    def recv(self, count):
        block = bytes(self.buffer[:count])
        del self.buffer[:count]
        return block
    def sendall(self, data):
        self.send_calls += 1
        raise TimeoutError('simulated permanently blocked receiver')

@pytest.mark.parametrize('case_id', IDS, ids=IDS)
def test_m7_p0(case_id, record_property):
    record_property('case_id', case_id)
    if case_id == 'CASE-0054':
        seed_token = b'NOT_A_PLC_VALUE__PRIVATE_SCENARIO_SEED'
        telemetry = Telemetry(event_capacity=8, seed_token=seed_token)
        with server_scope(telemetry=telemetry) as server:
            server.memory.write_words(100, [0xBEEF])
            with socket.create_connection(server.server_address, timeout=2) as sock:
                sock.settimeout(2)
                sock.sendall(request(head=100, points=1))
                assert int.from_bytes(read_reply(sock)[11:13], 'little') == 0xBEEF
            wait_for(lambda:telemetry.snapshot()['counters'].get('request_ok',0)==1)
        evidence = telemetry.snapshot()['sample'][0]
        assert evidence['session_id'] >= 1
        assert evidence['command'] == 0x0401
        assert evidence['memory_version'] >= 1
        assert evidence['release_version'].startswith('0.1.0-')
        assert evidence['seed_sha256'] == hashlib.sha256(seed_token).hexdigest()
        blob = json.dumps(telemetry.snapshot())
        assert 'BEEF' not in blob and '48879' not in blob
        assert 'PRIVATE_SCENARIO_SEED' not in blob and 'NOT_A_PLC_VALUE' not in blob
        assert '127.0.0.1' not in blob
    elif case_id == 'CASE-0068':
        packet = request(head=1, points=1)
        fake = BlockedReceiverSocket(packet)
        telemetry = Telemetry()
        limiter = threading.BoundedSemaphore(1)
        handler = object.__new__(Handler)
        handler.server = SimpleNamespace(limiter=limiter, telemetry=telemetry,
            max_body=4096, memory=Memory(), allowed_routes=frozenset((DEFAULT_ROUTE,)))
        handler.request = fake
        start = time.monotonic()
        handler.handle()
        assert time.monotonic()-start < 2.5
        assert fake.send_calls == 1
        assert all(0 < t <= IDLE_TIMEOUT for t in fake.deadlines)
        assert telemetry.snapshot()['counters'].get('send_failure') == 1
        assert limiter.acquire(blocking=False)
        limiter.release()
    elif case_id == 'CASE-0126':
        with server_scope() as server:
            class LowSendBuffer(Handler):
                def handle(self):
                    self.request.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
                    super().handle()
            server.RequestHandlerClass = LowSendBuffer
            stalled = socket.create_connection(server.server_address, timeout=2)
            try:
                stalled.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
                stalled.settimeout(0.15)
                high_reply = request(points=960)
                total_sent = 0
                for _ in range(5000):
                    try:
                        stalled.sendall(high_reply)
                        total_sent += 1
                    except (TimeoutError, BrokenPipeError, ConnectionResetError):
                        break
                assert total_sent >= 10
                with socket.create_connection(server.server_address, timeout=2) as second:
                    second.settimeout(2)
                    second.sendall(request(points=1))
                    result=read_reply(second)
                    assert result[:2] == b'\xd0\x00' and result[9:11] == b'\0\0'
                wait_for(lambda:server.telemetry.snapshot()['counters'].get('send_failure',0)>=1,seconds=5)
                # A bounded diagnostic ring is stable despite abusive request counts.
                assert len(server.telemetry.snapshot()['sample']) <= 64
            finally:
                stalled.close()
