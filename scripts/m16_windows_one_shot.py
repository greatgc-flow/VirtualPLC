"""Explicit opt-in Windows one-shot real-client evidence capture, fail-closed.

On an isolated Windows development PC with Git, Python>=3.11 and pytest installed:
  python -m scripts.m16_windows_one_shot --wheel AUTO --output D:\\new-run --expected-head <40hex>
  python -m scripts.m16_windows_one_shot --wheel C:\\path\\pymcprotocol-0.3.0-py3-none-any.whl --output D:\\new-run --expected-head <40hex>

AUTO fetches *only* pymcprotocol==0.3.0 from https://pypi.org/simple/,
then pins the byte hash before execution. Does not contact real PLC IPs.
Console bytes from the download are persisted verbatim into the output folder.
Never uploads evidence to PUBLIC GitHub. Never asserts independent approval.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
from scripts.m10_wheel_gate import WHEEL, verify_wheel
from scripts.m14_windows_evidence import package_run, ROOT

MIN_PYTHON = (3,11)


def run(*, wheel, output, expected_head, invoke=None, os_name=None):
    if (os_name or platform.system()) != 'Windows':
        raise ValueError('Windows execution required; do not treat a simulator as attestation')
    if sys.version_info[:2] < MIN_PYTHON:
        raise ValueError('Python >=3.11 required')
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('destination exists; refusing overwrite')
    if output == ROOT.resolve() or ROOT.resolve() in output.parents:
        raise ValueError('evidence must remain outside the public source repository')
    if len(expected_head)!=40 or any(c not in '0123456789abcdef' for c in expected_head):
        raise ValueError('expected-head must be a full lowercase 40-character commit SHA')
    # Download is opt-in only. Never mutate the source checkout.
    output.mkdir(parents=True,exist_ok=False)
    if str(wheel).upper() == 'AUTO':
        wheel_dir=output/'official_wheel'
        wheel_dir.mkdir()
        cmd=[sys.executable, '-m','pip','download','--disable-pip-version-check',
             '--no-deps','--only-binary=:all:', '--index-url','https://pypi.org/simple/',
             '--dest',str(wheel_dir),'pymcprotocol==0.3.0']
        completed=(invoke or (lambda x: subprocess.run(x, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=120, check=False)))(cmd)
        raw=completed.stdout or b''
        if isinstance(raw, str):raw=raw.encode('utf-8')
        (output/'wheel_download_stdout.bin').write_bytes(raw)
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
        if completed.returncode!=0:
            raise ValueError('pinned PyPI wheel download failed; artifacts retained')
        found=list(wheel_dir.iterdir())
        if len(found)!=1 or found[0].name!=WHEEL:
            raise ValueError('unexpected download entries, refusing execution')
        wheel=found[0]
    # Explicit path also remains opt-in and must match the *official* digest.
    wheel=Path(wheel).resolve()
    verify_wheel(wheel)
    manifest=package_run(wheel,output/'M14_CLIENT_RUN',expected_head,
                         require_windows=True)
    report={
        'schema':'virtualplc.m16.one-shot.v1',
        'result':'LOCAL_CLIENT_RUN_INDEPENDENT_ATTESTATION_REQUIRED',
        'release':'HOLD', 'approved_new_p0':0,
        'client_zip':str(output/'M14_CLIENT_RUN.zip'),
        'observed_os':'Windows','wheel_sha256':manifest['wheel_sha256'],
        'caller_supplied_git_head':expected_head,
    }
    (output/'M16_INSTRUCTIONS.txt').write_text(
        'Run scripts.m16_provenance_gate on M14_CLIENT_RUN.zip to inspect bytes.\n'
        'Do not upload this directory, raw OS fingerprints or wheel to PUBLIC GitHub.\n'
        'An independent reviewer must validate actual OS, origin and exact device model.\n',
        encoding='utf-8')
    (output/'M16_RESULT.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    # M14 subprocess emits exactly the bytes stored in runner_stdout.bin.
    # Concatenate in screen order: optional download, runner, final status.
    pieces=[]
    for item in ('wheel_download_stdout.bin','M14_CLIENT_RUN/runner_stdout.bin'):
        current=output/item
        if current.exists():
            pieces.append(current.read_bytes())
    pieces.append(('M16_WINDOWS='+report['result']+'\n').encode('utf-8'))
    (output/'M16_CONSOLE.bin').write_bytes(b''.join(pieces))
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-head', required=True)
    args=parser.parse_args(argv)
    try:
        report=run(wheel=args.wheel, output=args.output,expected_head=args.expected_head)
    except (OSError,ValueError,subprocess.SubprocessError,TimeoutError) as exc:
        print('M16_WINDOWS=HOLD: '+str(exc))
        return 2
    print('M16_WINDOWS='+report['result'])
    return 0 # Successful collection only; release remains HOLD.


if __name__=='__main__':
    raise SystemExit(main())
