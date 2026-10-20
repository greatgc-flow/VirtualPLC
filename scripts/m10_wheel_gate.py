"""Fail-closed, opt-in real-client gate: run pytest only with verified PyPI wheel.

All stdout and stderr from the runner is echoed to console and recorded byte-for-byte
in a UTF-8 evidence log. No production endpoints and no remote PLC connections.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

EXPECTED = '614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6'
WHEEL = 'pymcprotocol-0.3.0-py3-none-any.whl'


def verify_wheel(path):
    path = Path(path)
    if not path.is_file() or path.name != WHEEL:
        raise ValueError('missing expected pinned pymcprotocol wheel')
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != EXPECTED:
        raise ValueError('wheel SHA-256 mismatch: refusing to run')
    return {'wheel_filename': WHEEL, 'wheel_sha256': actual,
            'client_version': '0.3.0', 'source': 'user-provided SHA-pinned wheel'}


def run(wheel, evidence_dir):
    evidence_dir = Path(evidence_dir)
    if evidence_dir.exists():
        raise FileExistsError('evidence output already exists: no overwrite allowed')
    # Do not create evidence before input checks complete.
    info = verify_wheel(wheel)
    evidence_dir.mkdir(parents=True)
    package_dir = evidence_dir / '_pinned_package'
    package_dir.mkdir()
    src_root = Path(__file__).resolve().parents[1]
    report = {'status': 'NOT_RUN', 'release': 'HOLD',
              'python': sys.version, 'interpreter': sys.executable,
              **info}
    commands = [
        [sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps',
         '--only-binary=:all:', '--target', str(package_dir), str(Path(wheel).resolve())],
        [sys.executable, '-m', 'pytest', str(src_root/'tests'/'compat'), '-q',
         '--junitxml=' + str(evidence_dir/'pymc_junit.xml')],
    ]
    env = dict(os.environ)
    env['PYTHONPATH'] = str(package_dir) + os.pathsep + str(src_root)
    env['VIRTUALPLC_RUN_PYMC'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    log = bytearray()
    for idx, cmd in enumerate(commands):
        try:
            completed = subprocess.run(cmd, cwd=str(src_root), env=env,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, timeout=120)
            output = completed.stdout or b''
            log.extend(output)
            sys.stdout.buffer.write(output)
            sys.stdout.buffer.flush()
            rc = completed.returncode
        except subprocess.TimeoutExpired as exc:
            partial = exc.stdout or b''
            log.extend(partial)
            sys.stdout.buffer.write(partial)
            sys.stdout.buffer.flush()
            report['status'] = 'TIMEOUT'
            report['failed_step'] = idx
            break
        except Exception as exc:
            report['status'] = 'ERROR'
            report['error'] = str(exc)
            break
        if rc != 0:
            report['status'] = 'FAIL'
            report['failed_step'] = idx
            report['exit_code'] = rc
            break
    else:
        report['status'] = 'PASS_LOCAL_UNATTESTED'
    status_line = ('M10_CLIENT_RESULT='+report['status']+'\n').encode('utf-8')
    log.extend(status_line)
    sys.stdout.buffer.write(status_line)
    sys.stdout.buffer.flush()
    (evidence_dir/'console.log').write_bytes(log)
    report['stdout_sha256'] = hashlib.sha256(log).hexdigest()
    report['tests_authoritative'] = False
    report['windows_runner_observed'] = sys.platform == 'win32'
    report['windows_independent_evidence'] = False  # only externally reviewed evidence can attest
    (evidence_dir/'result.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    return 0 if report['status'] == 'PASS_LOCAL_UNATTESTED' else 2


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--wheel', required=True)
    p.add_argument('--evidence-dir', required=True)
    a = p.parse_args()
    try:
        return run(a.wheel, a.evidence_dir)
    except (OSError, ValueError) as exc:
        print('M10_CLIENT_GATE=NOT_RUN (' + str(exc) + ')')
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
