"""Bounded, opt-in localhost MC 3E binary load measurement; NOT a vendor certification.

Run: python -m scripts.m22_soak --out /path/to/new_empty_directory [--clients 1,4,8] [--iterations 30]
Everything runs on 127.0.0.1. Source and result hashes prove local provenance,
not independent Windows, PLC or performance acceptance. No arbitrary pass SLA.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import math
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

ROUTE = bytes.fromhex('00ffff0300')
REQUEST_HEADER = b'\x50\x00'
RESPONSE_HEADER = b'\xd0\x00'
MAX_CLIENTS = 8  # < server MAX_SESSIONS=16; leave capacity for readiness probes
MAX_ITERATIONS = 2000
MAX_TOTAL_REQUESTS = 8 * 2000 * 4
TIMEOUT_SECONDS = 3.0


def validate_plan(clients=(1, 4, 8), iterations=30):
    """Fail closed on ambiguous/oversized load plans (including bool and None)."""
    if not isinstance(clients, (list, tuple)) or not clients or len(clients) > 3:
        raise ValueError('1..3 client stages required')
    if any(type(n) is not int or not 1 <= n <= MAX_CLIENTS for n in clients):
        raise ValueError('each stage must have 1..8 clients')
    if len(set(clients)) != len(clients) or list(clients) != sorted(clients):
        raise ValueError('client stages must be unique ascending')
    if type(iterations) is not int or not 1 <= iterations <= MAX_ITERATIONS:
        raise ValueError('iterations must be 1..2000')
    if sum(clients) * iterations * 4 > MAX_TOTAL_REQUESTS:
        raise ValueError('request budget exceeded')
    return tuple(clients), iterations


def nearest_rank(values, percentile):
    """Discrete nearest-rank percentile, documented to avoid interpolation ambiguity."""
    if not values or type(percentile) not in (float, int) or not 0 < percentile <= 100:
        raise ValueError('nonempty values and percentile (0,100] required')
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percentile / 100) - 1)]


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def rss_trend_kib_per_minute(samples):
    """Least-squares RSS slope (KiB/min); descriptive, NOT leak diagnosis."""
    if len(samples) < 3:
        return None
    t0 = samples[0][0]
    xs = [t-t0 for t, _ in samples]
    ys = [v for _, v in samples]
    if xs[-1] <= 0:
        return None
    xm, ym = sum(xs)/len(xs), sum(ys)/len(ys)
    den = sum((x-xm)**2 for x in xs)
    if den <= 0:
        return None
    return round((sum((x-xm)*(y-ym) for x,y in zip(xs,ys)) / den)*60, 3)


def read_rss_kib(pid):
    """Read child process RSS; return None if unsupported. Never silently use 0."""
    if type(pid) is not int or pid <= 0:
        return None
    if sys.platform.startswith('linux'):
        try:
            with open('/proc/{}/status'.format(pid), encoding='ascii') as f:
                for line in f:
                    if line.startswith('VmRSS:'):
                        parts = line.split()
                        return int(parts[1]) if len(parts) == 3 and parts[2] == 'kB' else None
        except (OSError, ValueError):
            return None
    elif sys.platform == 'win32':
        # Windows PROCESS_MEMORY_COUNTERS.WorkingSetSize, without extra packages.
        try:
            import ctypes
            from ctypes import wintypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            PROCESS_VM_READ = 0x0010
            class PMC(ctypes.Structure):
                _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                            ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                            ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                            ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                            ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            psapi = ctypes.WinDLL('psapi', use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
            if not handle:
                return None
            try:
                counter = PMC()
                counter.cb = ctypes.sizeof(PMC)
                psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
                psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
                if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counter), counter.cb):
                    return None
                return counter.WorkingSetSize // 1024
            finally:
                kernel32.CloseHandle(handle)
        except (OSError, ValueError, AttributeError):
            return None
    return None


def frame(command, sub, head, device, values_or_count):
    """Encode only the fixed Q D/M batch commands, with a 960-point ceiling."""
    if (command, sub, device) not in ((0x0401, 0, 0xA8), (0x1401, 0, 0xA8),
                                       (0x0401, 1, 0x90), (0x1401, 1, 0x90)):
        raise ValueError('unsupported command')
    if type(head) is not int or not 0 <= head <= 9999:
        raise ValueError('invalid head')
    if command == 0x0401:
        if type(values_or_count) is not int or not 1 <= values_or_count <= 960:
            raise ValueError('invalid count')
        n, payload = values_or_count, b''
    else:
        if not isinstance(values_or_count, (list, tuple)) or not 1 <= len(values_or_count) <= 960:
            raise ValueError('invalid values')
        n = len(values_or_count)
        if sub == 0:
            if any(type(v) is not int or not 0 <= v <= 65535 for v in values_or_count):
                raise ValueError('invalid words')
            payload = struct.pack('<' + 'H' * n, *values_or_count)
        else:
            if any(type(v) is not int or v not in (0, 1) for v in values_or_count):
                raise ValueError('invalid bits')
            payload = bytes((values_or_count[i] << 4) | (values_or_count[i+1] if i+1 < n else 0)
                            for i in range(0, n, 2))
    body = struct.pack('<HHH', 4, command, sub) + head.to_bytes(3, 'little') + bytes([device]) + struct.pack('<H', n) + payload
    return REQUEST_HEADER + ROUTE + struct.pack('<H', len(body)) + body


def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        part = sock.recv(n-len(buf))
        if not part:
            raise ConnectionError('response ended mid-frame')
        buf.extend(part)
    return bytes(buf)


def exchange(sock, request):
    tick = time.perf_counter_ns()
    sock.sendall(request)
    hdr = recv_exact(sock, 9)
    if hdr[:2] != RESPONSE_HEADER or hdr[2:7] != ROUTE:
        raise ValueError('response header/route mismatch')
    size = int.from_bytes(hdr[7:9], 'little')
    if not 2 <= size <= 4096:
        raise ValueError('invalid response size')
    data = recv_exact(sock, size)
    if data[:2] != b'\x00\x00':
        raise ValueError('nonzero error code')
    return data[2:], (time.perf_counter_ns()-tick)//1000  # microseconds


def worker(port, worker_id, iterations, start_barrier):
    """Unique, non-overlapping D/M addresses avoid races masquerading as failures."""
    latencies = []
    dhead, mhead = 100 + worker_id * 10, 500 + worker_id * 10
    with socket.create_connection(('127.0.0.1', port), TIMEOUT_SECONDS) as s:
        s.settimeout(TIMEOUT_SECONDS)
        start_barrier.wait(timeout=TIMEOUT_SECONDS)
        for n in range(iterations):
            value = (worker_id * 997 + n * 101) % 65536
            d = [value, value ^ 0xFFFF]
            bits = [n % 2, (n + worker_id) % 2, 1]
            ans, us = exchange(s, frame(0x1401, 0, dhead, 0xA8, d))
            if ans: raise AssertionError('word write must have empty success data')
            latencies.append(us)
            ans, us = exchange(s, frame(0x0401, 0, dhead, 0xA8, 2))
            if ans != struct.pack('<HH', *d): raise AssertionError('word readback mismatch')
            latencies.append(us)
            ans, us = exchange(s, frame(0x1401, 1, mhead, 0x90, bits))
            if ans: raise AssertionError('bit write must have empty success data')
            latencies.append(us)
            ans, us = exchange(s, frame(0x0401, 1, mhead, 0x90, 3))
            if ans != bytes(((bits[0] << 4) | bits[1], (bits[2] << 4))):
                raise AssertionError('bit readback mismatch')
            latencies.append(us)
    return latencies


def _pick_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _await_server(proc, port):
    for _ in range(100):
        if proc.poll() is not None:
            raise RuntimeError('server exited before becoming ready')
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.02)
    raise TimeoutError('loopback server startup timeout')


def measure_stage(clients, iterations):
    port = _pick_port()
    # Isolate server RSS in its own process; no shell or external host selection.
    command = [sys.executable, '-m', 'virtual_plc', '--host', '127.0.0.1', '--port', str(port)]
    proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    stop = threading.Event()
    rss = []  # monotonic timestamp and *server child* KiB tuples
    def sampler():
        while not stop.wait(0.025):
            v = read_rss_kib(proc.pid)
            if v is not None: rss.append((time.monotonic(),v))
    thread = threading.Thread(target=sampler, daemon=True)
    try:
        _await_server(proc, port)
        initial_rss = read_rss_kib(proc.pid)
        if initial_rss is not None: rss.append((time.monotonic(),initial_rss))
        thread.start()
        barrier = threading.Barrier(clients)
        t0 = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=clients) as executor:
            futures = [executor.submit(worker, port, j, iterations, barrier) for j in range(clients)]
            values = [f.result(timeout=min(120, 5 + 4 * iterations)) for f in futures]
        elapsed = time.perf_counter() - t0
        final_rss = read_rss_kib(proc.pid)
        if final_rss is not None: rss.append((time.monotonic(),final_rss))
        samples = [x for row in values for x in row]
        if len(samples) != clients * iterations * 4:
            raise AssertionError('missing request latency samples')
        return {
            'clients_configured': clients, 'connections_successful': len(values),
            'iterations_per_client': iterations, 'requests_ok': len(samples),
            'requests_failed': 0, 'elapsed_seconds': round(elapsed, 6),
            'throughput_requests_per_second': round(len(samples)/elapsed, 3),
            'latency_unit': 'microseconds', 'percentile_method': 'nearest_rank',
            'p50_us': nearest_rank(samples, 50), 'p95_us': nearest_rank(samples, 95),
            'p99_us': nearest_rank(samples, 99), 'max_us': max(samples),
            'rss_scope': 'isolated_server_child_process_only', 'rss_unit': 'KiB',
            'rss_initial_kib': initial_rss, 'rss_final_kib': final_rss,
            'rss_peak_observed_kib': max(v for _, v in rss) if rss else None,
            'rss_trend_kib_per_minute': rss_trend_kib_per_minute(rss),
            'rss_trend_interpretation': 'descriptive_only_not_leak_diagnosis',
            'rss_samples': len(rss),
            'rss_delta_kib': final_rss - initial_rss if initial_rss is not None and final_rss is not None else None,
            'resource_sample_status': 'OBSERVED' if len(rss) >= 2 else 'UNAVAILABLE',
            'sessions_active_observed': None,  # server does not export live gauge; do NOT fabricate
        }
    finally:
        stop.set()
        if thread.is_alive(): thread.join(timeout=2)
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait(timeout=3)


def _json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')


def verify_evidence(folder):
    """Verify an untouched result directory by manifest, without trusting report status."""
    root = Path(folder)
    manifest = json.loads((root/'MANIFEST_SHA256.json').read_text(encoding='utf-8'))
    if set(manifest) != {'entries', 'schema'} or manifest['schema'] != 'm22-local-evidence-v1':
        raise ValueError('manifest schema mismatch')
    entries = manifest['entries']
    if set(entries) != {'report.json', 'console.log', 'junit.xml'}:
        raise ValueError('manifest inventory mismatch')
    for name, info in entries.items():
        file = root/name
        if not file.is_file() or file.stat().st_size != info['bytes'] or sha(file) != info['sha256']:
            raise ValueError('evidence hash mismatch: '+name)
    return json.loads((root/'report.json').read_text(encoding='utf-8'))


def run(out, clients=(1,4,8), iterations=30):
    clients, iterations = validate_plan(clients, iterations)
    target = Path(out).resolve()
    source_root = Path.cwd().resolve()
    if target == source_root or source_root in target.parents:
        raise ValueError('evidence output must stay outside source working tree')
    if target.exists(): raise FileExistsError('evidence output path already exists')
    # Only explicit fresh directory, no overwrite or reuse.
    target.mkdir(parents=True, exist_ok=False)
    lines = []
    report = {
        'schema': 'm22-soak-v1', 'status': 'HOLD', 'release': 'HOLD',
        'not_a_certification': True, 'loopback_only': True,
        'platform': platform.system(), 'python': platform.python_version(),
        'scope': 'isolated server child RSS; loopback network; no vendor PLC',
        'policy': 'descriptive metrics only; no SLA threshold or independent signoff',
        'clients': list(clients), 'iterations': iterations, 'stages': [],
        'source_sha256': {p: sha(Path(p)) for p in ('virtual_plc/server.py', 'virtual_plc/protocol.py',
                                                   'virtual_plc/memory.py', 'scripts/m22_soak.py')},
    }
    def emit(message):
        lines.append(message)
        print(message, flush=True)
    emit('M22 local bounded TCP measurement (NOT A RELEASE CERTIFICATION)')
    try:
        for count in clients:
            stage = measure_stage(count, iterations)
            report['stages'].append(stage)
            emit('clients={} requests={} errors={} p50={}us p95={}us p99={}us RSS_delta={}KiB'.format(
                count, stage['requests_ok'], stage['requests_failed'],
                stage['p50_us'],stage['p95_us'],stage['p99_us'],stage['rss_delta_kib']))
        report['status'] = 'MEASURED_NOT_CERTIFIED' if all(
            s['resource_sample_status']=='OBSERVED' for s in report['stages']) else 'HOLD_RSS_UNAVAILABLE'
    except (Exception,) as exc:
        report['status'] = 'HOLD_EXECUTION_FAILED'
        report['failure_type'] = type(exc).__name__
        # Do not write request payload, environment credentials or arbitrary exception strings.
        emit('execution failed: '+type(exc).__name__)
    emit('STATUS='+report['status']+' RELEASE=HOLD')
    (target/'console.log').write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))
    (target/'report.json').write_bytes(_json_bytes(report))
    suite = ET.Element('testsuite', name='m22_descriptive_load', tests=str(len(report['stages'])),
                       failures='0' if report['status']=='MEASURED_NOT_CERTIFIED' else '1')
    for stage in report['stages']:
        ET.SubElement(suite, 'testcase', name='clients_{}_descriptive'.format(stage['clients_configured']),
                      classname='m22_load', time=str(stage['elapsed_seconds']))
    if report['status'] != 'MEASURED_NOT_CERTIFIED':
        case = ET.SubElement(suite, 'testcase', name='evidence_gate', classname='m22_load')
        ET.SubElement(case, 'failure', message='not fully measured')
        suite.set('tests',str(len(report['stages'])+1))
    ET.ElementTree(suite).write(str(target/'junit.xml'), encoding='utf-8', xml_declaration=True)
    manifest = {'schema':'m22-local-evidence-v1', 'entries':{}}
    for name in ('report.json','console.log','junit.xml'):
        f = target/name
        manifest['entries'][name] = {'sha256':sha(f), 'bytes':f.stat().st_size}
    (target/'MANIFEST_SHA256.json').write_bytes(_json_bytes(manifest))
    verify_evidence(target)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, help='fresh, nonexistent evidence directory')
    ap.add_argument('--clients', default='1,4,8', help='ascending comma-separated 1..8, max 3 stages')
    ap.add_argument('--iterations', type=int, default=30, help='per-client iterations, 1..2000')
    args = ap.parse_args(argv)
    try:
        plan = [int(s) for s in args.clients.split(',')]
        result = run(args.out, plan, args.iterations)
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    return 0 if result['status']=='MEASURED_NOT_CERTIFIED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
