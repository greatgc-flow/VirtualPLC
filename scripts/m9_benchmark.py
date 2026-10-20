"""Deterministic, loopback-only MC/SLMP read benchmark (no performance SLA claims).

Records environment, response validation, 100/1000-word p50/p95/p99 and Linux RSS.
A 1000-word logical read is split into 960+40 because the current prototype's
wire point limit is 960; never silently exceed the protocol implementation.

No real PLC traffic or remote bind; no mutable global state in the simulator.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import socket
import struct
import sys
import threading
import time
from virtual_plc.memory import Memory
from virtual_plc.server import Server

ROUTE = bytes.fromhex('00ffff0300')
MAX_POINTS = 960


def percentile(values, fraction):
    if not values or not 0 <= fraction <= 1:
        raise ValueError('nonempty samples and percentile within [0,1] required')
    seq = sorted(values)
    position = (len(seq) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(seq) - 1)
    return round(seq[low] + (seq[high] - seq[low]) * (position - low), 6)


def recv_exact(sock, count):
    result = bytearray()
    while len(result) < count:
        block = sock.recv(count-len(result))
        if not block:
            raise EOFError('socket closed in response')
        result.extend(block)
    return bytes(result)


def read_words(sock, head, count):
    if type(head) is not int or type(count) is not int or head < 0 or not 1 <= count <= MAX_POINTS:
        raise ValueError('one request supports 1..960 valid points')
    body = (struct.pack('<HHH', 0x10, 0x0401, 0)
            + head.to_bytes(3, 'little') + b'\xa8'
            + struct.pack('<H', count))
    packet = b'\x50\x00' + ROUTE + struct.pack('<H', len(body)) + body
    sock.sendall(packet)
    header = recv_exact(sock, 9)
    if header[:7] != b'\xd0\x00' + ROUTE:
        raise ValueError('wrong response frame or route')
    length = int.from_bytes(header[7:9], 'little')
    if length != count * 2 + 2:
        raise ValueError('invalid response length')
    payload = recv_exact(sock, length)
    if payload[:2] != b'\x00\x00':
        raise ValueError('nonzero end code')
    return list(struct.unpack('<' + 'H'*count, payload[2:]))


def logical_read(sock, start, count):
    values = []
    while count:
        step = min(count, MAX_POINTS)
        values.extend(read_words(sock, start, step))
        start += step
        count -= step
    return values


def rss_kib():
    if sys.platform != 'linux':
        return None
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def environment():
    try:
        pymc = importlib.metadata.version('pymcprotocol')
    except importlib.metadata.PackageNotFoundError:
        pymc = 'NOT_INSTALLED'
    return {
        'os': platform.platform(), 'platform': sys.platform,
        'python': platform.python_version(),
        'pytest': importlib.metadata.version('pytest'),
        'pymcprotocol': pymc,
        'pid': os.getpid(),
        'transport': '127.0.0.1 (loopback only)',
        'process_rss_peak_kib': rss_kib(),
    }


def measure(*, rounds=20, sizes=(100, 1000)):
    if type(rounds) is not int or not 2 <= rounds <= 1000:
        raise ValueError('rounds must be between 2 and 1000')
    if tuple(sizes) != (100, 1000):
        raise ValueError('M9 fixed-size benchmark: 100 and 1000 words only')
    memory = Memory()
    values = [(i * 73 + 11) % 65536 for i in range(1000)]
    memory.write_words(100, values)
    server = Server(('127.0.0.1', 0), memory=memory)
    worker = threading.Thread(target=server.serve_forever,
                              kwargs={'poll_interval': 0.01}, daemon=True)
    worker.start()
    measurements = []
    try:
        with socket.create_connection(server.server_address, timeout=3) as sock:
            sock.settimeout(3)
            for size in sizes:
                samples = []
                for _ in range(rounds):
                    start_ns = time.monotonic_ns()
                    got = logical_read(sock, 100, size)
                    samples.append((time.monotonic_ns() - start_ns) / 1_000_000)
                    if got != values[:size]:
                        raise AssertionError('data corruption during benchmark')
                measurements.append({
                    'words': size, 'requests_per_logical_read': math.ceil(size/MAX_POINTS),
                    'rounds': rounds, 'p50_ms': percentile(samples, 0.5),
                    'p95_ms': percentile(samples, 0.95),
                    'p99_ms': percentile(samples, 0.99),
                    'min_ms': round(min(samples), 6), 'max_ms': round(max(samples), 6),
                    'result_checksum_sha256': hashlib.sha256(struct.pack('<'+'H'*size, *values[:size])).hexdigest(),
                })
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
        if worker.is_alive():
            raise RuntimeError('server thread remained alive')
    env = environment()
    env['process_rss_peak_kib'] = rss_kib()
    return {'status': 'PASS_LOCAL_UNATTESTED', 'kind': 'loopback-3e-binary',
            'no_performance_sla': True, 'not_vendor_client': True,
            'environment': env, 'measurements': measurements,
            'seed_expression': '(index * 73 + 11) % 65536',
            'word_read_limit_per_request': MAX_POINTS,
            'release': 'HOLD'}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--rounds', type=int, default=20)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(argv)
    result = measure(rounds=a.rounds)
    output = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('x', encoding='utf-8') as target:
        target.write(output)
    print(output, end='')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
