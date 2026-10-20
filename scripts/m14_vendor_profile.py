"""Validate a *claimed* Mitsubishi model/end-code profile without certifying it.

Profiles are declarative, local, explicit, model/firmware-specific, and pinned to
public manual URLs and page references. This command does not connect to PLCs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

G0E_IDS = ('CASE-0018','CASE-0019','CASE-0020','CASE-0064','CASE-0088','CASE-0090')
HEX_CODE = re.compile(r'^[0-9A-F]{4}$')


def check_profile(profile):
    if not isinstance(profile,dict): raise ValueError('profile must be object')
    exact_keys={'model','ethernet_module','firmware','manual_url','manual_revision','behavior'}
    if set(profile)!=exact_keys: raise ValueError('profile fields absent/unknown')
    for key in ('model','ethernet_module','firmware','manual_revision'):
        s=profile[key]
        if not isinstance(s,str) or not s.strip() or len(s)>140 or any(x in s for x in ('<','>','{','}')):
            raise ValueError('missing/invalid '+key)
        if s.strip().upper() in ('UNKNOWN','TODO','TBD','N/A'):
            raise ValueError('unresolved manufacturer identity: '+key)
    url=profile['manual_url']
    if not isinstance(url,str) or urlsplit(url).scheme!='https' or not urlsplit(url).netloc:
        raise ValueError('official reference must have HTTPS URL')
    if not (urlsplit(url).hostname and any(urlsplit(url).hostname == domain or
        urlsplit(url).hostname.endswith('.' + domain) for domain in
        ('mitsubishielectric.com', 'mitsubishielectric.co.jp'))):
        raise ValueError('manufacturer reference must use Mitsubishi domain')
    behavior=profile['behavior']
    if not isinstance(behavior,list) or len(behavior)!=len(G0E_IDS):
        raise ValueError('exactly six manufacturer cases required')
    seen=set(); resolved=0
    for case in behavior:
        if not isinstance(case,dict) or set(case)!={'case_id','trigger','end_code_hex','manual_page','comments'}:
            raise ValueError('invalid case schema')
        ident=case['case_id']
        if ident not in G0E_IDS or ident in seen:raise ValueError('missing/duplicate/foreign case ID')
        seen.add(ident)
        for item in ('trigger','comments'):
            if not isinstance(case[item],str) or not case[item].strip():
                raise ValueError('scenario description missing')
        code=case['end_code_hex']
        page=case['manual_page']
        if (code is None) != (page is None):
            raise ValueError('code and cited manual page must both exist or both be null')
        if code is not None:
            if not isinstance(code,str) or not HEX_CODE.fullmatch(code):raise ValueError('invalid end code')
            if type(page) is not int or page <= 0 or page >= 5000:raise ValueError('invalid manual page')
            resolved+=1
    return {'model_and_version_declared': True,'case_ids': list(G0E_IDS),
            'codes_with_citations': resolved, 'missing_code_sources': len(G0E_IDS)-resolved,
            'manufacturer_certified': False,
            'release':'HOLD',
            'meaning':'supplied metadata/citations are unverified claims, not manufacturer authorization'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.out.exists():
        print('M14_VENDOR=HOLD: destination exists')
        return 2
    try:
        raw=args.profile.read_bytes()
        report=check_profile(json.loads(raw))
        report['profile_sha256']=hashlib.sha256(raw).hexdigest()
    except (OSError,ValueError,json.JSONDecodeError) as exc:
        print('M14_VENDOR=HOLD: '+str(exc))
        return 2
    raw=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode()
    args.out.mkdir(parents=True,exist_ok=False)
    (args.out/'result.json').write_bytes(raw)
    (args.out/'console.txt').write_bytes(raw)
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()
    return 2  # always hold pending independent review


if __name__=='__main__':raise SystemExit(main())
