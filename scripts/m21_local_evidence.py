"""M21 local loopback-only pytest runner and fail-closed evidence collector.

No user-specified arbitrary command or network endpoint. Does not certify release,
Windows, a manufacturer, or an official pymcprotocol wheel. Python >=3.11.

Usage:
  python -m scripts.m21_local_evidence run --output D:\\VPLC_M21_NEW --mode smoke
  python -m scripts.m21_local_evidence verify --output D:\\VPLC_M21_NEW

Successful local pytest is *only* a reproducible internal regression observation.
Console data printed by the runner is written byte-for-byte to console.log.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET

SCHEMA = 'virtualplc.m21.local-evidence.v1'
ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    'smoke': ('tests/test_m20_fault_plan.py', 'tests/test_m20_backlog.py'),
    'core': ('tests/test_virtual_plc.py', 'tests/test_m20_fault_plan.py',
             'tests/test_m20_backlog.py'),
}
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
SOURCE_FILES = ('scripts/m21_local_evidence.py', 'virtual_plc/server.py',
                'virtual_plc/memory.py', 'virtual_plc/protocol.py',
                'virtual_plc/faults.py', 'backlog/M20_BACKLOG.json',
                'suite/catalog/test_cases.jsonl')
_ALLOWED = frozenset({'console.log', 'pytest.xml', 'result.json'})


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def safe_output(path, *, root=ROOT):
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValueError('nonempty output path is required')
    original = Path(path)
    if not original.is_absolute():
        raise ValueError('output must be an absolute path')
    final = original.resolve()
    repo = Path(root).resolve()
    if final == repo or repo in final.parents:
        raise ValueError('public source checkout cannot contain private evidence')
    if original.is_symlink() or final.exists():
        raise ValueError('output exists or is symlink; no overwrite')
    return final


class Tee:
    """One write goes to both endpoints, *exactly* the same bytes and order."""
    def __init__(self, fileobj, console, *, maximum=MAX_OUTPUT_BYTES):
        self.fileobj, self.console, self.maximum = fileobj, console, maximum
        self.size = 0
        self.overflow = False
        self.lock = threading.Lock()

    def write(self, raw):
        if not isinstance(raw, bytes):
            raise TypeError('Tee needs bytes')
        with self.lock:
            free = max(0, self.maximum - self.size)
            part = raw[:free]
            if part:
                # Both writes are within one lock. A console I/O failure fails
                # the run rather than claiming matching evidence.
                self.fileobj.write(part)
                self.fileobj.flush()
                self.console.write(part)
                self.console.flush()
                self.size += len(part)
            if len(part) != len(raw):
                self.overflow = True


def summarize_junit(path):
    """Only all-passing, non-skipped, positive-test JUnit is locally PASS."""
    if not path.is_file() or path.is_symlink():
        raise ValueError('JUnit artifact missing')
    root = ET.parse(path).getroot()
    if root.tag not in ('testsuites','testsuite'):
        raise ValueError('JUnit root is invalid')
    cases = list(root.iter('testcase'))
    if not cases:
        raise ValueError('JUnit has no test cases')
    failures = sum(bool(c.findall('failure')) for c in cases)
    errors = sum(bool(c.findall('error')) for c in cases)
    skips = sum(bool(c.findall('skipped')) for c in cases)
    identities = [(c.get('classname'), c.get('name')) for c in cases]
    if any(not a or not b for a,b in identities) or len(set(identities)) != len(identities):
        raise ValueError('JUnit duplicate or unidentified test case')
    return {'tests':len(cases), 'passed':len(cases)-failures-errors-skips,
            'failures':failures, 'errors':errors, 'skipped':skips}


def terminate_group(child):
    if child.poll() is not None:
        return
    if os.name == 'nt':
        # taskkill /T terminates pytest's local subprocess descendants, too.
        subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],
                       capture_output=True, timeout=10, check=False)
    else:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)


def _atomic_json(path, content):
    # The final manifest is the completion marker. Hard-link publish prevents
    # overwrite even if a different writer races after the existence check.
    temp = path.with_suffix('.partial')
    try:
        with temp.open('xb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def source_fingerprints(root, mode):
    return {p:digest((Path(root)/p).read_bytes())
            for p in (*SOURCE_FILES, *SUITES[mode])}


def run(output, *, mode='smoke', timeout_seconds=90, root=ROOT,
        executable=None, console=None):
    """Run a closed allowlist suite with fresh artifacts, even on FAIL/TIMEOUT.

    Returns a summary; CLI maps result to a nonzero exit on anything but PASS.
    Unit tests may inject an executable or console; CLI does not accept these.
    """
    if mode not in SUITES:
        raise ValueError('unknown suite mode')
    if type(timeout_seconds) is not int or not (1 <= timeout_seconds <= 1800):
        raise ValueError('timeout-seconds must be an integer 1..1800')
    dest = safe_output(output, root=root)
    for relative in SUITES[mode]:
        if not (Path(root)/relative).is_file():
            raise ValueError('required test file missing: ' + relative)
    before=source_fingerprints(root,mode)
    dest.mkdir(mode=0o700, parents=True, exist_ok=False)
    target = dest/'pytest.xml'
    command = [str(executable or sys.executable), '-m', 'pytest',
               '-p', 'no:cacheprovider', *SUITES[mode], '-q',
               '--junitxml='+str(target)]
    env = os.environ.copy()
    env.pop('PYTEST_ADDOPTS', None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    env['MC_SIM_ADAPTER_MODULE'] = 'virtual_plc.test_adapter'
    output_console = console if console is not None else sys.stdout.buffer
    rc = None
    timed_out = False
    cancelled = False
    launch_error = None
    start = time.monotonic()
    with (dest/'console.log').open('xb') as log:
        tee = Tee(log, output_console)
        tee.write(('M21 mode='+mode+'; release=HOLD; running local pytest only\n').encode())
        child = None
        thread = None
        try:
            options = {'cwd':str(Path(root).resolve()), 'env':env,
                       'stdout':subprocess.PIPE, 'stderr':subprocess.STDOUT,
                       'stdin':subprocess.DEVNULL}
            if os.name == 'nt':
                options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                options['start_new_session'] = True
            child = subprocess.Popen(command, **options)
            def pump():
                try:
                    while True:
                        chunk = child.stdout.read(4096)
                        if not chunk:
                            break
                        tee.write(chunk)
                except (OSError, ValueError) as error:
                    nonlocal_error[0] = str(error)
            nonlocal_error = [None]
            thread = threading.Thread(target=pump, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + timeout_seconds
                while child.poll() is None:
                    if tee.overflow:
                        launch_error = 'console output exceeds evidence cap'
                        terminate_group(child)
                        break
                    if time.monotonic() >= deadline:
                        timed_out = True
                        terminate_group(child)
                        break
                    time.sleep(0.02)
                rc = child.wait(timeout=5)
            except KeyboardInterrupt:
                cancelled = True
                terminate_group(child)
                rc = child.wait(timeout=5)
            if thread is not None:
                thread.join(timeout=10)
                if thread.is_alive():
                    launch_error = 'stdout reader did not terminate'
            if nonlocal_error[0]:
                launch_error = 'stdout capture failed: '+nonlocal_error[0]
        except (OSError, subprocess.SubprocessError) as exc:
            launch_error = 'subprocess launch/exit failed: '+type(exc).__name__
            if child is not None:
                terminate_group(child)
        try:
            observed = summarize_junit(target)
        except (OSError, ValueError, ET.ParseError) as exc:
            observed = {'tests':0,'passed':0,'failures':0,'errors':0,'skipped':0}
            launch_error = launch_error or ('JUnit invalid: '+str(exc))
        try:
            source_unchanged=(before == source_fingerprints(root,mode))
        except OSError:
            source_unchanged=False
        status = ('PASS' if source_unchanged and rc == 0 and not timed_out and not cancelled and
                  not launch_error and not tee.overflow and
                  observed['failures'] == observed['errors'] == observed['skipped'] == 0
                  and observed['passed'] > 0 else 'HOLD')
        # Reserve a final verdict line even if test output reached its limit.
        tee.maximum = MAX_OUTPUT_BYTES + 256
        tee.write(('\nM21_LOCAL_TEST='+status+'; release=HOLD\n').encode())
    result = {
        'schema': SCHEMA, 'mode':mode, 'test_status':status, 'release':'HOLD',
        'new_external_p0_approved':0, 'commands_allowlisted':True,
        'test_selection':list(SUITES[mode]),
        'exit_code':rc, 'timeout':timed_out,'cancelled':cancelled,
        'output_limit_exceeded':tee.overflow,'runner_error':launch_error,
        'junit':observed, 'elapsed_seconds':round(time.monotonic()-start,3),
        'source_sha256':before, 'source_unchanged':source_unchanged,
        'os_name':os.name, 'python_version':list(sys.version_info[:3]),
        'not_external_attestation':True,
    }
    with (dest/'result.json').open('xb') as report:
        report.write(json_bytes(result))
    manifest = {'schema':SCHEMA, 'release':'HOLD', 'test_status':status,
                'payload':{}}
    for name in sorted(_ALLOWED):
        p=dest/name
        if p.is_file():
            raw=p.read_bytes()
            manifest['payload'][name]={'bytes':len(raw),'sha256':digest(raw)}
    _atomic_json(dest/'manifest.json', json_bytes(manifest))
    return result


def verify(output):
    """Strict read-only verification; never treats synthetic local runs as approval."""
    original = Path(output)
    directory = original.resolve()
    if original.is_symlink() or not directory.is_dir() or directory.is_symlink():
        raise ValueError('evidence output missing or symlink')
    found = list(directory.iterdir())
    if any(p.is_symlink() or not p.is_file() for p in found):
        raise ValueError('evidence contains unsafe artifact')
    names={p.name for p in found}
    if names - (_ALLOWED|{'manifest.json'}):
        raise ValueError('unregistered artifacts present')
    if 'manifest.json' not in names or 'console.log' not in names or 'result.json' not in names:
        raise ValueError('required artifacts missing')
    document=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    if not isinstance(document,dict):
        raise ValueError('invalid manifest document')
    payload=document.get('payload')
    if document.get('schema')!=SCHEMA or not isinstance(payload,dict) or set(payload)!=names-{'manifest.json'}:
        raise ValueError('manifest mismatch or omitted files')
    for name,entry in payload.items():
        raw=(directory/name).read_bytes()
        if (not isinstance(entry,dict) or type(entry.get('bytes')) is not int
                or entry['bytes']!=len(raw) or entry.get('sha256')!=digest(raw)):
            raise ValueError('artifact changed: '+name)
    result=json.loads((directory/'result.json').read_text(encoding='utf-8'))
    if (document.get('release')!='HOLD' or result.get('release')!='HOLD'
            or result.get('new_external_p0_approved')!=0
            or document.get('test_status') != result.get('test_status')
            or type(result.get('source_unchanged')) is not bool
            or not isinstance(result.get('source_sha256'),dict)
            or not result['source_sha256']):
        raise ValueError('invalid release/attestation assertion')
    if result.get('test_status')=='PASS':
        if result.get('exit_code')!=0 or 'pytest.xml' not in payload or result.get('source_unchanged') is not True:
            raise ValueError('unjustified pass')
        observed=summarize_junit(directory/'pytest.xml')
        if observed!=result.get('junit') or any(observed[x] for x in ('failures','errors','skipped')):
            raise ValueError('JUnit contradicts PASS')
    return {'schema':SCHEMA,'integrity':'PASS','test_status':result.get('test_status'),
            'release':'HOLD','external_p0_attested':0,'payload_files':len(payload)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('run');p.add_argument('--output',required=True)
    p.add_argument('--mode',choices=sorted(SUITES),default='smoke')
    p.add_argument('--timeout-seconds',type=int,default=90)
    p=sub.add_parser('verify');p.add_argument('--output',required=True)
    options=parser.parse_args(argv)
    try:
        if options.action=='run':
            report=run(options.output,mode=options.mode,
                       timeout_seconds=options.timeout_seconds)
            verified=verify(options.output)
            return 0 if report['test_status']=='PASS' and verified['integrity']=='PASS' else 2
        data=verify(options.output)
        sys.stdout.buffer.write(json_bytes(data))
        return 0
    except (ValueError,OSError,ET.ParseError,subprocess.SubprocessError,KeyboardInterrupt) as exc:
        sys.stderr.write('M21_LOCAL_EVIDENCE=HOLD: '+str(exc)+'\n')
        return 2


if __name__=='__main__':
    raise SystemExit(main())
