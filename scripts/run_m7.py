"""Fail-closed merge of *existing* M6 regression + split TCP + new M7 JUnit.

Do not invent pass evidence; reject missing/failed/duplicate identities. The
full TCP suite is split so pathological fuzz cases run in a clean subprocess.
Console contents are written byte-identically to an evidence text file.
"""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
PHASES=[
 ('baseline',['tests/test_virtual_plc.py','tests/test_m4_p0_case_ids_v2.py',
              'suite/tests/domain','suite/tests/static','tests/test_m5_p0_case_ids.py',
              'tests/test_m5_governance.py','tests/test_m6_runtime.py','tests/test_m6_governance.py']),
 ('tcp43',['suite/tests/live/test_wire_cases.py','-k','not fuzz','--server-cmd',
           'python -m virtual_plc --host {host} --port {port}']),
 ('tcp_fuzz',['suite/tests/live/test_wire_cases.py','-k','fuzz','--server-cmd',
           'python -m virtual_plc --host {host} --port {port}']),
 ('m7',['tests/test_m7_runtime.py'])]

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='evidence/m7_run')
    args=p.parse_args();out=(ROOT/args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    logs=[];suites=ET.Element('testsuites');errors=[]
    for label,extra in PHASES:
        xml=out/(label+'.xml');cmd=[sys.executable,'-m','pytest',*extra,'-q',f'--junitxml={xml}']
        env=dict(os.environ,MC_SIM_ADAPTER_MODULE='virtual_plc.test_adapter',PYTHONPATH=str(ROOT))
        run=subprocess.run(cmd,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,timeout=180)
        statement='$ '+' '.join(cmd)+'\n'+run.stdout
        (out/(label+'.log')).write_text(statement,encoding='utf-8')
        logs.append(statement)
        if run.returncode!=0 or not xml.is_file():
            errors.append(f'{label}: exit {run.returncode}, junit_present={xml.is_file()}')
            break
        root=ET.parse(xml).getroot()
        for suite in root.findall('.//testsuite'):
            if int(suite.attrib.get('failures','0')) or int(suite.attrib.get('errors','0')):
                errors.append(f'{label}: JUnit failure/error')
            suites.append(suite)
    combined=out/'combined.xml';ET.ElementTree(suites).write(combined,encoding='utf-8',xml_declaration=True)
    if not errors:
        cmd=[sys.executable,'scripts/gate_report.py','--junit',str(combined),'--out',str(out/'gate.json')]
        result=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
        if result.returncode:errors.append('gate report failed')
        else:
            data=json.loads((out/'gate.json').read_text())
            if (data['suite_p0_observed_pass_unattested']!=176 or data['suite_p0_not_run']!=23
                  or data['suite_p0_fail'] or data['duplicate_junit_case_ids']):
                errors.append('exact CASE-ID expected 176/199 differs; see gate.json')
    try: client=importlib.metadata.version('pymcprotocol')
    except importlib.metadata.PackageNotFoundError:client='NOT_INSTALLED'
    metadata={'result':'PASS' if not errors else 'FAIL','phase_errors':errors,
        'python':platform.python_version(),'platform':platform.platform(),
        'pymcprotocol':client,'client_compat':'NOT_ATTESTED',
        'independent_gate':'HOLD','github_ci':'NOT_RUN','run_command':'python scripts/run_m7.py',
        'junit':str(combined)}
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    output=''.join(logs)+json.dumps(metadata,indent=2)+'\n'
    (out/'console.txt').write_text(output,encoding='utf-8')
    print(output,end='')
    return int(bool(errors))

if __name__=='__main__':raise SystemExit(main())
