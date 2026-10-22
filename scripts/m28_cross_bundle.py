"""M28 offline cross-bundle provenance and descriptive comparison.

Inputs: 2..12 original M26 result folders. Each undergoes the independent M27
read-only triage before any cross-bundle statistics. SHA-256 is integrity only:
no signatures, host identity, independent Windows validation, PLC, SLA,
statistical significance, leak-freedom, or automated release approval.
"""
from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from scripts import m24_compare as m24
from scripts import m26_multi_run as m26
from scripts import m27_compare as m27

MIN_BUNDLES = 2
MAX_BUNDLES = 12
METRICS = ('p50_us', 'p95_us', 'p99_us', 'rss_initial_kib',
           'rss_final_kib', 'rss_slope_kib_per_minute',
           'rss_within_run_delta_kib', 'requests_ok')
LIMIT_METRICS = {'p95_growth_percent': 'p95_us',
                 'p99_growth_percent': 'p99_us',
                 'rss_growth_kib': 'rss_final_kib'}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _validated_inputs(inputs):
    if not isinstance(inputs, (list, tuple)) or not MIN_BUNDLES <= len(inputs) <= MAX_BUNDLES:
        raise ValueError('M28 requires 2..12 original M26 folders')
    roots = [m27.safe_tree(item) for item in inputs]
    if len(set(roots)) != len(roots):
        raise ValueError('duplicate input folder')
    # Nested bundles could cause the same files to be credited twice.
    for i, a in enumerate(roots):
        for b in roots[i + 1:]:
            if a in b.parents or b in a.parents:
                raise ValueError('nested evidence folders')
    return roots


def _bundle(root, number):
    """Revalidate M26/M27; return only private-safe labels and digests."""
    triage = m27.analyze(root)  # Full M26 SHA/JUnit and each M25/M23 verification.
    raw = m27.bounded_file(root, 'report.json', 2_000_000)
    report = m27.json_object(raw)
    count = triage['requested']
    children = []
    identities = set()
    for i in range(1, triage['attempted'] + 1):
        # Failed/incomplete attempts have no verified M23 report. Never cherry-pick.
        if triage['runs'][i-1]['status'] != 'VERIFIED':
            continue
        item = m27.json_object(m27.bounded_file(root, f'runs/{i:02d}/report.json', 2_000_000))
        identities.add((item.get('platform'), item.get('python_version')))
        children.append(_sha(m27.bounded_file(root, f'runs/{i:02d}/report.json', 2_000_000)))
    if triage['status'] == 'COMPARABLE_DESCRIPTIVE' and len(identities) != 1:
        raise ValueError('inconsistent per-child identity')
    identity = next(iter(identities)) if len(identities) == 1 else (None, None)
    # Detect accidental source mutation during intake, not just before intake.
    m26.verify_output(root)
    return {'label': f'bundle_{number:02d}',
            'status': triage['status'], 'requested': count,
            'attempted': triage['attempted'],
            'report_sha256': _sha(raw),
            'manifest_sha256': _sha(m27.bounded_file(root, 'MANIFEST_SHA256.json', 2_000_000)),
            'child_report_sha256': children,
            'environment': {'platform': identity[0], 'python_version': identity[1],
                            'origin_attested': False, 'hardware_equivalence_proven': False},
            'source_sha256': report.get('source_sha256'),
            'options': report.get('options'),
            'statistics': triage.get('statistics') or {},
            'anomalies': [x for row in triage.get('runs', []) for x in row.get('anomalies', [])],
            'source_trust': 'HASH_ONLY_NOT_SIGNED'}


def _median(bundle, metric):
    stat = bundle['statistics'].get(metric)
    if not isinstance(stat, dict) or stat.get('status') != 'DESCRIPTIVE_ONLY':
        return None
    v = stat.get('median')
    return v if type(v) in (int, float) and math.isfinite(v) else None


def _differences(reference, candidate, allow_unequal_runs):
    mismatches = []
    if candidate['environment'] != reference['environment']:
        mismatches.append('platform_or_python_mismatch')
    if candidate['source_sha256'] != reference['source_sha256']:
        mismatches.append('source_mismatch')
    lhs, rhs = reference['options'], candidate['options']
    if not isinstance(lhs, dict) or not isinstance(rhs, dict):
        mismatches.append('missing_workload')
    else:
        if any(lhs.get(key) != rhs.get(key) for key in
               ('clients','duration','max_cycles','delay_ms','timeout')):
            mismatches.append('workload_mismatch')
        if not allow_unequal_runs and lhs.get('runs') != rhs.get('runs'):
            mismatches.append('run_count_mismatch')
    return mismatches


def analyze(inputs, limits=None, allow_unequal_runs=False):
    """Compare bundle-level medians, never pool underlying socket samples."""
    if type(allow_unequal_runs) is not bool:
        raise ValueError('allow_unequal_runs must be boolean')
    limits = m24.validate_limits(limits)
    paths = _validated_inputs(inputs)
    bundles = [_bundle(p, i) for i, p in enumerate(paths, 1)]
    # Reject replayed input evidence even when the directory/path and parent JSON differ.
    hashes = [b['report_sha256'] for b in bundles]
    if len(set(hashes)) != len(hashes):
        raise ValueError('duplicate M26 report contents')
    children = [sha for b in bundles for sha in b['child_report_sha256']]
    if len(set(children)) != len(children):
        raise ValueError('reused M23 child report across bundles')
    primary = bundles[0]
    mismatches = {}
    for b in bundles[1:]:
        issues = _differences(primary, b, allow_unequal_runs)
        if issues:
            mismatches[b['label']] = sorted(set(issues))
    invalid = [b['label'] for b in bundles if b['status'] != 'COMPARABLE_DESCRIPTIVE']
    comparisons = []
    exceedances = []
    missing = []
    incomplete_metrics = []
    sampling_differences = []
    if allow_unequal_runs:
        sampling_differences = [b['label'] for b in bundles[1:]
                                if b['requested'] != primary['requested']]
    if not invalid and not mismatches:
        for b in bundles[1:]:
            values = {}
            for key in METRICS:
                start = _median(primary, key)
                end = _median(b, key)
                if start is None or end is None:
                    incomplete_metrics.append({'candidate': b['label'], 'metric': key})
                values[key] = {
                    'baseline_median': start, 'candidate_median': end,
                    'delta': end-start if start is not None and end is not None else None}
            comparisons.append({'candidate':b['label'],'median_deltas':values})
            if limits:
                for key, limit in limits.items():
                    metric = LIMIT_METRICS[key]
                    old, new = _median(primary, metric), _median(b, metric)
                    if old is None or new is None or (key.endswith('_percent') and old == 0):
                        missing.append({'candidate': b['label'], 'metric': key})
                        continue
                    observed = (new-old)*100/old if key.endswith('_percent') else new-old
                    if observed > limit:
                        exceedances.append({'candidate': b['label'], 'metric': key,
                                            'observed': round(observed,6), 'user_limit':limit})
    status = ('HOLD_INPUT_NOT_COMPARABLE' if invalid else
              'INCOMPARABLE' if mismatches or missing or incomplete_metrics else
              'OPTIONAL_THRESHOLD_EXCEEDED' if exceedances else
              'DESCRIPTIVE_CROSS_BUNDLE')
    return {'schema': 'm28-cross-bundle-v1', 'status':status, 'release':'HOLD',
            'not_a_certification':True, 'independent_approval':False,
            'bundle_count':len(bundles), 'bundle_details':bundles,
            'ineligible_bundles':invalid, 'comparison_blockers':mismatches,
            'comparisons':comparisons, 'thresholds_explicit':limits,
            'threshold_exceedances':exceedances, 'insufficient_metrics':missing,
            'descriptive_metric_gaps':incomplete_metrics,
            'sampling_plan_differences':sampling_differences,
            'run_count_difference_explicitly_allowed':allow_unequal_runs,
            'environment_equivalence': 'OS_PYTHON_LABELS_ONLY_NOT_HOST_ATTESTATION',
            'provenance': 'SHA256_INTEGRITY_ONLY_NO_INDEPENDENT_ORIGIN',
            'historical_p0_observed':183, 'external_p0_hold':16,
            'interpretation':'bundle_medians_only_not_pooled_no_SLA_or_leak_freedom'}


def verify_output(folder):
    """Check exactly three output payloads, no symlinks, size or digest drift."""
    root = Path(folder).absolute()
    if not root.is_dir() or any(x.is_symlink() for x in (root, *root.parents)):
        raise ValueError('unsafe output root')
    expected = {'console.log','analysis.json','junit.xml','MANIFEST_SHA256.json'}
    if {p.name for p in root.iterdir()} != expected:
        raise ValueError('output inventory differs')
    mf = m27.json_object(m27.bounded_file(root, 'MANIFEST_SHA256.json', 20_000))
    if mf.get('schema') != 'm28-output-v1' or not isinstance(mf.get('entries'),dict):
        raise ValueError('bad M28 output manifest')
    if set(mf['entries']) != expected-{'MANIFEST_SHA256.json'}:
        raise ValueError('missing output manifest entry')
    for name, item in mf['entries'].items():
        data = m27.bounded_file(root,name,5_000_000)
        if (not isinstance(item,dict) or set(item) != {'bytes','sha256'}
            or type(item['bytes']) is not int or item['bytes'] != len(data)
            or item['sha256'] != _sha(data)):
            raise ValueError('M28 output digest mismatch')
    record = m27.json_object(m27.bounded_file(root, 'analysis.json', 5_000_000))
    status = record.get('status')
    if (record.get('schema')!='m28-cross-bundle-v1'
        or not isinstance(status, str) or record.get('release')!='HOLD'
        or record.get('not_a_certification') is not True
        or record.get('independent_approval') is True
        or record.get('external_p0_hold')!=16):
        raise ValueError('M28 output result inconsistent')
    console = m27.bounded_file(root, 'console.log', 250_000)
    expected_console = f'M28 CROSS-BUNDLE: {status} RELEASE=HOLD NOT CERTIFIED\n'.encode('utf-8')
    if console != expected_console:
        raise ValueError('M28 console/result contradiction')
    xml = m27.bounded_file(root,'junit.xml',250_000)
    if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
        raise ValueError('M28 JUnit DTD/entity prohibited')
    try:
        suite = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError('M28 invalid JUnit') from exc
    cases = list(suite.iter('testcase'))
    ok = status=='DESCRIPTIVE_CROSS_BUNDLE'
    if (suite.tag!='testsuite' or suite.get('name')!='m28_cross_bundle'
        or suite.get('tests')!='1' or suite.get('failures')!=('0' if ok else '1')
        or len(cases)!=1 or cases[0].get('classname')!='m28'
        or cases[0].get('name')!='descriptive_comparability_only'
        or len(cases[0].findall('failure'))!=int(not ok)
        or cases[0].find('skipped') is not None
        or cases[0].find('error') is not None):
        raise ValueError('M28 JUnit/result contradiction')
    return True


def write_once(out, report, inputs, emit_bytes=None):
    """Fresh external-only output; exact bytes sent to stdout are stored."""
    dest = Path(out).absolute()
    for input_path in inputs:
        origin = Path(input_path).absolute()
        if dest == origin or dest in origin.parents or origin in dest.parents:
            raise ValueError('M28 output must be separate from source evidence')
    dest = m26.fresh_destination(dest)
    line = f'M28 CROSS-BUNDLE: {report["status"]} RELEASE=HOLD NOT CERTIFIED\n'.encode('utf-8')
    if emit_bytes is None:
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
    else:
        emit_bytes(line)
    (dest/'console.log').write_bytes(line)
    (dest/'analysis.json').write_bytes(m26.json_bytes(report))
    ok = report['status'] == 'DESCRIPTIVE_CROSS_BUNDLE'
    suite = ET.Element('testsuite',name='m28_cross_bundle',tests='1',failures='0' if ok else '1')
    case = ET.SubElement(suite,'testcase',classname='m28',name='descriptive_comparability_only')
    if not ok:
        ET.SubElement(case,'failure',message=report['status'])
    (dest/'junit.xml').write_bytes(ET.tostring(suite,encoding='utf-8',xml_declaration=True))
    entries = {}
    for name in ('console.log','analysis.json','junit.xml'):
        data = (dest/name).read_bytes()
        entries[name]={'bytes':len(data),'sha256':_sha(data)}
    (dest/'MANIFEST_SHA256.json').write_bytes(
        m26.json_bytes({'schema':'m28-output-v1','entries':entries}))
    verify_output(dest)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inputs',nargs='+',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--thresholds-json',default=None,help='explicit M24-compatible caller limits')
    ap.add_argument('--allow-unequal-runs',action='store_true')
    args = ap.parse_args(argv)
    try:
        thresholds = None
        if args.thresholds_json:
            policy = Path(args.thresholds_json)
            if policy.is_symlink() or not policy.is_file() or policy.stat().st_size > 4096:
                raise ValueError('unsafe threshold file')
            thresholds = m27.json_object(policy.read_bytes())
        report = analyze(args.inputs, thresholds, args.allow_unequal_runs)
    except (ValueError,KeyError,OSError,TypeError,ET.ParseError) as exc:
        report = {'schema':'m28-cross-bundle-v1', 'status':'HOLD_INVALID_INPUT',
                  'release':'HOLD', 'not_a_certification':True,
                  'error_type':type(exc).__name__, 'external_p0_hold':16}
    write_once(args.out, report, args.inputs)
    return 0 if report['status']=='DESCRIPTIVE_CROSS_BUNDLE' else 1


if __name__=='__main__':
    raise SystemExit(main())
