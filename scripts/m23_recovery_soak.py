"""M23 bounded, opt-in loopback recovery and same-process duration soak.

No vendor PLC, no remote fault control, no background scheduling, no SLA,
no leak-free claim. Only Linux observed locally unless proven otherwise.

Run from repository root:
    python -m scripts.m23_recovery_soak --out /absolute/fresh --clients 4 --duration 2

A run produces console.log, report.json, junit.xml, MANIFEST_SHA256.json.
All paths must be outside the working tree and must not preexist.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import platform
import socket
import struct
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET

from scripts import m22_soak as base
from virtual_plc.faults import FaultPlan
from virtual_plc.memory import Memory
from virtual_plc.server import Server

MAX_DURATION_SEC = 60.0
MAX_CYCLES = 5000
MAX_CLIENTS = 8
SOURCE_FILES = (
    'scripts/m23_recovery_soak.py', 'scripts/m22_soak.py',
    'virtual_plc/server.py', 'virtual_plc/faults.py',
    'virtual_plc/memory.py', 'virtual_plc/protocol.py',
)


def validate_options(clients=4, duration=2.0, max_cycles=1000):
    """Reject booleans/non-finite values and all unbounded workload settings."""
    if type(clients) is not int or not 1 <= clients <= MAX_CLIENTS:
        raise ValueError('clients must be integer 1..8')
    if type(duration) not in (int, float) or not 0.2 <= duration <= MAX_DURATION_SEC:
        raise ValueError('duration must be finite seconds 0.2..60')
    if type(max_cycles) is not int or not 1 <= max_cycles <= MAX_CYCLES:
        raise ValueError('max_cycles must be integer 1..5000')
    return clients, float(duration), max_cycles


def _read_word(sock, address=100):
    payload, duration = base.exchange(sock, base.frame(0x0401, 0, address, 0xA8, 1))
    if len(payload) != 2:
        raise AssertionError('unexpected word response length')
    return struct.unpack('<H', payload)[0], duration


def _write_word(sock, address, value):
    payload, duration = base.exchange(sock, base.frame(0x1401, 0, address, 0xA8, [value]))
    if payload:
        raise AssertionError('write response must contain no device data')
    return duration


def fault_recovery_cycle(delay_ms=35):
    """Deterministic disconnect-before-write, reconnect, delay, write+readback.

    FaultPlan is in-process only; a local server owns unique ephemeral loopback
    port. The initial write is deliberately dropped *before* memory mutation.
    Reconnecting opens a new socket; it never forwards to production equipment.
    """
    if type(delay_ms) is not int or not 1 <= delay_ms <= 500:
        raise ValueError('delay_ms must be 1..500 integer')
    memory = Memory()
    plan = FaultPlan([{'action': 'disconnect'}, {'action': 'delay', 'delay_ms': delay_ms},
                      {'action': 'pass'}])
    with Server(('127.0.0.1', 0), memory=memory, fault_plan=plan) as server:
        thread = threading.Thread(target=server.serve_forever,
                                  kwargs={'poll_interval': 0.01}, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            with socket.create_connection(('127.0.0.1', port), timeout=2) as sock:
                sock.settimeout(2)
                sock.sendall(base.frame(0x1401, 0, 100, 0xA8, [0x1234]))
                try:
                    data = sock.recv(1)
                except ConnectionResetError:
                    data = b''
                if data != b'':
                    raise AssertionError('injected disconnect not observed')
            if memory.read_words(100, 1) != [0] or memory.version != 0:
                raise AssertionError('dropped write mutated memory')
            with socket.create_connection(('127.0.0.1', port), timeout=2) as sock:
                sock.settimeout(2)
                initial, delay_us = _read_word(sock)
                if initial != 0:
                    raise AssertionError('pre-recovery value altered')
                _write_word(sock, 100, 0x1234)
                recovered, _ = _read_word(sock)
                if recovered != 0x1234:
                    raise AssertionError('recovery readback mismatch')
            if memory.version != 1:
                raise AssertionError('exactly one write must commit')
            snap = plan.snapshot()
            if snap != {'configured': 3, 'consumed': 3, 'remaining': 0}:
                raise AssertionError('unexpected fault consumption')
            counters = server.telemetry.snapshot()['counters']
            if counters.get('fault_disconnect') != 1 or counters.get('fault_delay') != 1:
                raise AssertionError('missing fault telemetry')
            return {'scenario': 'disconnect_before_write_then_reconnect_then_delay',
                    'observed_disconnects': 1, 'reconnects_successful': 1,
                    'write_before_disconnect_applied': False,
                    'committed_writes_after_reconnect': memory.version,
                    'delayed_read_latency_us': delay_us, 'delay_requested_ms': delay_ms,
                    'verified_readback': True, 'plan_consumed': snap['consumed']}
        finally:
            server.shutdown()
            thread.join(timeout=3)
            if thread.is_alive():
                raise RuntimeError('fault server failed to stop')


def duration_soak(clients=4, duration=2.0, max_cycles=1000):
    """One isolated server child for entire bounded series; no pass/fail SLA.

    Each wave uses short-lived loopback sessions and validates D and M readback.
    Report actual elapsed time separately: in-flight socket operations can take
    up to the bounded socket timeout past the requested duration.
    """
    clients, duration, max_cycles = validate_options(clients, duration, max_cycles)
    port = base._pick_port()
    command = [sys.executable, '-m', 'virtual_plc', '--host', '127.0.0.1', '--port', str(port)]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    series, all_latencies = [], []
    initial_rss = None
    try:
        base._await_server(proc, port)
        initial_rss = base.read_rss_kib(proc.pid)
        start = time.monotonic()
        deadline = start + duration
        with concurrent.futures.ThreadPoolExecutor(max_workers=clients) as pool:
            cycle = 0
            while cycle < max_cycles and (cycle == 0 or time.monotonic() < deadline):
                if proc.poll() is not None:
                    raise RuntimeError('server process exited during duration soak')
                barrier = threading.Barrier(clients)
                futures = [pool.submit(base.worker, port, wid, 1, barrier)
                           for wid in range(clients)]
                rows = [future.result(timeout=base.TIMEOUT_SECONDS * 3)
                        for future in futures]
                latencies = [v for values in rows for v in values]
                if len(latencies) != clients * 4:
                    raise AssertionError('unexpected request count in wave')
                all_latencies.extend(latencies)
                rss = base.read_rss_kib(proc.pid)
                series.append({'elapsed_s': round(time.monotonic() - start, 6),
                               'cycle': cycle + 1, 'requests_ok': len(all_latencies),
                               'p95_wave_us': base.nearest_rank(latencies, 95),
                               'server_rss_kib': rss})
                cycle += 1
                # Prevent extremely dense sampling and yield to server threads.
                if time.monotonic() < deadline:
                    time.sleep(min(0.02, max(0, deadline - time.monotonic())))
        if proc.poll() is not None:
            raise RuntimeError('server exited at end of soak')
        rss_pairs = [(x['elapsed_s'], x['server_rss_kib']) for x in series
                     if x['server_rss_kib'] is not None]
        rss_final = base.read_rss_kib(proc.pid)
        return {'scenario': 'same_process_duration_bounded',
                'clients': clients, 'duration_requested_seconds': duration,
                'actual_duration_seconds': round(time.monotonic() - start, 6),
                'cycles': cycle, 'max_cycles': max_cycles,
                'stopped_by': 'cycle_budget' if cycle >= max_cycles else 'duration_budget',
                'requests_ok': len(all_latencies), 'requests_failed': 0,
                'p50_us': base.nearest_rank(all_latencies, 50),
                'p95_us': base.nearest_rank(all_latencies, 95),
                'p99_us': base.nearest_rank(all_latencies, 99),
                'latency_unit': 'microseconds', 'percentile_method': 'nearest_rank',
                'rss_scope': 'one_isolated_server_child_same_pid',
                'rss_initial_kib': initial_rss, 'rss_final_kib': rss_final,
                'rss_peak_observed_kib': max((v for _, v in rss_pairs), default=None),
                'rss_slope_kib_per_minute': base.rss_trend_kib_per_minute(rss_pairs),
                'rss_sample_count': len(rss_pairs), 'rss_series': series,
                'resource_sample_status': 'OBSERVED' if len(rss_pairs) >= 3 else 'INSUFFICIENT',
                'rss_interpretation': 'descriptive_only_insufficient_for_leak_freedom_claim',
                'active_sessions_observed': None,
                'server_exited_during_test': False}
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)


def _json_bytes(item):
    return (json.dumps(item, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def verify_evidence(out):
    """Detect accidental edits to recorded files; not proof of trusted origin."""
    path = Path(out)
    if not path.is_dir() or {x.name for x in path.iterdir()} != {
            'console.log', 'report.json', 'junit.xml', 'MANIFEST_SHA256.json'}:
        raise ValueError('evidence inventory mismatch')
    m = json.loads((path / 'MANIFEST_SHA256.json').read_text(encoding='utf-8'))
    if set(m) != {'schema', 'entries'} or m['schema'] != 'm23-local-evidence-v1':
        raise ValueError('manifest schema mismatch')
    if set(m['entries']) != {'console.log', 'report.json', 'junit.xml'}:
        raise ValueError('manifest tracked files mismatch')
    for name, info in m['entries'].items():
        if set(info) != {'sha256', 'bytes'}:
            raise ValueError('manifest entry schema mismatch')
        p = path / name
        if not p.is_file() or p.stat().st_size != info['bytes'] or base.sha(p) != info['sha256']:
            raise ValueError('evidence hash mismatch: ' + name)
    report = json.loads((path / 'report.json').read_text(encoding='utf-8'))
    if report.get('release') != 'HOLD' or report.get('not_a_certification') is not True:
        raise ValueError('cannot claim release approval')
    if report.get('status') not in ('MEASURED_NOT_CERTIFIED', 'HOLD_EXECUTION_FAILED', 'HOLD_RSS_UNAVAILABLE', 'HOLD_SOURCE_CHANGED'):
        raise ValueError('unknown evidence status')
    return report


def run(out, clients=4, duration=2.0, max_cycles=1000, delay_ms=35):
    clients, duration, max_cycles = validate_options(clients, duration, max_cycles)
    if type(delay_ms) is not int or not 1 <= delay_ms <= 500:
        raise ValueError('delay_ms must be 1..500 integer')
    target = Path(out).resolve()
    root = Path.cwd().resolve()
    if target == root or root in target.parents:
        raise ValueError('output must be outside repository working tree')
    if target.exists():
        raise FileExistsError('refusing to overwrite evidence')
    hashes = {f: base.sha(Path(f)) for f in SOURCE_FILES}
    target.mkdir(parents=True, exist_ok=False)
    lines = []
    report = {'schema': 'm23-recovery-duration-v1', 'release': 'HOLD',
              'status': 'HOLD_EXECUTION_FAILED', 'not_a_certification': True,
              'loopback_only': True, 'platform': platform.system(),
              'python_version': platform.python_version(),
              'source_sha256': hashes, 'source_unchanged': None,
              'fault_recovery': None, 'duration_soak': None,
              'p0_external_approvals': 0,
              'limitations': ['synthetic local faults; not vendor-equivalent',
                              'no independent SLA, no leak-free certification',
                              'samples only; 16 external P0 remain backlog']}

    def emit(line):
        print(line, flush=True)
        lines.append(line)

    emit('M23 LOCAL FAULT/RECOVERY + SINGLE-PROCESS SOAK; NOT RELEASE CERTIFICATION')
    try:
        report['fault_recovery'] = fault_recovery_cycle(delay_ms)
        emit('FAULT: drop-before-write=verified, reconnect=verified, readback=verified')
        report['duration_soak'] = duration_soak(clients, duration, max_cycles)
        r = report['duration_soak']
        emit('SOAK: clients={} cycles={} requests={} p95={}us samples={}'.format(
            r['clients'], r['cycles'], r['requests_ok'], r['p95_us'], r['rss_sample_count']))
        report['status'] = ('MEASURED_NOT_CERTIFIED' if r['resource_sample_status'] == 'OBSERVED'
                            else 'HOLD_RSS_UNAVAILABLE')
    except Exception as exc:
        report['status'] = 'HOLD_EXECUTION_FAILED'
        report['failure_type'] = type(exc).__name__
        emit('EXECUTION_FAILED: ' + type(exc).__name__)
    try:
        report['source_unchanged'] = all(base.sha(Path(f)) == v for f, v in hashes.items())
        if not report['source_unchanged']:
            report['status'] = 'HOLD_SOURCE_CHANGED'
            emit('SOURCE_CHANGED: running code not stable')
    except OSError:
        report['source_unchanged'] = False
        report['status'] = 'HOLD_SOURCE_CHANGED'
        emit('SOURCE_CHANGED: source unavailable')
    emit('STATUS={} RELEASE=HOLD'.format(report['status']))
    (target / 'console.log').write_bytes(('\n'.join(lines) + '\n').encode('utf-8'))
    (target / 'report.json').write_bytes(_json_bytes(report))
    success = report['status'] == 'MEASURED_NOT_CERTIFIED'
    fault_passed = report['fault_recovery'] is not None
    soak_passed = (report['duration_soak'] is not None and
                   report['duration_soak']['resource_sample_status'] == 'OBSERVED')
    # Never mark an unexecuted sub-scenario as passing; keep release HOLD.
    failures = (not fault_passed) + (not soak_passed) + (not success)
    suite = ET.Element('testsuite', name='m23_internal_descriptive',
                       tests='3', failures=str(failures))
    case = ET.SubElement(suite, 'testcase', classname='m23_internal', name='fault_cycle')
    if not fault_passed:
        ET.SubElement(case, 'failure', message='not_verified')
    case = ET.SubElement(suite, 'testcase', classname='m23_internal', name='same_process_duration_soak')
    if not soak_passed:
        ET.SubElement(case, 'failure', message='not_verified')
    case = ET.SubElement(suite, 'testcase', classname='m23_internal', name='measurement_release_gate')
    if not success:
        ET.SubElement(case, 'failure', message=report['status'])
    ET.ElementTree(suite).write(str(target / 'junit.xml'), encoding='utf-8', xml_declaration=True)
    manifest = {'schema': 'm23-local-evidence-v1', 'entries': {}}
    for name in ('console.log', 'report.json', 'junit.xml'):
        file = target / name
        manifest['entries'][name] = {'bytes': file.stat().st_size, 'sha256': base.sha(file)}
    (target / 'MANIFEST_SHA256.json').write_bytes(_json_bytes(manifest))
    verify_evidence(target)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    ap.add_argument('--clients', type=int, default=4)
    ap.add_argument('--duration', type=float, default=2.0)
    ap.add_argument('--max-cycles', type=int, default=1000)
    ap.add_argument('--delay-ms', type=int, default=35)
    args = ap.parse_args(argv)
    try:
        result = run(args.out, args.clients, args.duration, args.max_cycles, args.delay_ms)
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    return 0 if result['status'] == 'MEASURED_NOT_CERTIFIED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
