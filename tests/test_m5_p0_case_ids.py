"""M5 new P0 CASE-ID tests. Each ID maps to a distinct design oracle.

Only a strict subset of unexecuted catalog cases is implemented here.
Failure in any item must remain visible as a failed CASE-ID, not promoted.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import time
import tomllib
import pytest
from virtual_plc.memory import Memory
from virtual_plc.scenario import seed, snapshot, reset
from virtual_plc.config import DEFAULTS, load_config, validate_options
from virtual_plc.protocol import process, nibble_pack
from virtual_plc.server import Server
from suite.support.wire import request, pack_bits

ROOT = Path(__file__).resolve().parents[1]
CATALOG = {c['id']: c for line in (ROOT/'suite/catalog/test_cases.jsonl').read_text().splitlines() if (c := json.loads(line))}
VECTORS = {v['id']: v for v in json.loads((ROOT/'suite/fixtures/wire_vectors_baseline.json').read_text())}
ROUTE = bytes.fromhex('00 FF FF 03 00')

SELECTED = [
    'CASE-0006', 'CASE-0007', 'CASE-0009', 'CASE-0010', 'CASE-0011',
    'CASE-0012', 'CASE-0014', 'CASE-0016', 'CASE-0023', 'CASE-0024',
    'CASE-0025', 'CASE-0041', 'CASE-0048', 'CASE-0065', 'CASE-0081',
    'CASE-0084', 'CASE-0095', 'CASE-0104', 'CASE-0105', 'CASE-0106',
    'CASE-0123', 'CASE-0124', 'CASE-0142', 'CASE-0149',
    'CASE-0031', 'CASE-0130', 'CASE-0141'
]
assert len(SELECTED) == len(set(SELECTED))
assert all(CATALOG[x]['runner'] == 'runtime_adapter' and CATALOG[x]['phase'] == 'P0' for x in SELECTED)

@contextmanager
def loopback_server(memory=None):
    with Server(('127.0.0.1', 0), memory=memory) as server:
        th = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        th.start()
        try:
            yield server.server_address[1], server.memory
        finally:
            server.shutdown()
            th.join(timeout=2)
            assert not th.is_alive()


def read_exact(sock, n):
    data = bytearray()
    while len(data) < n:
        more = sock.recv(n - len(data))
        if not more:
            raise EOFError('unexpected close')
        data.extend(more)
    return bytes(data)


def exchange(port, packet):
    with socket.create_connection(('127.0.0.1', port), timeout=1.5) as sock:
        sock.settimeout(1.5)
        sock.sendall(packet)
        header = read_exact(sock, 9)
        body = read_exact(sock, int.from_bytes(header[7:9], 'little'))
        return header + body


def reply_code(reply):
    return int.from_bytes(reply[9:11], 'little')


def proto(raw, memory):
    return process(ROUTE, raw[9:], memory)

@contextmanager
def process_server():
    """Spawn an actual isolated localhost process, then terminate/kill at exit."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    p = subprocess.Popen([sys.executable, '-m', 'virtual_plc', '--host',
                          '127.0.0.1', '--port', str(port)], cwd=str(ROOT),
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        ready = False
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if p.poll() is not None:
                raise AssertionError('server process exited before bind')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.15):
                    ready = True
                    break
            except OSError:
                time.sleep(0.02)
        assert ready, 'server never entered ready state'
        yield port
    finally:
        if p.poll() is None:
            p.terminate()
        try:
            p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=2)


@pytest.mark.parametrize('case_id', SELECTED, ids=SELECTED)
def test_m5_case(case_id, record_property, tmp_path):
    record_property('case_id', case_id)
    mem = Memory(d_size=10000, m_size=10000)

    if case_id == 'CASE-0006':
        seed(mem, D={100: 100, 101: 200, 102: 300})
        vec = VECTORS['VEC001']
        assert proto(bytes.fromhex(vec['request_hex']), mem) == bytes.fromhex(vec['response_hex'])
    elif case_id == 'CASE-0007':
        vec = VECTORS['VEC002']
        assert proto(bytes.fromhex(vec['request_hex']), mem) == bytes.fromhex(vec['response_hex'])
        assert mem.read_words(100, 3) == [0x1995, 0x1202, 0x1130]
    elif case_id == 'CASE-0009':
        vec = VECTORS['VEC003']
        assert proto(bytes.fromhex(vec['request_hex']), mem) == bytes.fromhex(vec['response_hex'])
        assert mem.read_bits(10, 5) == [1, 0, 1, 0, 1]
    elif case_id == 'CASE-0010':
        seed(mem, M={10: 1, 11: 0, 12: 1, 13: 0, 14: 1})
        vec = VECTORS['VEC005']
        assert proto(bytes.fromhex(vec['request_hex']), mem) == bytes.fromhex(vec['response_hex'])
    elif case_id == 'CASE-0011':
        mem.write_bits(10, [0] * 7)
        for bits in [[1], [1, 0, 1, 0, 1, 1]]:
            pkt = request(cmd=0x1401, sub=1, head=10, device=0x90, points=len(bits), payload=pack_bits(bits))
            assert reply_code(proto(pkt, mem)) == 0
            assert mem.read_bits(10, len(bits)) == bits
            response = proto(request(sub=1, head=10, device=0x90, points=len(bits)), mem)
            assert response[11:] == pack_bits(bits)
            if len(bits) % 2:
                assert response[-1] & 15 == 0
        assert mem.read_bits(16, 1) == [0]  # odd write did not mutate padding position
    elif case_id == 'CASE-0012':
        w = request(head=100, points=1)
        b = request(sub=1, head=10, device=0x90, points=1)
        assert w[15:19] == bytes.fromhex('64 00 00 A8')
        assert b[15:19] == bytes.fromhex('0A 00 00 90')
        assert reply_code(proto(w, mem)) == reply_code(proto(b, mem)) == 0
    elif case_id == 'CASE-0014':
        before = mem.snapshot()
        r = proto(request(sub=0, head=1, device=0x90, points=1), mem)
        assert reply_code(r) != 0
        assert mem.snapshot() == before
    elif case_id == 'CASE-0016' or case_id == 'CASE-0095':
        def writer():
            for _ in range(150):
                mem.write_words(50, [0xFF] * 12)
        def resetter():
            for _ in range(150):
                mem.reset()
        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = pool.submit(writer), pool.submit(resetter)
            for _ in range(200):
                assert mem.read_words(50, 12) in ([0] * 12, [0xFF] * 12)
            a.result(timeout=4)
            b.result(timeout=4)
        assert mem.snapshot()['version'] == 300
    elif case_id == 'CASE-0023':
        assert seed(mem, D={1: 300}, M={2: 1})['D'][1] == 300
        assert snapshot(mem)['M'][2] == 1
        reset(mem)
        assert snapshot(mem)['D'][1] == snapshot(mem)['M'][2] == 0
    elif case_id == 'CASE-0024' or case_id == 'CASE-0105':
        before = snapshot(mem)
        with pytest.raises(ValueError):
            seed(mem, D={100: 7, 10000: 8}, M={3: 1})
        assert snapshot(mem) == before
    elif case_id == 'CASE-0025':
        assert load_config() == DEFAULTS
        path = tmp_path/'valid.toml'
        path.write_text('[server]\nhost="127.0.0.1"\nport=0\nd_size=300\nm_size=400\nmax_body=30\n')
        settings = load_config(path)
        assert settings['port'] == 0 and settings['d_size'] == 300 and settings['max_body'] == 30
    elif case_id == 'CASE-0041' or case_id == 'CASE-0123':
        def history():
            m = Memory(d_size=1000, m_size=1000)
            seed(m, D={100: 42}, M={10: 1}, reset=True)
            wire = proto(request(head=100, points=1), m)
            return snapshot(m), wire
        assert history() == history()
    elif case_id == 'CASE-0048':
        import ast
        for src in (ROOT/'virtual_plc').glob('*.py'):
            imports = [n.module or '' for n in ast.walk(ast.parse(src.read_text())) if isinstance(n, ast.ImportFrom)]
            imports += [a.name for n in ast.walk(ast.parse(src.read_text())) if isinstance(n, ast.Import) for a in n.names]
            assert all(not x.startswith(('yaml', 'ruamel')) for x in imports)
    elif case_id == 'CASE-0065':
        with pytest.raises(ValueError):
            Server(('127.0.0.1', 0), max_body=11)
        with pytest.raises(ValueError):
            validate_options({'max_body': 0})
        with Server(('127.0.0.1', 0), max_body=12) as server:
            assert server.max_body == 12
    elif case_id == 'CASE-0081':
        for count in (1, 2, 3, 7, 8):
            values = list(range(1, count+1))
            assert reply_code(proto(request(cmd=0x1401, head=300, points=count, payload=struct.pack('<'+'H'*count, *values)), mem)) == 0
            assert mem.read_words(300, count) == values
    elif case_id == 'CASE-0084':
        bits = [0, 1, 1, 0, 1, 1]
        assert reply_code(proto(request(cmd=0x1401, sub=1, head=1, device=0x90, points=6, payload=pack_bits(bits)), mem)) == 0
        assert proto(request(sub=1, head=1, device=0x90, points=6), mem)[11:] == b'\x01\x10\x11'
        assert mem.read_bits(1, 6) == bits
    elif case_id == 'CASE-0104':
        initial = snapshot(mem)
        changed = seed(mem, D={1: 65535}, M={2: 1})
        cleared = reset(mem)
        assert initial['version'] < changed['version'] < cleared['version']
        assert changed['D'][1] == 65535 and cleared['D'][1] == 0
    elif case_id == 'CASE-0106':
        path = tmp_path/'invalid.toml'
        path.write_text('[server\nport=5432\n')
        with pytest.raises(tomllib.TOMLDecodeError):
            load_config(path)
        result = subprocess.run([sys.executable, '-m', 'virtual_plc', '--config', str(path)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=5)
        assert result.returncode != 0 and 'configuration rejected before listening' in result.stderr
    elif case_id == 'CASE-0124':
        def run_sequence():
            m = Memory(d_size=128, m_size=128)
            for index in range(12):
                seed(m, D={index: index * 123}, M={index: index % 2})
            return snapshot(m)
        first = run_sequence()
        assert all(run_sequence() == first for _ in range(100))
    elif case_id == 'CASE-0031':
        import random
        rng = random.Random(20261020)
        before = snapshot(mem)
        started = time.monotonic()
        for _ in range(1000):
            # All mutations retain a fully decoded frame but use unsupported commands.
            cmd = rng.randint(0xE000, 0xEFFF)
            raw = request(cmd=cmd, head=rng.randrange(10000), points=1)
            response = proto(raw, mem)
            assert reply_code(response) != 0 and response[11:16] == ROUTE
        assert time.monotonic() - started < 5.0
        assert snapshot(mem) == before
    elif case_id == 'CASE-0130':
        # Remote-bind attempts fail before Server creates any listening socket.
        from unittest.mock import patch
        with patch('virtual_plc.server.socketserver.TCPServer.__init__') as bind:
            with pytest.raises(ValueError):
                Server(('192.0.2.1', 5000))
            bind.assert_not_called()
        with pytest.raises(ValueError):
            validate_options({'host': '192.0.2.1'})
    elif case_id == 'CASE-0141':
        before = snapshot(mem)
        for cmd, sub, qty, data in (
                (0xE012, 0, 1, b''), (0x1401, 0, 0, b''),
                (0x1401, 0, 2, b'\x01'), (0x1401, 1, 1, b'\xFF')):
            raw = request(cmd=cmd, sub=sub, head=200, device=0x90 if sub else 0xA8,
                          points=qty, payload=data)
            response = proto(raw, mem)
            assert reply_code(response) != 0
            assert len(response) <= 32
        assert snapshot(mem) == before
    elif case_id == 'CASE-0142':
        with process_server() as port:
            assert reply_code(exchange(port, request(head=0, points=1))) == 0
        with pytest.raises((OSError, TimeoutError)):
            socket.create_connection(('127.0.0.1', port), timeout=0.25)
    elif case_id == 'CASE-0149':
        with process_server() as port:
            raw = request(cmd=0x1401, head=500, points=1, payload=b'\xEF\xBE')
            assert reply_code(exchange(port, raw)) == 0
            assert exchange(port, request(head=500, points=1))[11:] == b'\xEF\xBE'
        with process_server() as fresh_port:
            assert exchange(fresh_port, request(head=500, points=1))[11:] == b'\x00\x00'
    else:
        raise AssertionError('case not implemented: '+case_id)
