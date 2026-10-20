"""M22 bounded load metrics: case IDs intentionally absent (not P0 external evidence)."""
import json
import os
import struct
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from scripts import m22_soak as m


@pytest.mark.parametrize('plan', [(1,), (1,4), (1,4,8), [2,8]])
def test_allowed_ramps(plan):
    assert m.validate_plan(plan,3) == (tuple(plan),3)


@pytest.mark.parametrize('plan', [None, [], [0], [-1], [9], [True], [1,1], [4,1],
                                     [1,2,3,4], ['4'], [1,4,8,9], [1,False]])
def test_invalid_ramps_rejected(plan):
    with pytest.raises(ValueError): m.validate_plan(plan, 3)


@pytest.mark.parametrize('iterations', [None, True, 0, -1, 2001, '1', 1.5])
def test_invalid_iterations(iterations):
    with pytest.raises(ValueError): m.validate_plan([1], iterations)


def test_percentiles_nearest_rank():
    data = [90, 50, 10, 80, 20, 40, 70, 30, 60, 100]
    assert (m.nearest_rank(data,50),m.nearest_rank(data,95),m.nearest_rank(data,99)) == (50,100,100)
    assert m.nearest_rank([17],99) == 17


@pytest.mark.parametrize('data,p', [([], 99),([1],0),([1],101),([1],True)])
def test_invalid_percentiles(data,p):
    with pytest.raises(ValueError): m.nearest_rank(data,p)


def test_trend_only_with_observed_samples():
    assert m.rss_trend_kib_per_minute([]) is None
    assert m.rss_trend_kib_per_minute([(1,20),(2,30)]) is None
    assert m.rss_trend_kib_per_minute([(0,100),(1,102),(2,104)]) == 120.0


@pytest.mark.parametrize('args', [
    (0x0401, 0, 0xA8, 1), (0x1401, 1, 0x90, [1,0,1]),
    (0x1401, 0, 0xA8, [0,65535])
])
def test_wire_header_length_and_command(args):
    cmd, sub, dev, value = args
    msg = m.frame(cmd,sub,10,dev,value)
    assert msg[:2] == m.REQUEST_HEADER
    assert msg[2:7] == m.ROUTE
    assert int.from_bytes(msg[7:9], 'little') == len(msg)-9
    assert struct.unpack_from('<H',msg,11)[0] == cmd
    assert struct.unpack_from('<H',msg,13)[0] == sub
    assert msg[18] == dev


@pytest.mark.parametrize('args', [
    (0x1234, 0, 0xA8, 1), (0x0401, 0, 0x90, 1), (0x0401, 1, 0xA8, 1),
    (0x0401, 0, 0xA8, 0), (0x1401, 0, 0xA8, []),
    (0x1401, 0, 0xA8, [65536]), (0x1401, 1, 0x90, [2]),
    (0x1401, 1, 0x90, [True]), (0x0401, 0, 0xA8, True),
])
def test_invalid_frames_rejected(args):
    with pytest.raises(ValueError): m.frame(args[0],args[1],100,args[2],args[3])


class FakeSocket:
    def __init__(self, response): self.buf = bytearray(response);self.sent = []
    def sendall(self,data): self.sent.append(data)
    def recv(self,n):
        payload=bytes(self.buf[:n]);del self.buf[:n];return payload


def test_fragmented_valid_response():
    payload = struct.pack('<HH', 1,65535)
    response = m.RESPONSE_HEADER + m.ROUTE + struct.pack('<H',len(payload)+2) + b'\x00\x00' + payload
    sock = FakeSocket(response)
    answer, duration = m.exchange(sock,b'hello')
    assert answer==payload and duration>=0 and sock.sent==[b'hello']


@pytest.mark.parametrize('response', [
    b'',
    b'\x50\x00' + m.ROUTE + b'\x02\x00' + b'\x00\x00',
    m.RESPONSE_HEADER + bytes(5) + b'\x02\x00' + b'\x00\x00',
    m.RESPONSE_HEADER + m.ROUTE + b'\x01\x00' + b'\x00',
    m.RESPONSE_HEADER + m.ROUTE + b'\x02\x00' + b'\x59\xc0',
    m.RESPONSE_HEADER + m.ROUTE + b'\x04\x00' + b'\x00\x00\x01',
])
def test_invalid_replies_rejected(response):
    with pytest.raises((ConnectionError, ValueError)):
        m.exchange(FakeSocket(response),b'cmd')


def test_rss_reads_own_process_or_unavailable():
    assert m.read_rss_kib(0) is None
    assert m.read_rss_kib(True) is None
    value = m.read_rss_kib(os.getpid())
    assert value is None or value>0


def test_one_client_load_is_real_loopback():
    stage=m.measure_stage(1,3)
    assert stage['requests_ok']==12 and stage['requests_failed']==0
    assert stage['connections_successful']==1
    assert stage['p50_us']<=stage['p95_us']<=stage['p99_us']<=stage['max_us']
    assert stage['rss_scope']=='isolated_server_child_process_only'
    assert stage['sessions_active_observed'] is None


def test_max_8_clients_bounded_load():
    stage=m.measure_stage(8,2)
    assert stage['requests_ok']==64 and stage['connections_successful']==8
    assert stage['rss_peak_observed_kib'] is None or stage['rss_peak_observed_kib'] > 0


def test_full_run_creates_immutable_local_evidence(tmp_path):
    out=tmp_path/'fresh'
    report=m.run(out, [1,4], 2)
    assert report['release']=='HOLD'
    assert report['status'] in ('MEASURED_NOT_CERTIFIED','HOLD_RSS_UNAVAILABLE')
    assert [s['requests_ok'] for s in report['stages']]==[8,32]
    assert m.verify_evidence(out)==report
    assert (out/'console.log').read_text().endswith('RELEASE=HOLD\n')
    assert ET.parse(out/'junit.xml').getroot().tag == 'testsuite'
    with pytest.raises(FileExistsError):m.run(out,[1],1)


def test_fail_closed_on_stage_error_and_keeps_evidence(tmp_path, monkeypatch):
    def die(*args): raise TimeoutError('no secrets in the report')
    monkeypatch.setattr(m,'measure_stage',die)
    out=tmp_path/'failure'
    result=m.run(out,[1],1)
    assert result['status']=='HOLD_EXECUTION_FAILED'
    assert result['failure_type']=='TimeoutError'
    assert 'no secrets' not in (out/'report.json').read_text()
    assert m.verify_evidence(out)['release']=='HOLD'
    assert int(ET.parse(out/'junit.xml').getroot().attrib['failures'])>0


def test_source_tree_output_forbidden(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):m.run(tmp_path/'nested',[1],1)
    assert not (tmp_path/'nested').exists()


@pytest.mark.parametrize('file', ['report.json','console.log','junit.xml','MANIFEST_SHA256.json'])
def test_detects_evidence_tamper(tmp_path,file):
    out=tmp_path/'fresh'
    m.run(out,[1],1)
    (out/file).write_bytes((out/file).read_bytes()+b'X')
    with pytest.raises((ValueError, json.JSONDecodeError)):
        m.verify_evidence(out)


def test_do_not_claim_external_p0_or_vendor_certification(tmp_path):
    out=tmp_path/'fresh'
    result=m.run(out,[1],1)
    assert result['not_a_certification'] is True
    assert result['release']=='HOLD'
    assert 'CASE-' not in (out/'junit.xml').read_text()
    assert result['loopback_only'] is True
    assert result['policy'].startswith('descriptive')
