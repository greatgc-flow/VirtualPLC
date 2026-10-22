"""M27: offline, read-only M26 multi-run evidence triage.

Checks original hashes/JUnit and every successful M23 child via M25. Numbers are
descriptive, NEVER vendor/Windows validation, an SLA or release approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import xml.etree.ElementTree as ET

from scripts import m23_recovery_soak as m23
from scripts import m24_compare as m24
from scripts import m25_replicates as m25
from scripts import m26_multi_run as m26

METRICS = ('p50_us','p95_us','p99_us','rss_initial_kib','rss_final_kib',
           'rss_slope_kib_per_minute','requests_ok')


def json_object(raw):
    try:
        obj = json.loads(raw.decode('utf-8'),
                         parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
    except (ValueError, UnicodeError) as exc:
        raise ValueError('invalid evidence JSON') from exc
    if not isinstance(obj, dict):
        raise ValueError('JSON object required')
    return obj


def bounded_file(root, name, limit):
    p = root / name
    if p.is_symlink() or not p.is_file() or p.stat().st_size > limit:
        raise ValueError('missing/unsafe/oversized evidence: '+name)
    return p.read_bytes()


def safe_tree(location):
    p = Path(location).absolute()
    if any(x.is_symlink() for x in (p, *p.parents)):
        raise ValueError('symlink evidence root/ancestor')
    root = p.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('evidence not directory')
    dirs = files = total = 0
    for folder, subdirs, names in os.walk(root, followlinks=False):
        dirs += 1
        if dirs > 70:
            raise ValueError('too many directories')
        for name in subdirs + names:
            if (Path(folder) / name).is_symlink():
                raise ValueError('symlink evidence member')
        for name in names:
            file = Path(folder) / name
            if not file.is_file():
                raise ValueError('nonregular evidence member')
            files += 1
            total += file.stat().st_size
            if files > 200 or total > 90_000_000:
                raise ValueError('evidence size or count limit')
    return root


def verify_junit(raw, entries, status):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('JUnit DTD or entity')
    try:
        suite = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError('invalid M26 JUnit') from exc
    cases = list(suite.iter('testcase'))
    names = ['repeat_{:02d}'.format(i) for i in range(1,len(entries)+1)]+['aggregate']
    failed = sum(x['status']!='VERIFIED' for x in entries)+(status!='OBSERVED_NOT_CERTIFIED')
    if (suite.tag != 'testsuite' or suite.get('name')!='m26_local_orchestrator'
        or suite.get('tests')!=str(len(names)) or suite.get('failures')!=str(failed)
        or len(cases)!=len(names) or [x.get('name') for x in cases]!=names):
        raise ValueError('M26 JUnit coverage mismatch')
    for index, case in enumerate(cases):
        expected_failure = (index<len(entries) and entries[index]['status']!='VERIFIED'
                            or index==len(entries) and status!='OBSERVED_NOT_CERTIFIED')
        if (case.get('classname')!='m26' or case.find('error') is not None
            or case.find('skipped') is not None
            or len(case.findall('failure'))!=int(expected_failure)):
            raise ValueError('M26 JUnit outcome mismatch')


def describe(items):
    if not items or any(type(v) not in (int,float) or not math.isfinite(v) for v in items):
        return {'status':'INSUFFICIENT_NUMERIC_DATA','count':len(items)}
    mid = statistics.median(items)
    return {'status':'DESCRIPTIVE_ONLY','count':len(items),'min':min(items),
            'median':mid,'max':max(items),
            'median_absolute_deviation':statistics.median([abs(x-mid) for x in items]),
            'per_run':items}


def analyze(folder, limits=None):
    """Fail closed on corrupt input; incomplete but untampered runs become HOLD."""
    limits = m24.validate_limits(limits)
    root = safe_tree(folder)
    try:
        m26.verify_output(root)
        record = json_object(bounded_file(root,'report.json',2_000_000))
        console = bounded_file(root,'console.log',250_000)
        junit = bounded_file(root,'junit.xml',250_000)
    except (OSError,TypeError,KeyError,UnicodeError) as exc:
        raise ValueError('invalid M26 bundle') from exc
    if (record.get('schema')!='m26-orchestration-v1' or record.get('release')!='HOLD'
        or record.get('not_a_certification') is not True
        or record.get('independent_approval') is not False
        or record.get('external_p0_remaining')!=16
        or record.get('source_unchanged') is not True):
        raise ValueError('invalid M26 safety gate')
    entries = record.get('runs')
    requested, attempted, state = record.get('requested'),record.get('attempted'),record.get('status')
    if (type(requested) is not int or not 3<=requested<=30
        or type(attempted) is not int or not 0<=attempted<=requested
        or not isinstance(entries,list) or len(entries)!=attempted
        or not all(isinstance(x,dict) for x in entries)
        or not isinstance(state,str) or not
        (state=='OBSERVED_NOT_CERTIFIED' or state.startswith('HOLD_'))
        or not isinstance(record.get('source_sha256'),dict)
        or not record['source_sha256']
        or [x.get('run') for x in entries]!=list(range(1,attempted+1))):
        raise ValueError('inconsistent M26 report')
    opts = record.get('options')
    if not isinstance(opts,dict) or m26.validate_options(**opts)!=opts or opts['runs']!=requested:
        raise ValueError('M26 options mismatch')
    complete = (attempted==requested and state=='OBSERVED_NOT_CERTIFIED'
                and all(x.get('status')=='VERIFIED' and x.get('child_status')=='EXECUTED'
                        and x.get('return_code')==0 for x in entries))
    if state=='OBSERVED_NOT_CERTIFIED' and not complete:
        raise ValueError('false M26 completion')
    if state.startswith('HOLD_') and record.get('descriptive_summary') is not None:
        raise ValueError('M26 HOLD with accepted summary')
    if console.count(b'STATUS=')!=1 or not console.endswith(
            b'STATUS='+state.encode('ascii')+b' RELEASE=HOLD\n'):
        raise ValueError('M26 console/report mismatch')
    verify_junit(junit,entries,state)
    rows, paths, differences = [], [], set()
    first = None
    for entry in entries:
        n=entry['run']
        stdout=bounded_file(root,'run_stdout/{:02d}.log'.format(n),250_000)
        if hashlib.sha256(stdout).hexdigest()!=entry.get('stdout_sha256'):
            raise ValueError('M26 child stdout mismatch')
        row={'run':n,'status':entry.get('status'),'child_status':entry.get('child_status'),
             'integrity':'UNVERIFIED','metrics':None,'anomalies':[]}
        if row['status']=='VERIFIED':
            if row['child_status']!='EXECUTED' or entry.get('return_code')!=0:
                raise ValueError('false verified child')
            p=root/'runs'/'{:02d}'.format(n)
            child=m25.verify_run(p)['report']
            if any(child['source_sha256'].get(k)!=record['source_sha256'].get(k)
                   for k in m23.SOURCE_FILES):
                raise ValueError('parent/child source mismatch')
            soak=child['duration_soak']
            if (soak['clients']!=opts['clients']
                or soak['duration_requested_seconds']!=opts['duration']
                or soak.get('max_cycles')!=opts['max_cycles']
                or child['fault_recovery'].get('delay_requested_ms')!=opts['delay_ms']):
                raise ValueError('parent/child workload mismatch')
            fingerprints=(child['platform'],child['python_version'],
                          json.dumps(child['source_sha256'],sort_keys=True),
                          soak['clients'],soak['duration_requested_seconds'],
                          soak.get('max_cycles'),child['fault_recovery'].get('delay_requested_ms'))
            if first is None:
                first=fingerprints
            else:
                for i,key in enumerate(('platform','python','source','clients',
                                        'duration','cycles','fault_delay')):
                    if fingerprints[i]!=first[i]:
                        differences.add(key)
                        row['anomalies'].append('MISMATCH_'+key.upper())
            values={k:soak.get(k) for k in METRICS}
            initial,final=values['rss_initial_kib'],values['rss_final_kib']
            values['rss_within_run_delta_kib']=(final-initial if
                    type(final) in (int,float) and type(initial) in (int,float) else None)
            row['metrics']=values
            row['integrity']='HASH_VERIFIED_NOT_ATTESTED'
            row['recovery']={'readback':child['fault_recovery']['verified_readback'],
                             'reconnects':child['fault_recovery']['reconnects_successful']}
            paths.append(p)
        else:
            row['anomalies'].append('FAILED_OR_INCOMPLETE_RUN')
        rows.append(row)
    if complete and len(paths)!=requested:
        raise ValueError('missing verified run in completed batch')
    if complete:
        summary=m25.analyze(paths)
        if summary.get('status') not in ('INCOMPARABLE','REPEATED_OBSERVATIONS_ONLY'):
            raise ValueError('unacceptable M25 status')
        if summary['status']=='INCOMPARABLE':
            differences.update(summary.get('issues') or ['unknown_difference'])
    stats,alerts,missing={},[],[]
    if complete and not differences:
        keys=METRICS+('rss_within_run_delta_kib',)
        stats={key:describe([row['metrics'][key] for row in rows]) for key in keys}
        if limits:
            base=rows[0]['metrics']
            aliases={'p95_growth_percent':'p95_us','p99_growth_percent':'p99_us',
                     'rss_growth_kib':'rss_final_kib'}
            for row in rows[1:]:
                for key,maximum in limits.items():
                    before=base[aliases[key]]
                    after=row['metrics'][aliases[key]]
                    if (type(before) not in (int,float) or type(after) not in (int,float)
                        or key.endswith('_percent') and before==0):
                        missing.append({'run':row['run'],'metric':key})
                        continue
                    observed=((after-before)*100/before if key.endswith('_percent')
                              else after-before)
                    if observed>maximum:
                        alerts.append({'run':row['run'],'metric':key,
                                       'observed':round(observed,6),'limit':maximum})
                        row['anomalies'].append('OPTIONAL_THRESHOLD_'+key.upper())
    outcome=('HOLD_INCOMPLETE_RUNS' if not complete else
             'INCOMPARABLE' if differences or missing else
             'OPTIONAL_THRESHOLD_EXCEEDED' if alerts else 'COMPARABLE_DESCRIPTIVE')
    return {'schema':'m27-triage-v1','status':outcome,'release':'HOLD',
            'not_a_certification':True,'independent_approval':False,
            'm26_status':state,'requested':requested,'attempted':attempted,
            'evidence_integrity':'HASH_VERIFIED_NOT_ORIGIN_ATTESTED',
            'limits_explicit':limits,'no_default_thresholds':limits is None,
            'comparable':complete and not differences and not missing,
            'mismatch_reasons':sorted(differences),'numeric_missing':missing,
            'threshold_exceedances':alerts,'runs':rows,'statistics':stats,
            'historical_p0_locally_observed':183,'external_p0_hold':16,
            'interpretation':'descriptive_only_no_SLA_no_leak_freedom_no_vendor_certification'}


def write_once(out, report, *, input_folder=None, emit_bytes=None):
    target=Path(out).absolute()
    if input_folder is not None:
        src=Path(input_folder).absolute()
        if src==target or src in target.parents or target in src.parents:
            raise ValueError('output must be separate from M26 input')
    target=m26.fresh_destination(target)
    line=('M27 TRIAGE: '+report['status']+' RELEASE=HOLD NOT CERTIFIED\n').encode()
    if emit_bytes is None:
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
    else:
        emit_bytes(line)
    (target/'console.log').write_bytes(line)
    (target/'analysis.json').write_bytes(m26.json_bytes(report))
    suite=ET.Element('testsuite',name='m27_read_only_triage',tests='1',
                     failures='0' if report['status']=='COMPARABLE_DESCRIPTIVE' else '1')
    case=ET.SubElement(suite,'testcase',classname='m27',name='comparable_descriptive_only')
    if report['status']!='COMPARABLE_DESCRIPTIVE':
        ET.SubElement(case,'failure',message=report['status'])
    (target/'junit.xml').write_bytes(ET.tostring(suite,encoding='utf-8',xml_declaration=True))
    entries={}
    for name in ('console.log','analysis.json','junit.xml'):
        raw=(target/name).read_bytes()
        entries[name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    (target/'MANIFEST_SHA256.json').write_bytes(
        m26.json_bytes({'schema':'m27-local-evidence-v1','entries':entries}))
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--thresholds-json',default=None)
    args=p.parse_args(argv)
    try:
        limits=None
        if args.thresholds_json:
            policy=Path(args.thresholds_json)
            if policy.is_symlink() or policy.stat().st_size>4096:
                raise ValueError('unsafe threshold JSON')
            limits=json_object(policy.read_bytes())
        result=analyze(args.input,limits)
    except (ValueError,OSError,TypeError,KeyError,ET.ParseError) as exc:
        result={'schema':'m27-triage-v1','status':'HOLD_INVALID_INPUT','release':'HOLD',
                'not_a_certification':True,'independent_approval':False,
                'error_type':type(exc).__name__,'external_p0_hold':16}
    write_once(args.out,result,input_folder=args.input)
    return 0 if result['status']=='COMPARABLE_DESCRIPTIVE' else 1


if __name__=='__main__':
    raise SystemExit(main())
