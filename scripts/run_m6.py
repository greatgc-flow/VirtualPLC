"""Run all M5 phases plus M6 distinct CASE-IDs and mirror stdout to logs.

NEVER claims vendor/field compatibility or grants release. Hardware-free loopback.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from xml.etree import ElementTree as ET
try:
    from scripts.run_m5 import run_one
except ModuleNotFoundError:
    from run_m5 import run_one

ROOT=Path(__file__).resolve().parents[1]

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--output',default='evidence/m6_run')
    p.add_argument('--fast',action='store_true',help='skip older 45-case TCP loopback phase')
    a=p.parse_args(argv)
    out=Path(a.output)
    if not out.is_absolute():out=ROOT/out
    out.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,MC_SIM_ADAPTER_MODULE='virtual_plc.test_adapter')
    phases=[('regression',['tests/test_virtual_plc.py','tests/test_m4_p0_case_ids_v2.py',
                          'suite/tests/domain','suite/tests/static']),
            ('m5',['tests/test_m5_p0_case_ids.py','tests/test_m5_governance.py']),
            ('m6',['tests/test_m6_runtime.py','tests/test_m6_governance.py'])]
    if not a.fast:
        phases.append(('tcp',['suite/tests/live/test_wire_cases.py']))
    results={}
    outputs=[]
    for label,paths in phases:
        xml=out/(label+'.xml')
        command=[sys.executable,'-m','pytest']+paths+['-q','--junitxml='+str(xml)]
        if label=='tcp':
            command+=['--server-cmd','python -m virtual_plc --host {host} --port {port}']
        results[label]=run_one(label,command,env,out)
        if results[label]!=0:
            print('Suite '+label+' failed; release HOLD.',flush=True)
            break
        outputs.append(xml)
    if len(outputs)!=len(phases):
        return 1
    merged=ET.Element('testsuites')
    for path in outputs:
        doc=ET.parse(path).getroot()
        for node in doc.findall('.//testsuite'):
            merged.append(node)
    combined=out/'combined.xml'
    ET.ElementTree(merged).write(combined,encoding='utf-8',xml_declaration=True)
    gate=out/'gate.json'
    results['gate_report']=run_one('gate_report',[sys.executable,
        'scripts/gate_report.py','--junit',str(combined),'--out',str(gate)],env,out)
    try:version=importlib.metadata.version('pymcprotocol')
    except importlib.metadata.PackageNotFoundError:version='NOT_INSTALLED'
    evidence={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
              'python':sys.version,'os':platform.platform(),
              'pymcprotocol_installed_version':version,
              'pymcprotocol_client_attestation':'NOT_ATTESTED',
              'suite_sha256':sha256((ROOT/'suite/catalog/test_cases.jsonl').read_bytes()).hexdigest(),
              'server_sha256':sha256((ROOT/'virtual_plc/server.py').read_bytes()).hexdigest(),
              'telemetry_sha256':sha256((ROOT/'virtual_plc/telemetry.py').read_bytes()).hexdigest(),
              'test_sha256':sha256((ROOT/'tests/test_m6_runtime.py').read_bytes()).hexdigest(),
              'phase_exit_codes':results,'release':'HOLD','ci_run':'NOT_RUN'}
    (out/'run_metadata.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'gate':json.loads(gate.read_text()),'metadata':evidence},indent=2))
    return 0 if all(code==0 for code in results.values()) else 1

if __name__=='__main__':raise SystemExit(main())
