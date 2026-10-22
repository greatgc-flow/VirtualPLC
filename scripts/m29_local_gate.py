"""M29 offline, bounded grouped pytest and CASE-ID audit; never a release approval.

Only test_*.py from tests/, suite/tests/static and suite/tests/domain.
No wheel install, no remote PLC I/O, no automated CI, no implicit PASS on SKIP.
Exact terminal bytes are mirrored into console.log. Python >= 3.11.
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
import tempfile
import time
import xml.etree.ElementTree as ET

MAX_GROUPS=12
MAX_FILES=160
MAX_OUTPUT=2_000_000


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode('utf-8')


def find_tests(root):
    paths=sorted((root/'tests').glob('test_*.py'))
    for subdir in ('suite/tests/static','suite/tests/domain'):
        folder=root/subdir
        if folder.is_dir():
            paths+=sorted(folder.glob('test_*.py'))
    if not paths or len(paths)>MAX_FILES:
        raise ValueError('empty or excessive test inventory')
    if any(p.is_symlink() or not p.is_file() or root not in p.resolve().parents for p in paths):
        raise ValueError('unsafe source test path')
    return paths


def fingerprint(root,tests):
    candidates=set(tests)
    for dir_name in ('scripts','virtual_plc','tests','suite'):
        directory=root/dir_name
        if directory.is_dir():
            candidates.update(directory.rglob('*.py'))
    for rel in ('suite/catalog/test_cases.jsonl','backlog/M20_BACKLOG.json','pyproject.toml'):
        p=root/rel
        if p.is_file():
            candidates.add(p)
    if len(candidates)>600:
        raise ValueError('unbounded source inventory')
    result={}
    for file in sorted(candidates):
        if file.is_symlink() or not file.is_file() or file.stat().st_size>MAX_OUTPUT:
            raise ValueError('unsafe source')
        result[file.relative_to(root).as_posix()]=digest(file.read_bytes())
    return result


def group_files(paths,groups=6):
    if type(groups) is not int or not 1<=groups<=MAX_GROUPS or not paths or len(set(paths))!=len(paths):
        raise ValueError('invalid group plan')
    count=min(groups,len(paths))
    width=(len(paths)+count-1)//count
    return [paths[i:i+width] for i in range(0,len(paths),width)]


def fresh(out,checkout):
    target=Path(out).absolute()
    if target==checkout or checkout in target.parents or target in checkout.parents:
        raise ValueError('evidence path overlaps checkout')
    if target.exists() or any(p.is_symlink() for p in (target,*target.parents)):
        raise ValueError('evidence path exists/is symlink')
    target.mkdir(parents=True,exist_ok=False)
    return target


def terminate(proc):
    if proc.poll() is not None:
        return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],
                       stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,timeout=8,check=False)
    else:
        try:
            os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=8)


def execute(argv,root,timeout):
    """Bound output on disk and time; kill descendants; no automatic retry."""
    flags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
    with tempfile.TemporaryFile(mode='w+b') as capture:
        proc=subprocess.Popen(argv,cwd=str(root),stdin=subprocess.DEVNULL,
                              stdout=capture,stderr=subprocess.STDOUT,
                              creationflags=flags,start_new_session=os.name!='nt')
        begun=time.monotonic()
        state='FINISHED'
        try:
            while proc.poll() is None:
                if os.fstat(capture.fileno()).st_size>MAX_OUTPUT:
                    state='OVERSIZE'
                    terminate(proc)
                    break
                if time.monotonic()-begun>=timeout:
                    state='TIMEOUT'
                    terminate(proc)
                    break
                time.sleep(0.05)
        except BaseException:
            terminate(proc)
            raise
        capture.seek(0)
        output=capture.read(MAX_OUTPUT+1)
        if len(output)>MAX_OUTPUT:
            state='OVERSIZE'
            output=output[:MAX_OUTPUT]
    return state,proc.returncode,output


def parse_junit(raw):
    if len(raw)>MAX_OUTPUT or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('unsafe JUnit XML')
    try:
        root=ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError('invalid JUnit XML') from exc
    if root.tag not in ('testsuite','testsuites'):
        raise ValueError('unexpected JUnit root')
    cases=list(root.iter('testcase'))
    if not cases:
        raise ValueError('JUnit with zero test nodes')
    counts={'pass':0,'fail':0,'error':0,'skip':0}
    nodes=set()
    owners={}
    for case in cases:
        key=case.get('classname'),case.get('name')
        if not all(type(v) is str and v for v in key) or key in nodes:
            raise ValueError('duplicate or missing test-node identity')
        nodes.add(key)
        tags=[kind for kind in ('failure','error','skipped') if case.find(kind) is not None]
        if len(tags)>1:
            raise ValueError('conflicting JUnit outcome')
        status={'failure':'fail','error':'error','skipped':'skip'}.get(tags[0] if tags else '', 'pass')
        counts[status]+=1
        ids=[p.get('value') for p in case.findall('./properties/property') if p.get('name')=='case_id']
        if len(ids)>1:
            raise ValueError('multiple canonical CASE-ID annotations')
        if ids:
            cid=ids[0]
            if not isinstance(cid,str) or len(cid)!=9 or not cid.startswith('CASE-') or not cid[5:].isdigit():
                raise ValueError('invalid canonical CASE-ID')
            if cid in owners:
                raise ValueError('duplicate canonical CASE-ID')
            owners[cid]=status
    for suite in root.iter('testsuite'):
        scoped=list(suite.iter('testcase'))
        declared={'tests':len(scoped),'failures':sum(c.find('failure') is not None for c in scoped),
                  'errors':sum(c.find('error') is not None for c in scoped),
                  'skipped':sum(c.find('skipped') is not None for c in scoped)}
        for name,n in declared.items():
            val=suite.get(name)
            if val is None or not val.isdecimal() or int(val)!=n:
                raise ValueError('JUnit count/status contradiction: '+name)
    return {'counts':counts,'nodes':nodes,'cases':owners}


def audit_p0(root,seen):
    catalog=root/'suite/catalog/test_cases.jsonl'
    backlog=root/'backlog/M20_BACKLOG.json'
    if not catalog.is_file() or not backlog.is_file():
        return {'status':'NOT_AVAILABLE','observed_pass':len(seen)}
    entries=[json.loads(row) for row in catalog.read_text(encoding='utf-8').splitlines() if row.strip()]
    all_ids=[row.get('id') for row in entries]
    if len(all_ids)!=len(set(all_ids)):
        raise ValueError('catalog duplicate ID')
    expected={row['id'] for row in entries if row.get('phase')=='P0'}
    gates=json.loads(backlog.read_text(encoding='utf-8'))
    external=[item for gate in gates['external_dependencies'] for item in gate['case_ids']]
    if len(external)!=len(set(external)) or set(external)-expected or set(seen)-expected:
        raise ValueError('invalid external backlog or JUnit CASE-ID')
    observed={name for name,status in seen.items() if status=='pass'}
    missing=sorted(expected-observed)
    return {'status':'MATCHED_EXTERNAL_BACKLOG' if set(missing)==set(external)
            else 'HOLD_MISSING_OR_UNPASSED_CASES',
            'catalog_p0':len(expected),'observed_pass':len(observed),
            'missing':missing,'external_backlog_count':len(external)}


def run(root,out,groups=6,timeout=240,runner=None,emit=None):
    checkout=Path(root).resolve(strict=True)
    if type(timeout) not in (int,float) or not 20<=timeout<=900:
        raise ValueError('timeout outside 20..900')
    tests=find_tests(checkout)
    before=fingerprint(checkout,tests)
    partitions=group_files(tests,groups)
    evidence=fresh(out,checkout)
    (evidence/'groups').mkdir()
    runner=runner or execute
    emit=emit or (lambda b:(sys.stdout.buffer.write(b),sys.stdout.buffer.flush()))
    buffer=bytearray()
    lines=[]
    nodes=set()
    owners={}
    status='HOLD_INCOMPLETE_GROUPS'
    def write(line):
        raw=(line+'\n').encode('utf-8')
        emit(raw)
        buffer.extend(raw)
    write('M29 GROUPED LOCAL TESTS; RELEASE=HOLD; NOT CERTIFIED')
    try:
        for index,paths in enumerate(partitions,1):
            if fingerprint(checkout,tests)!=before:
                status='HOLD_SOURCE_DRIFT'
                break
            xml=evidence/'groups'/('group_%02d.xml'%index)
            argv=[sys.executable,'-m','pytest',*[p.relative_to(checkout).as_posix() for p in paths],
                  '-q','--disable-warnings','--junitxml='+str(xml)]
            entry={'group':index,'files':[p.relative_to(checkout).as_posix() for p in paths],
                   'status':'HOLD','return_code':None,'counts':None}
            try:
                state,code,log=runner(argv,checkout,timeout)
                if not isinstance(log,bytes) or len(log)>MAX_OUTPUT:
                    raise ValueError('oversized or nonbytes subprocess evidence')
                (evidence/'groups'/('group_%02d.log'%index)).write_bytes(log)
                entry['execution']=state
                entry['return_code']=code
                if state=='FINISHED' and code==0 and xml.is_file():
                    parsed=parse_junit(xml.read_bytes())
                    entry['counts']=parsed['counts']
                    if (any(parsed['counts'][k] for k in ('fail','error','skip'))
                        or nodes & parsed['nodes'] or set(owners) & set(parsed['cases'])):
                        entry['status']='HOLD_UNPASSED_OR_DUPLICATE'
                    else:
                        entry['status']='LOCAL_PASS'
                        nodes.update(parsed['nodes'])
                        owners.update(parsed['cases'])
                else:
                    entry['status']='HOLD_'+str(state)
            except (OSError,ValueError,ET.ParseError) as exc:
                entry['status']='HOLD_INVALID_EVIDENCE'
                entry['error_type']=type(exc).__name__
            lines.append(entry)
            write('GROUP %02d/%02d STATUS=%s'%(index,len(partitions),entry['status']))
            if entry['status']!='LOCAL_PASS':
                break
        if fingerprint(checkout,tests)!=before:
            status='HOLD_SOURCE_DRIFT'
        elif len(lines)==len(partitions) and all(x['status']=='LOCAL_PASS' for x in lines):
            audit=audit_p0(checkout,owners)
            status=('HOLD_P0_COVERAGE' if audit['status']=='HOLD_MISSING_OR_UNPASSED_CASES'
                    else 'LOCAL_REGRESSION_OBSERVED_NOT_CERTIFIED')
        else:
            audit=audit_p0(checkout,owners)
    except (Exception,KeyboardInterrupt) as exc:
        status='HOLD_INTERNAL_OR_INTERRUPTED'
        audit={'status':'NOT_AUDITED','error_type':type(exc).__name__}
    if fingerprint(checkout,tests)!=before:
        status='HOLD_SOURCE_DRIFT'
    write('STATUS=%s RELEASE=HOLD'%status)
    (evidence/'console.log').write_bytes(buffer)
    report={'schema':'m29-grouped-regression-v1','status':status,'release':'HOLD',
            'not_a_certification':True,'independent_approval':False,
            'planned_groups':len(partitions),'attempted_groups':len(lines),
            'source_sha256':before,'source_unchanged':fingerprint(checkout,tests)==before,
            'groups':lines,'case_audit':audit}
    (evidence/'report.json').write_bytes(json_bytes(report))
    ok=status=='LOCAL_REGRESSION_OBSERVED_NOT_CERTIFIED'
    suite=ET.Element('testsuite',name='m29_local_regression',tests='1',
                     failures='0' if ok else '1')
    case=ET.SubElement(suite,'testcase',classname='m29',name='grouped_local_regression')
    if not ok:
        ET.SubElement(case,'failure',message=status)
    (evidence/'junit.xml').write_bytes(ET.tostring(suite,encoding='utf-8',xml_declaration=True))
    manifest=[]
    for path in sorted(evidence.rglob('*')):
        if path.is_file() and path.name!='MANIFEST_SHA256.json':
            raw=path.read_bytes()
            manifest.append({'path':path.relative_to(evidence).as_posix(),
                             'bytes':len(raw),'sha256':digest(raw)})
    (evidence/'MANIFEST_SHA256.json').write_bytes(
        json_bytes({'schema':'m29-evidence-v1','files':manifest}))
    verify_output(evidence)
    return report


def verify_output(folder):
    root=Path(folder).absolute()
    if not root.is_dir() or any(p.is_symlink() for p in (root,*root.parents)):
        raise ValueError('unsafe M29 evidence root')
    listed=list(root.rglob('*'))
    if len(listed)>300 or any(p.is_symlink() for p in listed):
        raise ValueError('unsafe M29 inventory members')
    manifest=json.loads((root/'MANIFEST_SHA256.json').read_text(encoding='utf-8'))
    if manifest.get('schema')!='m29-evidence-v1' or not isinstance(manifest.get('files'),list):
        raise ValueError('M29 invalid manifest schema')
    entries=manifest['files']
    names=[x.get('path') for x in entries if isinstance(x,dict)]
    inventory={p.relative_to(root).as_posix() for p in listed if p.is_file()}
    if len(names)!=len(entries) or len(names)!=len(set(names)) or inventory!=set(names)|{'MANIFEST_SHA256.json'}:
        raise ValueError('M29 manifest inventory disagreement')
    for item in entries:
        name=item['path']
        if (not isinstance(name,str) or not name or name.startswith('/')
            or ':' in name or '\\' in name or '..' in Path(name).parts):
            raise ValueError('unsafe member path')
        file=root/name
        if (file.is_symlink() or not file.is_file() or type(item.get('bytes')) is not int
            or file.stat().st_size!=item['bytes'] or digest(file.read_bytes())!=item.get('sha256')):
            raise ValueError('M29 evidence hash mismatch')
    record=json.loads((root/'report.json').read_text(encoding='utf-8'))
    if (record.get('schema')!='m29-grouped-regression-v1' or record.get('release')!='HOLD'
        or record.get('not_a_certification') is not True
        or record.get('independent_approval') is not False):
        raise ValueError('M29 false approval report')
    status=record.get('status')
    if not isinstance(status,str) or not (root/'console.log').read_bytes().endswith(
            ('STATUS=%s RELEASE=HOLD\n'%status).encode('utf-8')):
        raise ValueError('M29 console contradiction')
    xml=(root/'junit.xml').read_bytes()
    if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
        raise ValueError('M29 JUnit entity')
    tree=ET.fromstring(xml)
    ok=status=='LOCAL_REGRESSION_OBSERVED_NOT_CERTIFIED'
    if (tree.tag!='testsuite' or tree.get('name')!='m29_local_regression'
        or tree.get('tests')!='1' or tree.get('failures')!=('0' if ok else '1')
        or len(list(tree.iter('testcase')))!=1 or len(list(tree.iter('failure')))!=int(not ok)):
        raise ValueError('M29 JUnit contradiction')
    return len(entries)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--out',required=True)
    parser.add_argument('--groups',type=int,default=6)
    parser.add_argument('--timeout',type=float,default=240)
    args=parser.parse_args(argv)
    try:
        report=run(args.root,args.out,args.groups,args.timeout)
    except (OSError,ValueError) as exc:
        parser.error(str(exc))
    return 0 if report['status']=='LOCAL_REGRESSION_OBSERVED_NOT_CERTIFIED' else 1


if __name__=='__main__':
    raise SystemExit(main())
