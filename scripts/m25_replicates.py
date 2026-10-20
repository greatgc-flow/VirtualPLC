"""M25: verify M23 local evidence independently and summarize repeated observations.

M23 has one *bounded* loopback server per run. M25 requires distinct, complete,
unchanged run folders; it never creates or modifies source evidence. Fingerprints
prove file integrity only, not independent origin, hardware equivalence, SLA,
statistical significance, or leak-freedom.

Usage (from repository root):
    python -m scripts.m25_replicates --inputs /tmp/run1 /tmp/run2 /tmp/run3 --out /tmp/aggregate-new

All output paths MUST be fresh and outside the source tree. No thresholds by default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import xml.etree.ElementTree as ET

from scripts.m24_compare import parse_report

FILES = ('console.log', 'report.json', 'junit.xml')
MAX_BYTES = {'console.log': 250_000, 'report.json': 2_000_000,
             'junit.xml': 250_000, 'MANIFEST_SHA256.json': 10_000}
EXPECTED_TESTS = ('fault_cycle', 'same_process_duration_soak', 'measurement_release_gate')
MAX_RUNS = 30


def sha_bytes(content):
    return hashlib.sha256(content).hexdigest()


def _json_object(data, label):
    try:
        item = json.loads(data.decode('utf-8'))
    except (ValueError, UnicodeError) as exc:
        raise ValueError('invalid JSON: ' + label) from exc
    if not isinstance(item, dict):
        raise ValueError('JSON object required: ' + label)
    return item


def _read_safe(path, name):
    f = path / name
    if f.is_symlink() or not f.is_file() or f.stat().st_size > MAX_BYTES[name]:
        raise ValueError('unsafe/missing/oversize evidence file: ' + name)
    return f.read_bytes()


def verify_run(directory):
    """Verify a single immutable-like, complete M23 evidence folder, read-only.

    No signatures or trusted timestamp exist in M23; authenticity remains HOLD.
    Only measured, source-stable, three-test successful reports qualify.
    """
    original = Path(directory)
    if original.is_symlink():
        raise ValueError('symlink evidence directory refused')
    p = original.resolve(strict=True)
    if not p.is_dir() or {f.name for f in p.iterdir()} != set(FILES) | {'MANIFEST_SHA256.json'}:
        raise ValueError('unexpected or missing evidence file')
    raw = {name: _read_safe(p, name) for name in FILES + ('MANIFEST_SHA256.json',)}
    manifest = _json_object(raw['MANIFEST_SHA256.json'], 'manifest')
    if set(manifest) != {'schema', 'entries'} or manifest['schema'] != 'm23-local-evidence-v1' or not isinstance(manifest['entries'], dict) or set(manifest['entries']) != set(FILES):
        raise ValueError('manifest layout mismatch')
    for name in FILES:
        entry = manifest['entries'][name]
        if (not isinstance(entry, dict) or set(entry) != {'sha256','bytes'}
            or type(entry['bytes']) is not int or entry['bytes'] != len(raw[name])
            or entry['sha256'] != sha_bytes(raw[name])):
            raise ValueError('evidence digest mismatch: ' + name)
    if b'<!DOCTYPE' in raw['junit.xml'].upper() or b'<!ENTITY' in raw['junit.xml'].upper():
        raise ValueError('XML DTD/entity forbidden')
    try:
        xml = ET.fromstring(raw['junit.xml'])
    except ET.ParseError as exc:
        raise ValueError('invalid JUnit') from exc
    if xml.tag != 'testsuite' or xml.get('name') != 'm23_internal_descriptive':
        raise ValueError('JUnit suite mismatch')
    items = list(xml.iter('testcase'))
    if (len(items) != 3 or {x.get('name') for x in items} != set(EXPECTED_TESTS)
        or any(x.get('classname') != 'm23_internal' or x.find('failure') is not None
               or x.find('error') is not None or x.find('skipped') is not None for x in items)
        or xml.get('tests') != '3' or xml.get('failures') != '0'):
        raise ValueError('JUnit cases failed/missing/extra')
    report = _json_object(raw['report.json'], 'report')
    if (report.get('fault_recovery') is None or not isinstance(report['fault_recovery'], dict)
        or report['fault_recovery'].get('verified_readback') is not True
        or report['fault_recovery'].get('write_before_disconnect_applied') is not False
        or report['fault_recovery'].get('reconnects_successful') != 1
        or report['fault_recovery'].get('committed_writes_after_reconnect') != 1):
        raise ValueError('fault recovery inconsistent')
    # Reuse authoritative M24 schema / fail-closed numeric validation.
    parsed, digest = parse_report(p / 'report.json')
    if parsed != report or digest != sha_bytes(raw['report.json']):
        raise ValueError('report changed while verifying')
    soak = report['duration_soak']
    series = soak.get('rss_series')
    if (not isinstance(series, list) or not 3 <= len(series) <= 5000
        or len(series) != soak['rss_sample_count']
        or type(soak.get('cycles')) is not int or soak['cycles'] != len(series)
        or type(soak.get('requests_ok')) is not int
        or soak['requests_ok'] != 4 * soak['clients'] * len(series)):
        raise ValueError('RSS series and request totals inconsistent')
    last_elapsed = -1.0
    last_requests = 0
    for row in series:
        if not isinstance(row, dict):
            raise ValueError('RSS series row invalid')
        elapsed = row.get('elapsed_s')
        requests = row.get('requests_ok')
        rss = row.get('server_rss_kib')
        if (type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed <= last_elapsed
            or type(requests) is not int or requests - last_requests != 4*soak['clients']
            or (rss is not None and (type(rss) not in (int,float) or not math.isfinite(rss) or rss < 0))):
            raise ValueError('RSS series monotonicity invalid')
        last_elapsed, last_requests = elapsed, requests
    log = raw['console.log'].decode('utf-8',errors='strict')
    if (not log.startswith('M23 LOCAL FAULT/RECOVERY')
        or 'FAULT: drop-before-write=verified' not in log
        or 'STATUS=MEASURED_NOT_CERTIFIED RELEASE=HOLD\n' not in log
        or log.count('STATUS=') != 1):
        raise ValueError('console report mismatch')
    return {'path': str(p), 'report': report,
            'sha256': {k: sha_bytes(v) for k,v in raw.items()}}


def _safe_median(items):
    return statistics.median(items)


def analyze(inputs, min_runs=3):
    """Equal-workload repeated-run summary; no p-value or causal inference."""
    if type(min_runs) is not int or not 2 <= min_runs <= MAX_RUNS:
        raise ValueError('min_runs must be 2..30 integer')
    if not isinstance(inputs, (list,tuple)) or not min_runs <= len(inputs) <= MAX_RUNS:
        raise ValueError('run count out of bounds')
    paths = [Path(p).resolve(strict=True) for p in inputs]
    if len(set(paths)) != len(paths):
        raise ValueError('duplicate run folder')
    runs = [verify_run(p) for p in paths]
    digests = [r['sha256']['report.json'] for r in runs]
    if len(set(digests)) != len(digests):
        raise ValueError('repeated identical report content is not independent evidence')
    first = runs[0]['report']; s = first['duration_soak']
    issues = []
    for r in runs[1:]:
        t = r['report']; x=t['duration_soak']
        if t['platform'] != first['platform'] or t['python_version'] != first['python_version']:
            issues.append('environment_mismatch')
        if t['source_sha256'] != first['source_sha256']:
            issues.append('source_mismatch')
        if any(x.get(k) != s.get(k) for k in ('clients','duration_requested_seconds','max_cycles')):
            issues.append('workload_mismatch')
        if t['fault_recovery'].get('delay_requested_ms') != first['fault_recovery'].get('delay_requested_ms'):
            issues.append('fault_plan_mismatch')
    def stats(key):
        values = [r['report']['duration_soak'][key] for r in runs]
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
            return {'count': len(values),'status':'INSUFFICIENT_NUMERIC_DATA'}
        med = _safe_median(values)
        return {'count':len(values), 'min':min(values),'median':med,'max':max(values),
                'median_absolute_deviation':_safe_median([abs(v-med) for v in values]),
                'raw_observations':values}
    return {'schema':'m25-repeat-summary-v1',
            'status': 'INCOMPARABLE' if issues else 'REPEATED_OBSERVATIONS_ONLY',
            'issues':sorted(set(issues)), 'release':'HOLD', 'not_a_certification':True,
            'provenance': 'sha256_integrity_only_no_signed_origin',
            'independent_approval':False,'external_backlog_p0':16,
            'runs':len(runs), 'platform': first['platform'], 'python_version': first['python_version'],
            'source_sha256':first['source_sha256'],
            'workload':{'clients':s['clients'],'duration_requested_seconds':s['duration_requested_seconds'],
                        'max_cycles':s.get('max_cycles'),
                        'fault_delay_requested_ms':first['fault_recovery'].get('delay_requested_ms')},
            'input_evidence':[{'report_sha256':r['sha256']['report.json'],
                               'junit_sha256':r['sha256']['junit.xml'],
                               'manifest_sha256':r['sha256']['MANIFEST_SHA256.json']} for r in runs],
            'metrics': {k:stats(k) for k in ('p50_us','p95_us','p99_us','rss_initial_kib',
                        'rss_final_kib','rss_slope_kib_per_minute','requests_ok')},
            'interpretation':'descriptive_samples_only_no_SLA_no_significance_no_leak_freedom'}


def write_once(out, report):
    root=Path(__file__).resolve().parents[1]
    target=Path(out).absolute()
    if target.exists() or target == root or root in target.parents:
        raise ValueError('output must be new and outside source tree')
    target.mkdir(parents=True,exist_ok=False)
    body=(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
    line=f"M25 REPEATED EVIDENCE: {report['status']}; runs={report['runs']}; RELEASE=HOLD; NOT CERTIFIED\n"
    console=line.encode('utf-8')
    (target/'summary.json').write_bytes(body)
    (target/'console.log').write_bytes(console)
    manifest={'schema':'m25-evidence-v1','entries':{name:{'sha256':sha_bytes((target/name).read_bytes()),
                         'bytes':(target/name).stat().st_size} for name in ('summary.json','console.log')}}
    (target/'MANIFEST_SHA256.json').write_bytes((json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode())
    print(line,end='',flush=True)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',nargs='+',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--min-runs',type=int,default=3)
    options=parser.parse_args(argv)
    report=analyze(options.inputs,options.min_runs)
    write_once(options.out,report)
    return 0 if report['status']=='REPEATED_OBSERVATIONS_ONLY' else 1


if __name__=='__main__':
    raise SystemExit(main())
