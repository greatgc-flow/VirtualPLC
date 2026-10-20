"""Strictly local, opt-in raw client *request* capture and independent wire validation.

Capture proves observed bytes in the local test process; it is NOT independent
provenance, producer authenticity, Mitsubishi device certification, or release approval.
Do not export actual plant traffic here: only dummy D100/M10 simulator transactions.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import struct

CLIENT_CASES = {
    'CASE-0027': 'D', 'CASE-0028': 'M', 'CASE-0029': 'D',
    'CASE-0109': 'D', 'CASE-0110': 'M', 'CASE-0111': 'M',
}
WHEEL_SHA256 = '614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6'
ROUTE = bytes.fromhex('00 ff ff 03 00')
D_VALUES = (0x1995, 0x1202, 0x1130)
M_VALUES = (1, 0, 1, 0, 1)
MAX_FRAME_BYTES = 4096


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_request(raw: bytes) -> dict:
    """Independently decode the specific supported 3E Binary request subset."""
    if type(raw) is not bytes or not 21 <= len(raw) <= MAX_FRAME_BYTES:
        raise ValueError('request frame length unsupported')
    if raw[:2] != b'\x50\x00' or raw[2:7] != ROUTE:
        raise ValueError('non-local or unsupported station subheader/route')
    length = int.from_bytes(raw[7:9], 'little')
    if length != len(raw)-9:
        raise ValueError('response data-length field does not equal request size')
    timer,cmd,sub=struct.unpack_from('<HHH',raw,9)
    if timer == 0:
        raise ValueError('zero client monitoring timer')
    address = int.from_bytes(raw[15:18], 'little')
    device = raw[18]
    count = int.from_bytes(raw[19:21], 'little')
    payload = raw[21:]
    if (cmd,sub) not in ((0x1401,0),(0x0401,0),(0x1401,1),(0x0401,1)):
        raise ValueError('unsupported batch command/subcommand')
    kind = 'D' if sub == 0 else 'M'
    expected_address, expected_device, expected_count = ((100,0xA8,3) if kind == 'D'
                                                            else (10,0x90,5))
    if (address,device,count) != (expected_address,expected_device,expected_count):
        raise ValueError('client addressed unexpected device')
    if cmd == 0x0401:
        if payload:
            raise ValueError('read contained unexpected payload')
    elif kind == 'D':
        if payload != struct.pack('<3H', *D_VALUES):
            raise ValueError('unexpected D write payload')
    else:
        if payload != b'\x10\x10\x10':
            raise ValueError('unexpected M write payload')
    return {'command':f'{cmd:04X}', 'subcommand':f'{sub:04X}',
            'device':kind, 'address':address,'count':count,
            'bytes':len(raw),'sha256':sha256(raw)}


def validate_capture(case_id: str, raw_frames: list[bytes]) -> dict:
    """Check exact two-frame write/read exchange without trusting client internals."""
    kind = CLIENT_CASES.get(case_id)
    if kind is None or len(raw_frames) != 2:
        raise ValueError('unknown test ID or incomplete capture')
    details = [parse_request(x) for x in raw_frames]
    if [x['command'] for x in details] != ['1401','0401']:
        raise ValueError('command ordering must be write then read')
    if any(x['device'] != kind for x in details):
        raise ValueError('CASE-ID/device crosswalk mismatch')
    return {'schema':'virtualplc.m15.wire-capture.v1',
            'case_id':case_id, 'frames':[
                {'request_hex':frame.hex(),**meta}
                for frame,meta in zip(raw_frames,details)
            ], 'source':'localhost-real-client-request-hook',
            'attested':False,'release':'HOLD'}


def write_capture(path, case_id, frames):
    """Create once; never overwrite, including in concurrent test runs."""
    path=Path(path)
    data=validate_capture(case_id,frames)
    encoded=(json.dumps(data,sort_keys=True,indent=2)+'\n').encode('utf-8')
    with path.open('xb') as fh:
        fh.write(encoded)
    return sha256(encoded)


def verify_capture_dir(path) -> dict:
    """Six exact case files, per-frame independent replay, no extras or symlinks."""
    folder=Path(path)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError('raw request capture directory missing')
    observed=set(p.name for p in folder.iterdir())
    wanted={f'{k}.json' for k in CLIENT_CASES}
    if observed != wanted:
        raise ValueError('capture missing, extra, or duplicate CASE-ID files')
    hashes={}
    for case_id in sorted(CLIENT_CASES):
        p=folder/(case_id+'.json')
        if p.is_symlink() or not p.is_file():
            raise ValueError('capture file is symlink or missing')
        b=p.read_bytes()
        if len(b)>32768:
            raise ValueError('capture file oversized')
        decoded=json.loads(b)
        if decoded.get('schema')!='virtualplc.m15.wire-capture.v1' or decoded.get('case_id')!=case_id:
            raise ValueError('wrong capture schema or case ID')
        if decoded.get('attested') is not False or decoded.get('release')!='HOLD':
            raise ValueError('capture cannot claim release attestation')
        frames=decoded.get('frames')
        if not isinstance(frames,list) or len(frames)!=2:
            raise ValueError('capture must contain exactly two frames')
        raw=[]
        for item in frames:
            if not isinstance(item,dict) or type(item.get('request_hex')) is not str:
                raise ValueError('missing hex payload')
            raw.append(bytes.fromhex(item['request_hex']))
        expected=validate_capture(case_id,raw)
        if decoded != expected:
            raise ValueError('decoded and independently computed request fields disagree')
        hashes[case_id]=sha256(b)
    return {'status':'SIX_REQUEST_CAPTURES_INTACT_UNATTESTED',
            'file_sha256':hashes, 'case_ids':sorted(CLIENT_CASES)}
