"""M12 fail-closed local regression evidence report.

This utility never promotes an unexecuted P0 CASE-ID or approves release.
stdout and console.txt contain identical bytes. Never overwrite existing evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
from xml.etree import ElementTree as ET
from scripts.m11_gatekeeper import M10_REMAINING, get_readiness

EXPECTED_TEST_FILE = 'test_m12_fault_matrix.py'
EXPECTED_MATRIX_COUNT = 51

def analyze_junit(path: Path) -> dict:
    content = path.read_bytes()
    root = ET.fromstring(content)
    if root.tag not in ('testsuite', 'testsuites'):
        raise ValueError('unrecognized JUnit root')
    cases = list(root.iter('testcase'))
    if not cases:
        raise ValueError('JUnit contains no test cases')
    keys = []
    counts = {'failure':0, 'error':0, 'skipped':0}
    for case in cases:
        key = (case.get('classname'), case.get('name'))
        if not all(key) or key in keys:
            raise ValueError('missing or duplicate JUnit case identity')
        keys.append(key)
        for tag in counts:
            counts[tag] += sum(1 for x in case if x.tag==tag)
    if any(counts.values()):
        raise ValueError('JUnit includes failed/errored/skipped cases')
    m12 = [c for c in cases if EXPECTED_TEST_FILE in (c.get('file') or '')]
    if len(m12) != EXPECTED_MATRIX_COUNT:
        # pytest defaults omit file when --junitxml uses junit_family xunit2.
        m12 = [c for c in cases if 'test_m12_fault_matrix' in (c.get('classname') or '')]
    if len(m12) != EXPECTED_MATRIX_COUNT:
        raise ValueError('M12 contract case count not exactly 51')
    return {'sha256': hashlib.sha256(content).hexdigest(), 'total_cases': len(cases),
            'm12_fault_matrix_cases': len(m12), 'failures':0, 'errors':0, 'skipped':0}

def attest(junit: Path, root: Path) -> dict:
    result = analyze_junit(junit)
    previous = get_readiness()
    if set(previous['m10_remaining_case_ids']) != M10_REMAINING:
        raise ValueError('upstream unexecuted-case roster has drifted')
    if previous['baseline_p0_observed_unattested'] != 183:
        raise ValueError('baseline P0 evidence changed')
    files = ['tests/test_m12_fault_matrix.py','scripts/m12_audit.py',
             'suite/catalog/test_cases.jsonl','M10_REMAINING_P0.json']
    source_hashes = {}
    for f in files:
        source_hashes[f] = hashlib.sha256((root/f).read_bytes()).hexdigest()
    return {'phase':'M12', 'schema':1, 'local_regression':'PASS',
            'junit':result, 'source_sha256':source_hashes,
            'p0_prior_observed_unattested':183, 'new_case_id_passes':0,
            'p0_remaining':16,'p0_attested':0,'release':'HOLD',
            'external_gates':previous['external_gate_status'],
            'os':platform.platform(),'python':platform.python_version(),
            'note':'51 M12 regression cases are not independent P0 case-ID acceptance evidence.'}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--junit',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    a=p.parse_args(argv)
    if a.out.exists():
        raise SystemExit('HOLD: refusing evidence overwrite')
    try:
        report=attest(a.junit,a.root)
    except (ValueError,OSError,ET.ParseError,json.JSONDecodeError) as exc:
        print('M12_AUDIT=BLOCKED: '+str(exc))
        return 2
    data=(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'result.json').write_bytes(data)
    (a.out/'console.txt').write_bytes(data)
    sys.stdout.buffer.write(data)
    sys.stdout.flush()
    return 0 # audit passed, release is still HOLD

if __name__=='__main__':
    raise SystemExit(main())
