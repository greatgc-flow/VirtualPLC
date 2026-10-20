"""M24 opt-in deterministic fault taxonomy, loopback-only, bounded workload.

A synthetic MC 3E simulator test is NOT an actual PLC safety or compatibility test.
The server is never exposed outside 127.0.0.1. FaultPlan is in-process only.

Run: python -m scripts.m24_scenarios --out /fresh/outside/checkout --seed 17
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import socket
import threading
import time
import xml.etree.ElementTree as ET

from scripts import m22_soak as wire
from scripts import m23_recovery_soak as previous
from virtual_plc.faults import FaultPlan
from virtual_plc.memory import Memory
from virtual_plc.server import Server

SCENARIOS = ('disconnect_before_write', 'delay_then_read', 'read_timeout_then_reconnect')
SOURCE_FILES = ('scripts/m24_scenarios.py', 'scripts/m23_recovery_soak.py',
                'virtual_plc/faults.py', 'virtual_plc/server.py', 'virtual_plc/memory.py')


def validate_plan(seed=17, repeats=1, delay_ms=60):
    """Fixed scenario catalog; no arbitrary frame/PLC address supplied by users."""
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError('seed must be unsigned 32-bit integer')
    if type(repeats) is not int or not 1 <= repeats <= 3:
        raise ValueError('repeats must be integer 1..3')
    if type(delay_ms) is not int or not 40 <= delay_ms <= 200:
        raise ValueError('delay_ms must be integer 40..200')
    return seed, repeats, delay_ms


def scenario_order(seed=17, repeats=1):
    seed, repeats, _ = validate_plan(seed, repeats)
    rnd = random.Random(seed)
    order = []
    for _ in range(repeats):
        block = list(SCENARIOS)
        rnd.shuffle(block)
        order.extend(block)
    return tuple(order)


def _with_server(plan, func):
    memory = Memory()
    with Server(('127.0.0.1', 0), memory=memory, fault_plan=plan) as server:
        thread = threading.Thread(target=server.serve_forever,
                                  kwargs={'poll_interval': 0.01}, daemon=True)
        thread.start()
        try:
            return func(server, memory)
        finally:
            server.shutdown()
            thread.join(timeout=3)
            if thread.is_alive():
                raise RuntimeError('test server did not stop')


def _read(address, port, timeout=1.5):
    with socket.create_connection(('127.0.0.1', port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        return previous._read_word(sock, address)


def delay_then_read(delay_ms):
    """Delay only an initial read, verify exact response and consumption."""
    plan = FaultPlan([{'action': 'delay', 'delay_ms': delay_ms}])

    def run(server, memory):
        value, latency_us = _read(100, server.server_address[1])
        if value != 0 or memory.version != 0 or plan.snapshot()['consumed'] != 1:
            raise AssertionError('delayed read corrupted state or fault sequence')
        if server.telemetry.snapshot()['counters'].get('fault_delay') != 1:
            raise AssertionError('delay telemetry missing')
        return {'scenario': 'delay_then_read', 'readback_unchanged': True,
                'latency_us_observed': latency_us, 'delay_ms_configured': delay_ms}
    return _with_server(plan, run)


def read_timeout_then_reconnect(delay_ms):
    """Timeout read only; NEVER automatically retry an ambiguous write."""
    plan = FaultPlan([{'action': 'delay', 'delay_ms': delay_ms}, {'action': 'pass'}])

    def run(server, memory):
        port = server.server_address[1]
        with socket.create_connection(('127.0.0.1', port), timeout=1) as sock:
            sock.settimeout(0.012)
            sock.sendall(wire.frame(0x0401, 0, 100, 0xA8, 1))
            try:
                wire.recv_exact(sock, 2)
            except socket.timeout:
                timed_out = True
            else:
                timed_out = False
        if not timed_out:
            raise AssertionError('read timeout not observed')
        # Wait for consumption of first fault step before the reconnect.
        deadline = time.monotonic() + 1.0
        while plan.snapshot()['consumed'] < 1 and time.monotonic() < deadline:
            time.sleep(0.002)
        if plan.snapshot()['consumed'] != 1:
            raise AssertionError('timed-out request not consumed')
        value, _ = _read(100, port)
        if value != 0 or memory.version != 0 or plan.snapshot()['consumed'] != 2:
            raise AssertionError('read timeout/reconnect state mismatch')
        if server.telemetry.snapshot()['counters'].get('fault_delay') != 1:
            raise AssertionError('timeout fault not recorded')
        return {'scenario': 'read_timeout_then_reconnect', 'observed_timeout': True,
                'successful_reconnect': True, 'memory_unchanged': True,
                'delay_ms_configured': delay_ms}
    return _with_server(plan, run)


def run_one(name, delay_ms):
    if name == 'disconnect_before_write':
        result = previous.fault_recovery_cycle(delay_ms)
        if not result['verified_readback'] or result['write_before_disconnect_applied']:
            raise AssertionError('failed synthetic recovery invariants')
        return {'scenario': name, 'recovered': True, 'dropped_write_uncommitted': True}
    if name == 'delay_then_read':
        return delay_then_read(delay_ms)
    if name == 'read_timeout_then_reconnect':
        return read_timeout_then_reconnect(delay_ms)
    raise ValueError('unknown scenario')


def _json_bytes(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')


def _safe_output(out):
    path = Path(out).resolve()
    root = Path(__file__).resolve().parents[1]
    if root == path or root in path.parents or path.exists():
        raise ValueError('output must not exist and must be outside source tree')
    return path


def run(out, seed=17, repeats=1, delay_ms=60):
    seed, repeats, delay_ms = validate_plan(seed, repeats, delay_ms)
    target = _safe_output(out)
    hashes = {name: wire.sha(Path(__file__).resolve().parents[1] / name) for name in SOURCE_FILES}
    target.mkdir(parents=True, exist_ok=False)
    order = scenario_order(seed, repeats)
    report = {'schema': 'm24-scenario-matrix-v1', 'status': 'HOLD_EXECUTION_FAILED',
              'release': 'HOLD', 'not_a_certification': True, 'loopback_only': True,
              'seed': seed, 'repeats': repeats, 'delay_ms': delay_ms,
              'platform': platform.system(), 'scenarios_order': list(order),
              'results': [], 'source_sha256': hashes, 'source_unchanged': None,
              'external_p0_promoted': 0}
    lines = ['M24 DETERMINISTIC LOOPBACK FAULT MATRIX; RELEASE=HOLD']
    for name in order:
        try:
            row = run_one(name, delay_ms)
            row['status'] = 'OBSERVED_NONCERTIFYING'
        except Exception as exc:
            row = {'scenario': name, 'status': 'HOLD_EXECUTION_FAILED',
                   'failure_type': type(exc).__name__}
        report['results'].append(row)
        lines.append('SCENARIO {} {}'.format(name, row['status']))
        if row['status'] != 'OBSERVED_NONCERTIFYING':
            break
    report['source_unchanged'] = all(
        wire.sha(Path(__file__).resolve().parents[1] / name) == digest
        for name, digest in hashes.items())
    if not report['source_unchanged']:
        report['status'] = 'HOLD_SOURCE_CHANGED'
    elif len(report['results']) == len(order) and all(
            row['status'] == 'OBSERVED_NONCERTIFYING' for row in report['results']):
        report['status'] = 'OBSERVED_NONCERTIFYING'
    lines.append('STATUS={} RELEASE=HOLD'.format(report['status']))
    text = '\n'.join(lines) + '\n'
    print(text, end='', flush=True)
    (target / 'console.log').write_bytes(text.encode('utf-8'))
    (target / 'report.json').write_bytes(_json_bytes(report))
    suite = ET.Element('testsuite', name='m24_local_matrix', tests=str(len(order)), failures='0')
    for idx, name in enumerate(order):
        case = ET.SubElement(suite, 'testcase', name='{}_{:02d}'.format(name, idx),
                             classname='m24_synthetic_only')
        if idx >= len(report['results']) or report['results'][idx]['status'] != 'OBSERVED_NONCERTIFYING' or not report['source_unchanged']:
            ET.SubElement(case, 'failure', message='not verified')
    suite.set('failures', str(len(suite.findall('.//failure'))))
    ET.ElementTree(suite).write(str(target / 'junit.xml'), encoding='utf-8', xml_declaration=True)
    names = ('console.log', 'report.json', 'junit.xml')
    manifest = {'schema': 'm24-local-evidence-v1', 'files': {
        name: {'bytes': (target / name).stat().st_size, 'sha256': wire.sha(target / name)}
        for name in names}}
    (target / 'MANIFEST_SHA256.json').write_bytes(_json_bytes(manifest))
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True)
    p.add_argument('--seed', type=int, default=17)
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--delay-ms', type=int, default=60)
    args = p.parse_args(argv)
    result = run(args.out, args.seed, args.repeats, args.delay_ms)
    return 0 if result['status'] == 'OBSERVED_NONCERTIFYING' else 1


if __name__ == '__main__':
    raise SystemExit(main())
