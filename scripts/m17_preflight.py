"""Fail-closed Windows prerequisite preflight for a *future* real-client test.

Never launches pymcprotocol, downloads a wheel or contacts a PLC.
A successful return only means the local environment meets the declared
prerequisites; it is not Windows attestation, a test PASS, or release approval.

Usage:
 python -m scripts.m17_preflight --wheel AUTO --output D:\\NEW_DIR \
     --expected-head <40 hex> --report D:\\NEW_DIR.preflight.json

All console bytes are written identically to the report file, including HOLD.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

from scripts.m10_wheel_gate import verify_wheel
from scripts.m14_windows_evidence import ROOT

_SHA = re.compile(r'^[0-9a-f]{40}$')
_ORIGINS = frozenset({
    'https://github.com/greatgc-flow/virtualplc',
    'git@github.com:greatgc-flow/virtualplc',
    'ssh://git@github.com/greatgc-flow/virtualplc',
})


def normalize_origin(text):
    """Only explicitly recognized GitHub remotes may pass; no local mirror spoofing."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Git origin is empty')
    result = text.strip().rstrip('/').lower()
    if result.endswith('.git'):
        result = result[:-4]
    return result


def checked_locations(output, report, wheel, root=ROOT):
    """Refuse overwriting evidence, or recording it within the public checkout."""
    root = Path(root).resolve()
    output = Path(output).resolve()
    report = Path(report).resolve()
    if output.exists():
        raise ValueError('evidence output already exists; choose a new path')
    if output == root or root in output.parents:
        raise ValueError('evidence output is inside source checkout')
    if report.exists():
        raise ValueError('preflight report already exists; no overwrite')
    if report == root or root in report.parents:
        raise ValueError('preflight report is inside public checkout')
    if report == output or output in report.parents:
        raise ValueError('preflight report must be outside the pending output directory')
    if str(wheel).upper() != 'AUTO':
        # Content is SHA-verified by verify_wheel before any later execution.
        verify_wheel(Path(wheel).resolve())
    return output, report


def _git(cmd, *, runner=subprocess.run, root=ROOT):
    result = runner(['git','-C',str(Path(root).resolve()),*cmd],
                    capture_output=True,text=True,check=False,timeout=15)
    if result.returncode != 0:
        raise ValueError('Git probe failed: ' + ' '.join(cmd))
    return result.stdout.strip()


def check_git(expected_head, *, runner=subprocess.run, root=ROOT):
    """Untrusted local claims only; reviewer must still validate machine/source."""
    if not isinstance(expected_head, str) or not _SHA.fullmatch(expected_head):
        raise ValueError('expected-head must be full lowercase 40 hex')
    top = Path(_git(['rev-parse','--show-toplevel'],runner=runner,root=root)).resolve()
    if top != Path(root).resolve():
        raise ValueError('script is not executing from its Git repository root')
    actual = _git(['rev-parse','HEAD'],runner=runner,root=root)
    if actual != expected_head:
        raise ValueError('Git HEAD differs from user-specified exact commit')
    if _git(['status','--porcelain','--untracked-files=normal'],runner=runner,root=root):
        raise ValueError('Git checkout contains tracked or untracked changes')
    origin = normalize_origin(_git(['remote','get-url','origin'],runner=runner,root=root))
    if origin not in _ORIGINS:
        raise ValueError('Git origin is not the specified greatgc-flow/VirtualPLC repository')
    return {'observed_head': actual, 'checkout_clean': True,
            'origin_repo': 'greatgc-flow/VirtualPLC',
            'independently_attested': False}


def preflight(*, wheel, output, expected_head, report, os_name=None,
              version_info=None, package_version=None, git_runner=None, root=ROOT):
    """All external probes may be injected for synthetic negative-path tests."""
    if (os_name if os_name is not None else platform.system()) != 'Windows':
        raise ValueError('Windows required; cannot certify Windows on another OS')
    version_info = version_info or sys.version_info[:2]
    if tuple(version_info[:2]) < (3,11):
        raise ValueError('Python 3.11 or newer is required')
    output, report = checked_locations(output,report,wheel,root=root)
    if package_version is None:
        package_version = importlib.metadata.version
    try:
        pytest_version = package_version('pytest')
    except importlib.metadata.PackageNotFoundError:
        raise ValueError('pytest 8.x/9.x is not installed') from None
    match = re.match(r'^(\d+)\.(\d+)(?:\.|$)',pytest_version)
    if not match or not 8 <= int(match.group(1)) < 10:
        raise ValueError('pytest 8.x/9.x required, got ' + str(pytest_version))
    git=check_git(expected_head,runner=(git_runner or subprocess.run),root=root)
    return {
        'schema': 'virtualplc.m17.preflight.v1',
        'status': 'READY_FOR_LOCAL_TEST_COLLECTION_ONLY',
        'release': 'HOLD', 'new_p0_approved': 0,
        'observed_os': 'Windows',
        'python_version': '.'.join(map(str,version_info[:2])),
        'pytest_version': pytest_version,
        'wheel_mode': 'PINNED_PYPI_AUTO' if str(wheel).upper() == 'AUTO' else 'SHA_VERIFIED_OFFLINE',
        'wheel_verified': str(wheel).upper() != 'AUTO',
        'provenance': git,
        'external_windows_attestation': False,
        'actual_client_tests_ran': False,
        'note': 'Preflight only. Run M16 tool in a fresh directory and retain all raw private evidence.',
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expected-head',required=True)
    parser.add_argument('--report',type=Path,required=True)
    opts=parser.parse_args(argv)
    # Console/report equivalence applies both to READY and HOLD outcomes.
    try:
        state=preflight(wheel=opts.wheel,output=opts.output,
                        expected_head=opts.expected_head,report=opts.report)
        rc=0
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        state={
            'schema':'virtualplc.m17.preflight.v1','status':'HOLD',
            'release':'HOLD','new_p0_approved':0,
            'reason':str(error),'actual_client_tests_ran':False,
            'external_windows_attestation':False,
        }
        rc=2
    raw=(json.dumps(state,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
    # Failure paths must not write under the public checkout, even if the
    # validated preflight never reached checked_locations().
    resolved_report = opts.report.resolve()
    resolved_output = opts.output.resolve()
    protected_root = ROOT.resolve()
    report_forbidden = (resolved_report == protected_root or
                        protected_root in resolved_report.parents or
                        resolved_report == resolved_output or
                        resolved_output in resolved_report.parents)
    if report_forbidden:
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
        return 2
    if not opts.report.exists():
        try:
            opts.report.parent.mkdir(parents=True,exist_ok=True)
            with opts.report.open('xb') as stream:
                stream.write(raw)
        except OSError:
            rc=2
    else:
        rc=2 # Never overwrite a previous report, even on otherwise READY results.
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
