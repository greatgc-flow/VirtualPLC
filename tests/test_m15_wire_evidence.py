"""M15 simulated capture oracle: does not count as actual pymcprotocol P0 success."""
import copy
import json
import struct
from pathlib import Path
import pytest
from scripts.m15_wire_evidence import (CLIENT_CASES, parse_request,
    validate_capture, write_capture, verify_capture_dir)

ROUTE = bytes.fromhex('00 ff ff 03 00')

def make_frame(kind='D', command=0x1401, *, route=ROUTE, timer=16,
               address=None, device=None, count=None, payload=None):
    sub=0 if kind=='D' else 1
    address = (100 if kind=='D' else 10) if address is None else address
    device = (0xA8 if kind=='D' else 0x90) if device is None else device
    count = (3 if kind=='D' else 5) if count is None else count
    if payload is None:
        payload = ((struct.pack('<3H',0x1995,0x1202,0x1130) if kind=='D'
                    else b'\x10\x10\x10') if command==0x1401 else b'')
    body=(struct.pack('<HHH', timer, command, sub)
          +address.to_bytes(3,'little') + bytes([device])
          +struct.pack('<H', count) + payload)
    return b'\x50\x00' + route + struct.pack('<H',len(body)) + body


def make_frames(kind):
    return [make_frame(kind),make_frame(kind,0x0401)]

@pytest.mark.parametrize('case_id,kind', sorted(CLIENT_CASES.items()))
def test_capture_writer_and_strict_replay(case_id,kind,tmp_path):
    path=tmp_path/(case_id+'.json')
    h=write_capture(path,case_id,make_frames(kind))
    assert len(h)==64
    assert json.loads(path.read_text())['attested'] is False
    with pytest.raises(FileExistsError):
        write_capture(path,case_id,make_frames(kind))

@pytest.mark.parametrize('kind', ['D','M'])
def test_independent_wire_decoding(kind):
    decoded=[parse_request(f) for f in make_frames(kind)]
    assert [x['command'] for x in decoded] == ['1401','0401']
    assert [x['device'] for x in decoded] == [kind,kind]

@pytest.mark.parametrize('case_id,kind', sorted(CLIENT_CASES.items()))
def test_reject_wrong_device_case_crosswalk(case_id,kind):
    wrong='M' if kind=='D' else 'D'
    with pytest.raises(ValueError,match='crosswalk'):
        validate_capture(case_id,make_frames(wrong))

@pytest.mark.parametrize('corruption', [
    'short','long','subheader','route','wrong_length','zero_timer','bad_command',
    'bad_address','bad_device','bad_count','bad_data','read_payload', 'truncated_data',
    'bad_device_kind', 'invalid_byte_type'
])
def test_invalid_wire_rejected(corruption):
    raw=make_frame()
    b=bytearray(raw)
    if corruption=='short': raw=raw[:20]
    elif corruption=='long': raw=raw+b'\x00'*4096
    elif corruption=='subheader':b[0]=0x51;raw=bytes(b)
    elif corruption=='route':b[3]=0x30;raw=bytes(b)
    elif corruption=='wrong_length':b[7]=0;raw=bytes(b)
    elif corruption=='zero_timer':b[9]=0;raw=bytes(b)
    elif corruption=='bad_command':b[11]=0x02;raw=bytes(b)
    elif corruption=='bad_address':b[15]=0xff;raw=bytes(b)
    elif corruption=='bad_device':b[18]=0x90;raw=bytes(b)
    elif corruption=='bad_count':b[19]=4;raw=bytes(b)
    elif corruption=='bad_data':b[-1]^=1;raw=bytes(b)
    elif corruption=='read_payload':raw=make_frame(command=0x0401,payload=b'\x00')
    elif corruption=='truncated_data':raw=raw[:-1]
    elif corruption=='bad_device_kind':raw=make_frame(kind='M',device=0xA8)
    elif corruption=='invalid_byte_type':raw=bytearray(raw)
    with pytest.raises((ValueError,TypeError)):
        parse_request(raw)

@pytest.mark.parametrize('fault', ['missing','extra','symlink','mismatched_hash',
    'forged_approval','wrong_case_id','corrupt_hex','wrong_case_kind','missing_frames',
    'extra_frames','changed_payload','changed_metadata','overlarge'])
def test_capture_dir_cannot_be_forged(tmp_path,fault):
    folder=tmp_path/'c';folder.mkdir()
    for cid,kind in CLIENT_CASES.items():
        write_capture(folder/(cid+'.json'),cid,make_frames(kind))
    assert len(verify_capture_dir(folder)['case_ids'])==6
    target=folder/'CASE-0027.json'
    if fault=='missing': target.unlink()
    elif fault=='extra':(folder/'unexpected.json').write_text('{}')
    elif fault=='symlink':
        target.unlink();target.symlink_to(folder/'CASE-0028.json')
    else:
        obj=json.loads(target.read_text())
        if fault=='mismatched_hash': obj['frames'][0]['sha256']='0'*64
        elif fault=='forged_approval':obj['attested']=True
        elif fault=='wrong_case_id':obj['case_id']='CASE-9999'
        elif fault=='corrupt_hex':obj['frames'][0]['request_hex']='GG'
        elif fault=='wrong_case_kind':obj['frames'][0]['device']='M'
        elif fault=='missing_frames':obj['frames'].pop()
        elif fault=='extra_frames':obj['frames'].append(copy.deepcopy(obj['frames'][0]))
        elif fault=='changed_payload':obj['frames'][0]['request_hex']=obj['frames'][0]['request_hex'][:-2]+'ff'
        elif fault=='changed_metadata':obj['frames'][0]['count']=9
        elif fault=='overlarge':obj['unused']='x'*32768
        target.write_text(json.dumps(obj))
    with pytest.raises((ValueError,TypeError)):
        verify_capture_dir(folder)


def test_incorrect_request_order_fails():
    with pytest.raises(ValueError,match='ordering'):
        validate_capture('CASE-0027',list(reversed(make_frames('D'))))


def test_unknown_case_fails():
    with pytest.raises(ValueError,match='unknown'):
        validate_capture('CASE-9999',make_frames('D'))


def test_real_client_not_available_is_skip_not_pass(monkeypatch):
    monkeypatch.delenv('VIRTUALPLC_RUN_PYMC',raising=False)
    from tests.compat.test_pymcprotocol_030 import live_client
    with pytest.raises(pytest.skip.Exception):
        live_client()


def test_m10_successful_pytest_without_six_real_raw_requests_is_hold(monkeypatch,tmp_path):
    """A zero exit code from an unrelated test is NOT an accepted real-client run."""
    from scripts import m10_wheel_gate as gate
    from types import SimpleNamespace
    fake_wheel=tmp_path/gate.WHEEL
    fake_wheel.write_bytes(b'not a real wheel')
    monkeypatch.setattr(gate, 'verify_wheel', lambda path: {
        'wheel_filename': gate.WHEEL,'wheel_sha256':gate.EXPECTED,
        'client_version':'0.3.0','source':'mock only'})
    monkeypatch.setattr(gate.subprocess,'run', lambda *a,**kw:
        SimpleNamespace(returncode=0,stdout=b'6 passed in simulated runner\n'))
    dest=tmp_path/'output'
    assert gate.run(fake_wheel,dest)==2
    report=json.loads((dest/'result.json').read_text())
    assert report['status']=='FAIL_MISSING_OR_BAD_RAW_REQUESTS'
    assert report['tests_authoritative'] is False
    assert report['release']=='HOLD'


def test_m14_rejects_missing_raw_requests_in_existing_valid_junit(tmp_path):
    from tests.test_m14_windows_evidence import fake_client_run
    from scripts.m14_windows_evidence import inspect_client_run
    folder=fake_client_run(tmp_path/'proof')
    (folder/'raw_capture'/'CASE-0027.json').unlink()
    with pytest.raises(ValueError):
        inspect_client_run(folder)


def test_m14_rejects_rewritten_raw_request_hash_and_counters(tmp_path):
    from tests.test_m14_windows_evidence import fake_client_run
    from scripts.m14_windows_evidence import inspect_client_run
    folder=fake_client_run(tmp_path/'proof')
    obj=json.loads((folder/'result.json').read_text())
    obj['raw_requests']['file_sha256']['CASE-0027']='0'*64
    (folder/'result.json').write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='raw-capture'):
        inspect_client_run(folder)
