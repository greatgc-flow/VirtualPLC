"""Reproducible separate-phase TDD launcher; console output mirrored to evidence.

Use on isolated loopback-only test machines. Does not trigger GitHub Actions.
M5 never signs or promotes a release based on its own test results.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
import argparse
import json
import os
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_one(label, args, env, logdir):
    log = logdir / (label + '.log')
    with log.open('w', encoding='utf-8') as evidence:
        print('COMMAND: '+subprocess.list2cmdline(args), flush=True)
        evidence.write('COMMAND: '+subprocess.list2cmdline(args)+'\n')
        proc = subprocess.Popen(args, cwd=ROOT, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='replace')
        for line in proc.stdout:
            sys.stdout.write(line)
            evidence.write(line)
        return proc.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='evidence/m5_run',
                        help='Evidence directory, preferably outside the repository')
    parser.add_argument('--fast', action='store_true', help='omit 45 TCP integration cases')
    args = parser.parse_args()
    dest = Path(args.output)
    if not dest.is_absolute():
        dest = ROOT / dest
    dest.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, MC_SIM_ADAPTER_MODULE='virtual_plc.test_adapter')
    phase = [('regression', ['tests/test_virtual_plc.py', 'tests/test_m4_p0_case_ids_v2.py',
                            'suite/tests/domain', 'suite/tests/static']),
             ('new_cases', ['tests/test_m5_p0_case_ids.py', 'tests/test_m5_governance.py'])]
    if not args.fast:
        phase.append(('tcp', ['suite/tests/live/test_wire_cases.py']))
    files = []
    results = {}
    for label, paths in phase:
        xml = dest / (label + '.xml')
        command = [sys.executable, '-m', 'pytest'] + paths + ['-q', '--junitxml=' + str(xml)]
        if label == 'tcp':
            command.extend(['--server-cmd', 'python -m virtual_plc --host {host} --port {port}'])
        rc = run_one(label, command, env, dest)
        results[label] = rc
        if rc != 0:
            break
        files.append(xml)
    if all(v == 0 for v in results.values()):
        combined = ET.Element('testsuites')
        for file in files:
            x = ET.parse(file).getroot()
            for suite in x.findall('.//testsuite'):
                combined.append(suite)
        xml = dest / 'combined.xml'
        ET.ElementTree(combined).write(xml, encoding='utf-8', xml_declaration=True)
        rc = run_one('gate_report', [sys.executable, 'scripts/gate_report.py',
                         '--junit', str(xml)], env, dest)
        results['gate_report'] = rc
    record = {'date_utc':datetime.now(timezone.utc).isoformat(),
              'python':sys.version, 'os': platform.platform(), 'phase_exit_codes':results,
              'release':'HOLD', 'autonomous_approval':False}
    (dest/'run_meta.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print('Evidence:',dest)
    return 0 if results and all(x == 0 for x in results.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
