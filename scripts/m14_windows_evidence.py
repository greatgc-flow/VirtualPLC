"""M14 fail-closed evidence packaging for REAL pinned pymcprotocol on Windows.

Runs only against a local 127.0.0.1 simulator; does not contact a physical PLC.
No release approvals are given by this program. Standard library only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import zipfile

from scripts.m10_wheel_gate import verify_wheel
from scripts.m13_evidence_gate import verify_client_junit

ROOT = Path(__file__).resolve().parents[1]
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_client_run(folder):
    """Verify provenance *claims* and integrity, not independent authenticity."""
    folder = Path(folder)
    report_path, log_path, junit_path = (folder / x for x in
        ('result.json', 'console.log', 'pymc_junit.xml'))
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if not isinstance(report, dict) or report.get('status') != 'PASS_LOCAL_UNATTESTED':
        raise ValueError('client runner did not report full successful execution')
    if report.get('tests_authoritative') is not False:
        raise ValueError('client result improperly claims independent approval')
    if report.get('wheel_sha256') != '614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6':
        raise ValueError('client report wheel SHA differs from official pin')
    if sha256(log_path) != report.get('stdout_sha256'):
        raise ValueError('client console SHA-256 mismatch')
    parsed = verify_client_junit(junit_path)
    return {
        'client_state': 'SIX_LOCAL_RESULTS_INTACT_NOT_ATTESTED',
        'client_case_ids': parsed['case_ids'],
        'client_junit_sha256': parsed['junit_sha256'],
        'console_sha256': sha256(log_path),
        'result_json_sha256': sha256(report_path),
        'claimed_windows_runner': report.get('windows_runner_observed') is True,
        'independent_windows_attestation': False,
    }


def local_git_provenance(root, expected_head):
    """Git metadata is an environmental claim; reviewer must compare remotely."""
    if not SHA_PATTERN.fullmatch(expected_head):
        raise ValueError('expected commit must be a lowercase 40-char SHA')
    cmds = [
        ['git', '-C', str(root), 'rev-parse', 'HEAD'],
        ['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=normal'],
    ]
    actual = subprocess.run(cmds[0], capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    changes = subprocess.run(cmds[1], capture_output=True, text=True, timeout=10, check=True).stdout
    if actual != expected_head:
        raise ValueError('local checked-out HEAD does not equal independently supplied expected HEAD')
    if changes.strip():
        raise ValueError('Git checkout is dirty; evidence provenance ambiguous')
    return {'claimed_local_head': actual, 'working_tree_clean_at_start': True,
            'externally_verified_head': False}


def package_run(wheel, output, expected_head, *, require_windows=True, invoke=None):
    """Provide run injection only for offline tests; never permit alternate client implementation."""
    if require_windows and platform.system() != 'Windows':
        raise ValueError('real Windows evidence must execute on Windows')
    wheel = Path(wheel).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('destination exists: refusing overwrite')
    if output.is_relative_to(ROOT.resolve()):
        raise ValueError('place evidence OUTSIDE the public repository')
    wheel_meta = verify_wheel(wheel)
    provenance = local_git_provenance(ROOT, expected_head)
    output.mkdir(parents=True, exist_ok=False)
    evidence = output / 'client_run'
    cmd = [sys.executable, '-m', 'scripts.m10_wheel_gate', '--wheel', str(wheel),
           '--evidence-dir', str(evidence)]
    runner = invoke or (lambda args: subprocess.run(args, cwd=str(ROOT),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=180, check=False))
    try:
        completed = runner(cmd)
        raw = completed.stdout or b''
        if isinstance(raw, str):
            raw = raw.encode('utf-8')
        (output / 'runner_stdout.bin').write_bytes(raw)
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
        if completed.returncode != 0:
            raise ValueError('real client runner failed; no PASS evidence')
        verified = inspect_client_run(evidence)
        if not verified['claimed_windows_runner']:
            raise ValueError('runner did not report Windows OS')
        manifest = {
          'schema': 'virtualplc.m14.client-evidence.v1',
          'conclusion': 'LOCAL_CLIENT_PASS_INDEPENDENT_ATTESTATION_PENDING',
          'release': 'HOLD', 'p0_new_independently_attested': 0,
          'wheel_sha256': wheel_meta['wheel_sha256'],
          'observed_os': platform.system(), 'python_version': platform.python_version(),
          'provenance': provenance, 'client': verified,
          'files': {},
        }
        for child in sorted(output.rglob('*')):
            if child.is_file():
                rel = child.relative_to(output).as_posix()
                manifest['files'][rel] = {'bytes': child.stat().st_size, 'sha256': sha256(child)}
        encoded = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode('utf-8')
        (output / 'M14_EVIDENCE.json').write_bytes(encoded)
        with zipfile.ZipFile(str(output) + '.zip', mode='x', compression=zipfile.ZIP_DEFLATED) as z:
            for child in sorted(output.rglob('*')):
                if child.is_file():
                    z.write(child, child.relative_to(output))
        return manifest
    except BaseException:
        # Deliberately keep incomplete artifacts for post-mortem, never call them PASS.
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wheel', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--expected-head', required=True)
    a = p.parse_args(argv)
    try:
        result = package_run(a.wheel, a.output, a.expected_head)
    except (OSError, ValueError, subprocess.SubprocessError, TimeoutError) as exc:
        print('M14_CLIENT=HOLD: ' + str(exc))
        return 2
    print('M14_CLIENT=' + result['conclusion'])
    return 0  # Successful evidence capture only; release stays HOLD.


if __name__ == '__main__':
    raise SystemExit(main())
