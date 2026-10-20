"""M24 bounded cross-run performance comparison. Descriptive, NOT SLA or leak certification.

Only authenticated *locally hashed* evidence in the M23 report schema is accepted;
file SHA does not prove provenance. Without equal run conditions comparison is
INCOMPARABLE. All thresholds optional and caller-owned, never auto-created.

Usage: python -m scripts.m24_compare --baseline B/report.json --candidate C/report.json --out /fresh/output
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys

REQUIRED = ('p50_us', 'p95_us', 'p99_us', 'requests_ok', 'requests_failed',
            'clients', 'duration_requested_seconds', 'rss_initial_kib',
            'rss_final_kib', 'rss_sample_count')
THRESHOLDS = ('p95_growth_percent', 'p99_growth_percent', 'rss_growth_kib')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_report(path):
    """Reject missing, failed, contradictory and nonnumeric evidence."""
    p = Path(path).resolve(strict=True)
    if not p.is_file() or p.stat().st_size > 2_000_000:
        raise ValueError('invalid report size')
    try:
        report = json.loads(p.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError) as exc:
        raise ValueError('invalid report JSON') from exc
    if not isinstance(report, dict) or (report.get('schema') != 'm23-recovery-duration-v1'
        or report.get('status') != 'MEASURED_NOT_CERTIFIED'
        or report.get('release') != 'HOLD'
        or report.get('not_a_certification') is not True
        or report.get('loopback_only') is not True
        or report.get('source_unchanged') is not True
        or report.get('p0_external_approvals') != 0):
        raise ValueError('not an eligible locally observed M23 report')
    x = report.get('duration_soak')
    if not isinstance(x, dict) or x.get('resource_sample_status') != 'OBSERVED' or x.get('rss_scope') != 'one_isolated_server_child_same_pid':
        raise ValueError('incomplete measurement report')
    for k in REQUIRED:
        v = x.get(k)
        if v is not None and (type(v) not in (int, float) or not math.isfinite(v) or v < 0):
            raise ValueError('invalid numeric measurement: ' + k)
    if any(x.get(k) is None for k in ('p50_us', 'p95_us', 'p99_us', 'requests_ok',
                    'requests_failed', 'clients', 'duration_requested_seconds')):
        raise ValueError('required measurement missing')
    if (type(x['clients']) is not int or type(x['requests_ok']) is not int
        or type(x['requests_failed']) is not int or type(x['rss_sample_count']) is not int
        or type(x['duration_requested_seconds']) not in (int, float)):
        raise ValueError('invalid measurement types')
    if (not isinstance(report.get('platform'), str) or not report['platform']
        or not isinstance(report.get('python_version'), str) or not report['python_version']):
        raise ValueError('environment metadata missing')
    if (x['requests_ok'] == 0 or x['requests_failed'] != 0
        or not 1 <= x['clients'] <= 8 or not 0.2 <= x['duration_requested_seconds'] <= 60
        or not (x['p50_us'] <= x['p95_us'] <= x['p99_us'])
        or x['rss_sample_count'] < 3):
        raise ValueError('inconsistent measurements')
    if not isinstance(report.get('source_sha256'), dict) or not report['source_sha256']:
        raise ValueError('source fingerprints missing')
    if any(type(k) is not str or type(v) is not str or len(v) != 64 or
           any(c not in '0123456789abcdef' for c in v) for k,v in report['source_sha256'].items()):
        raise ValueError('bad source digest')
    return report, _sha(p)


def validate_limits(limits=None):
    if limits is None:
        return None
    if not isinstance(limits, dict) or not limits or set(limits) - set(THRESHOLDS):
        raise ValueError('thresholds must be explicit known keys')
    for v in limits.values():
        if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
            raise ValueError('threshold must be finite and nonnegative')
    return dict(limits)


def compare(baseline, candidate, limits=None, allow_source_drift=False):
    limits = validate_limits(limits)
    if type(allow_source_drift) is not bool:
        raise ValueError('allow_source_drift must be boolean')
    b, bh = parse_report(baseline)
    c, ch = parse_report(candidate)
    if Path(baseline).resolve() == Path(candidate).resolve() or bh == ch:
        raise ValueError('identical reports cannot prove independent runs')
    bx, cx = b['duration_soak'], c['duration_soak']
    reasons = []
    if b.get('platform') != c.get('platform') or b.get('python_version') != c.get('python_version'):
        reasons.append('different_platform_or_python')
    if bx['clients'] != cx['clients'] or bx['duration_requested_seconds'] != cx['duration_requested_seconds'] or bx.get('max_cycles') != cx.get('max_cycles'):
        reasons.append('different_workload')
    if b.get('source_sha256') != c.get('source_sha256') and not allow_source_drift:
        reasons.append('source_changed')
    deltas = {}
    for k in ('p50_us', 'p95_us', 'p99_us'):
        old, new = bx[k], cx[k]
        deltas[k] = {'baseline': old, 'candidate': new, 'absolute_change_us': new-old,
                     'relative_change_percent': None if old == 0 else round((new-old)*100/old,3)}
    a, d = bx['rss_final_kib'], cx['rss_final_kib']
    rss_delta = None if a is None or d is None else d-a
    changed = {'p95_growth_percent': deltas['p95_us']['relative_change_percent'],
               'p99_growth_percent': deltas['p99_us']['relative_change_percent'],
               'rss_growth_kib': rss_delta}
    # Descriptive only. Even an optional exceedance is NOT a release decision.
    exceeded = []
    if not reasons and limits:
        for key, max_delta in limits.items():
            if changed[key] is None:
                reasons.append('missing_data_for_' + key)
            elif changed[key] > max_delta:
                exceeded.append(key)
    status = ('INCOMPARABLE' if reasons else 'OPTIONAL_THRESHOLD_EXCEEDED' if exceeded
              else 'COMPARABLE_DESCRIPTIVE')
    return {'schema':'m24-compare-v1','status':status,'release':'HOLD',
            'not_a_certification':True,'no_memory_leak_claim':True,
            'baseline_sha256':bh,'candidate_sha256':ch,
            'source_drift_allowed':allow_source_drift,
            'source_equal':b['source_sha256']==c['source_sha256'],
            'environment':{'baseline_platform':b.get('platform'),'candidate_platform':c.get('platform'),
                           'baseline_python':b.get('python_version'),'candidate_python':c.get('python_version')},
            'issues':reasons,'thresholds_explicit':limits,'thresholds_exceeded':exceeded,
            'latency_deltas':deltas,'rss_final_delta_kib':rss_delta,
            'interpretation':'observed_only_no_SLA_or_leak_freedom'}


def write_once(out, result):
    target = Path(out).resolve()
    root = Path(__file__).resolve().parents[1]
    if target.exists() or target == root or root in target.parents:
        raise ValueError('fresh output outside source tree required')
    target.mkdir(parents=True, exist_ok=False)
    body = (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode('utf-8')
    console = ('M24 COMPARISON: {}; RELEASE=HOLD; NOT CERTIFIED\n'.format(result['status'])).encode('utf-8')
    print(console.decode('utf-8'), end='', flush=True)
    (target/'comparison.json').write_bytes(body)
    (target/'console.log').write_bytes(console)
    entries = {name:{'bytes':(target/name).stat().st_size, 'sha256':_sha(target/name)}
               for name in ('comparison.json','console.log')}
    (target/'MANIFEST_SHA256.json').write_text(json.dumps({'schema':'m24-compare-evidence-v1','files':entries},sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--thresholds-json', default=None, help='optional explicit comparison thresholds JSON (never a vendor SLA)')
    ap.add_argument('--allow-source-drift', action='store_true')
    args = ap.parse_args(argv)
    limits = None
    if args.thresholds_json:
        p = Path(args.thresholds_json)
        if p.stat().st_size > 4096:
            raise ValueError('threshold policy too large')
        limits = json.loads(p.read_text(encoding='utf-8'))
    result = compare(args.baseline, args.candidate, limits, args.allow_source_drift)
    write_once(args.out, result)
    return 0 if result['status'] == 'COMPARABLE_DESCRIPTIVE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
