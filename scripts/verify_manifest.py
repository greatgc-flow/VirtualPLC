"""Check SHA256 exact set; no dependency on ZIP or PLC."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'MANIFEST_SHA256.json'
EXCL={'MANIFEST_SHA256.json'}
def audit():
    man=json.loads(PATH.read_text(encoding='utf-8'))
    actual={str(p.relative_to(ROOT)).replace('\\','/'):p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts and p.name not in EXCL}
    expected={entry['path']:entry for entry in man['files']}
    errors=[]
    if set(actual)!=set(expected):errors.extend(['MISSING: '+k for k in sorted(set(expected)-set(actual))]+['EXTRA: '+k for k in sorted(set(actual)-set(expected))])
    for name in sorted(set(actual)&set(expected)):
        data=actual[name].read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected[name]['sha256']:errors.append('HASH: '+name)
        if len(data)!=expected[name]['size']:errors.append('SIZE: '+name)
    return errors,len(expected)
if __name__=='__main__':
    errors,count=audit();print('MANIFEST PASS' if not errors else 'MANIFEST FAIL',count,errors[:20]);sys.exit(bool(errors))
