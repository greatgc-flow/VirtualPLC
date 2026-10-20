"""M26 bounded local multi-run orchestrator for VirtualPLC.

Independent external P0 gates remain HOLD. Runs M23 subprocess on loopback only,
checks each result via M25 verifier, aggregates descriptive observations only.
Always creates a NEW output directory outside the source tree. Records the exact
bytes echoed to stdout in output/console.log. Partial/failing runs remain intact.

Example:
 python -m scripts.m26_multi_run --out D:\\VPLC_M26_001 --runs 3 --duration 0.5

No production PLC endpoints, automatic retry, SLA acceptance or background tasks.
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
import time
import xml.etree.ElementTree as ET

from scripts import m23_recovery_soak as m23
from scripts import m25_replicates as m25

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_FILES = tuple(sorted(set(m23.SOURCE_FILES) | {
    'scripts/m25_replicates.py', 'scripts/m26_multi_run.py',
}))
MAX_RUNS = 30
MIN_RUNS = 3
MAX_LOG_BYTES = 250_000
MAX_TIMEOUT_SECONDS = 240.0


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def source_fingerprint():
    """Hash every relevant source file, rejecting symlinks and missing sources."""
    hashes = {}
    for rel in PROVENANCE_FILES:
        p = ROOT / rel
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 3_000_000:
            raise ValueError('missing/unsafe source: ' + rel)
        hashes[rel] = digest(p.read_bytes())
    return hashes


def validate_options(runs=3, clients=2, duration=0.5, max_cycles=30,
                     delay_ms=20, timeout=30):
    if type(runs) is not int or not MIN_RUNS <= runs <= MAX_RUNS:
        raise ValueError('runs must be integer 3..30')
    m23.validate_options(clients=clients, duration=duration, max_cycles=max_cycles)
    if type(delay_ms) is not int or not 1 <= delay_ms <= 500:
        raise ValueError('delay_ms must be integer 1..500')
    if (type(timeout) not in (int, float) or not 5 <= timeout <= MAX_TIMEOUT_SECONDS
            or timeout < duration + 4):
        raise ValueError('timeout must be finite 5..240s and >= duration+4s')
    return dict(runs=runs, clients=clients, duration=duration,
                max_cycles=max_cycles, delay_ms=delay_ms, timeout=timeout)


def fresh_destination(out):
    """Prevent clobbering, source-tree modification and parent symlink bypass."""
    original = Path(out).absolute()
    if original == ROOT or ROOT in original.parents:
        raise ValueError('output must be outside source tree')
    # Check all existing ancestors; don't follow attacker-created symlink paths.
    for path in (original, *original.parents):
        if path.is_symlink():
            raise ValueError('symlink output path refused')
    if original.exists():
        raise FileExistsError('existing output refused')
    original.mkdir(parents=True, exist_ok=False)
    return original


def kill_process_group(proc):
    """Terminate server descendants on timeout; local subprocess only."""
    if proc.poll() is not None:
        return
    if os.name == 'nt':
        # /T includes descendants; command arguments are not taken from the user.
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5, check=False)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def run_child(out, options):
    """Execute one fixed command, capture bounded stdout/stderr and return detail."""
    command = [sys.executable, '-m', 'scripts.m23_recovery_soak',
               '--out', str(out), '--clients', str(options['clients']),
               '--duration', str(options['duration']),
               '--max-cycles', str(options['max_cycles']),
               '--delay-ms', str(options['delay_ms'])]
    child_env = dict(os.environ)
    child_env['PYTHONUNBUFFERED'] = '1'
    proc = None
    started = time.monotonic()
    try:
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        proc = subprocess.Popen(command, cwd=str(ROOT), env=child_env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, creationflags=flags,
                                start_new_session=(os.name != 'nt'))
        try:
            stdout, _ = proc.communicate(timeout=options['timeout'])
            return_code = proc.returncode
            outcome = 'EXECUTED' if return_code == 0 else 'CHILD_FAILED'
        except subprocess.TimeoutExpired:
            kill_process_group(proc)
            # communicate once more to drain bounded OS pipe after kill.
            stdout, _ = proc.communicate(timeout=5)
            return_code = proc.returncode
            outcome = 'TIMEOUT'
    except (OSError, subprocess.TimeoutExpired) as exc:
        if proc is not None:
            kill_process_group(proc)
        stdout = ('SPAWN_OR_CLEANUP_FAILED: ' + type(exc).__name__ + '\n').encode()
        return_code, outcome = None, 'SPAWN_FAILED'
    except BaseException:
        # KeyboardInterrupt/SystemExit must never orphan a live server child.
        if proc is not None:
            kill_process_group(proc)
        raise
    if len(stdout) > MAX_LOG_BYTES:
        # Never treat truncated logs as successful evidence.
        outcome = 'OVERSIZE_LOG'
        stdout = stdout[:MAX_LOG_BYTES]
    return {'status':outcome, 'return_code':return_code,
            'elapsed_s':round(time.monotonic()-started,6), 'stdout':stdout}


def _junit(results, status):
    suite = ET.Element('testsuite', name='m26_local_orchestrator',
                       tests=str(len(results)+1),
                       failures=str(sum(x['status']!='VERIFIED' for x in results)
                                    + (status!='OBSERVED_NOT_CERTIFIED')))
    for entry in results:
        case = ET.SubElement(suite, 'testcase', classname='m26',
                             name='repeat_{:02d}'.format(entry['run']))
        if entry['status']!='VERIFIED':
            ET.SubElement(case, 'failure', message=entry['status'])
    last = ET.SubElement(suite, 'testcase', classname='m26', name='aggregate')
    if status!='OBSERVED_NOT_CERTIFIED':
        ET.SubElement(last, 'failure', message=status)
    return ET.tostring(suite, encoding='utf-8', xml_declaration=True)


def verify_output(folder):
    """Check the final file inventory and all digests (integrity, not authenticity)."""
    d = Path(folder)
    manifest=json.loads((d/'MANIFEST_SHA256.json').read_text(encoding='utf-8'))
    if manifest.get('schema')!='m26-local-evidence-v1' or not isinstance(manifest.get('files'),list):
        raise ValueError('invalid M26 manifest')
    entries = manifest['files']
    inventory = {str(p.relative_to(d).as_posix()) for p in d.rglob('*') if p.is_file()}
    expected={e['path'] for e in entries}
    if inventory != expected|{'MANIFEST_SHA256.json'} or len(expected)!=len(entries):
        raise ValueError('manifest inventory mismatch')
    for e in entries:
        name=e['path']
        if (not isinstance(name,str) or not name or name.startswith('/')
            or '\\' in name or ':' in name or '..' in Path(name).parts):
            raise ValueError('unsafe manifest path')
        file=d/name
        if file.is_symlink() or not file.is_file() or file.stat().st_size!=e['bytes'] or digest(file.read_bytes())!=e['sha256']:
            raise ValueError('manifest digest mismatch: '+name)
    return len(entries)


def run(out, runs=3, clients=2, duration=0.5, max_cycles=30,
        delay_ms=20, timeout=30, child_runner=None, emit_bytes=None):
    """Orchestrate multiple local M23 runs. No unattended retries on ambiguity.

    child_runner and emit_bytes are dependency injection points for tests. The
    runner receives a fresh run folder and validated options and returns a dict.
    """
    options=validate_options(runs,clients,duration,max_cycles,delay_ms,timeout)
    pre_hash=source_fingerprint()  # before output creation
    root=fresh_destination(out)
    child_runner=child_runner or run_child
    emit_bytes=emit_bytes or (lambda data: (sys.stdout.buffer.write(data),sys.stdout.buffer.flush()))
    logs=bytearray()
    results=[]
    summary=None
    reason=None
    status='HOLD_EXECUTION_INCOMPLETE'
    def emit(line):
        raw=(line+'\n').encode('utf-8')
        emit_bytes(raw)
        logs.extend(raw)
    try:
        emit('M26 LOCAL BOUNDED REPEATS; RELEASE=HOLD; NOT CERTIFIED')
        (root/'runs').mkdir(exist_ok=False)
        (root/'run_stdout').mkdir(exist_ok=False)
        for n in range(1,runs+1):
            if source_fingerprint()!=pre_hash:
                reason='SOURCE_CHANGED_BEFORE_RUN';break
            child_out=root/'runs'/'{:02d}'.format(n)
            response=child_runner(child_out, options)
            raw=response.get('stdout',b'')
            if not isinstance(raw,bytes) or len(raw)>MAX_LOG_BYTES:
                raise ValueError('child output must be bounded bytes')
            (root/'run_stdout'/'{:02d}.log'.format(n)).write_bytes(raw)
            result={'run':n,'child_status':response.get('status'),
                    'return_code':response.get('return_code'),
                    'elapsed_s':response.get('elapsed_s'),
                    'stdout_sha256':digest(raw),'status':'HOLD',
                    'verification_error':None}
            if response.get('status')=='EXECUTED' and response.get('return_code')==0:
                try:
                    m25.verify_run(child_out)
                    if source_fingerprint()!=pre_hash:
                        raise ValueError('source changed in flight')
                    result['status']='VERIFIED'
                except (ValueError,OSError,KeyError,TypeError) as exc:
                    result['verification_error']=type(exc).__name__
            results.append(result)
            emit('RUN {:02d}/{} STATUS={} CHILD={}'.format(n,runs,result['status'],result['child_status']))
            if result['status']!='VERIFIED':
                reason='RUN_NOT_VERIFIED';break
        if reason is None and len(results)==runs:
            if source_fingerprint()!=pre_hash:
                reason='SOURCE_CHANGED_BEFORE_SUMMARY'
            else:
                try:
                    summary=m25.analyze([root/'runs'/'{:02d}'.format(i) for i in range(1,runs+1)])
                    if summary['status']!='REPEATED_OBSERVATIONS_ONLY':
                        reason='INCOMPARABLE_OBSERVATIONS'
                    elif source_fingerprint()!=pre_hash:
                        reason='SOURCE_CHANGED_DURING_SUMMARY'
                    else:
                        status='OBSERVED_NOT_CERTIFIED'
                except (ValueError,OSError,KeyError,TypeError) as exc:
                    reason='SUMMARY_'+type(exc).__name__
        if reason:
            status='HOLD_'+reason
    except (Exception, KeyboardInterrupt) as exc:
        status='HOLD_INTERRUPTED' if isinstance(exc,KeyboardInterrupt) else 'HOLD_INTERNAL_ERROR'
        reason=type(exc).__name__
    finally:
        # Fail-closed when source differs while finalizing even if runs succeeded.
        try:
            stable=source_fingerprint()==pre_hash
        except (OSError,ValueError):
            stable=False
        if not stable:
            status='HOLD_SOURCE_CHANGED'
        emit('STATUS={} RELEASE=HOLD'.format(status))
        (root/'console.log').write_bytes(logs)
        final={'schema':'m26-orchestration-v1','status':status,'release':'HOLD',
               'not_a_certification':True,'source_unchanged':stable,
               'source_sha256':pre_hash,'options':options,'attempted':len(results),
               'requested':runs,'runs':results,'reason':reason,
               'descriptive_summary':summary if status=='OBSERVED_NOT_CERTIFIED' else None,
               'external_p0_remaining':16,'independent_approval':False}
        (root/'report.json').write_bytes(json_bytes(final))
        (root/'junit.xml').write_bytes(_junit(results,status))
        manifest=[]
        for file in sorted(p for p in root.rglob('*') if p.is_file()):
            name=file.relative_to(root).as_posix()
            if name=='MANIFEST_SHA256.json':continue
            data=file.read_bytes()
            manifest.append({'path':name,'bytes':len(data),'sha256':digest(data)})
        (root/'MANIFEST_SHA256.json').write_bytes(json_bytes({'schema':'m26-local-evidence-v1','files':manifest}))
        verify_output(root)
    return final


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True)
    p.add_argument('--runs',type=int,default=3)
    p.add_argument('--clients',type=int,default=2)
    p.add_argument('--duration',type=float,default=0.5)
    p.add_argument('--max-cycles',type=int,default=30)
    p.add_argument('--delay-ms',type=int,default=20)
    p.add_argument('--timeout',type=float,default=30)
    args=p.parse_args(argv)
    try:
        report=run(**vars(args))
    except (OSError,ValueError) as exc:
        p.error(str(exc))
    return 0 if report['status']=='OBSERVED_NOT_CERTIFIED' else 1


if __name__=='__main__':
    raise SystemExit(main())
