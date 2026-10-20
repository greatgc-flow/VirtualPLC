"""M6 distinct CASE-ID tests; all traffic is 127.0.0.1 only."""
from __future__ import annotations
import json
from pathlib import Path
import os
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
import pytest
from virtual_plc.server import Server
from virtual_plc.telemetry import Telemetry
from virtual_plc.memory import Memory
from suite.support.wire import request

ROOT=Path(__file__).resolve().parents[1]
CATALOG={x['id']:x for s in (ROOT/'suite/catalog/test_cases.jsonl').read_text().splitlines() if (x:=json.loads(s))}
IDS=['CASE-0032','CASE-0033','CASE-0045','CASE-0051','CASE-0066',
     'CASE-0069','CASE-0115','CASE-0116','CASE-0138','CASE-0139',
     'CASE-0143','CASE-0145']
assert all(CATALOG[c]['phase']=='P0' and CATALOG[c]['runner']=='runtime_adapter' for c in IDS)

@contextmanager
def running(telemetry=None, memory=None):
    with Server(('127.0.0.1',0),telemetry=telemetry,memory=memory) as server:
        th=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01},daemon=True)
        th.start()
        try: yield server
        finally:
            server.shutdown()
            th.join(timeout=2)
            assert not th.is_alive()

def one(port,pkt):
    with socket.create_connection(('127.0.0.1',port),timeout=2) as sock:
        sock.settimeout(2)
        sock.sendall(pkt)
        head=sock.recv(4096)
        return head

def eventually(fn,limit=3):
    until=time.monotonic()+limit
    while time.monotonic()<until:
        if fn():return
        time.sleep(.01)
    assert fn()

@pytest.fixture(scope='module')
def malformed_stress_evidence():
    t=Telemetry(event_capacity=32)
    with running(t) as server:
        for _ in range(1000):
            with socket.create_connection(server.server_address,timeout=2) as sock:
                sock.sendall(b'\x01\x02'+b'\0'*7)
        eventually(lambda:t.snapshot()['counters'].get('framing_error',0)==1000,limit=8)
    return t.snapshot()

@pytest.mark.parametrize('case_id',IDS,ids=IDS)
def test_m6_runtime(case_id,record_property,tmp_path,capsys,malformed_stress_evidence):
    record_property('case_id',case_id)
    t=Telemetry(event_capacity=32)
    if case_id=='CASE-0045':
        with pytest.raises(ValueError): Server(('0.0.0.0',0),telemetry=t)
        with pytest.raises(ValueError): Server(('127.0.0.2',0),telemetry=t)
        with running(t) as server:
            assert server.server_address[0]=='127.0.0.1'
    elif case_id in ('CASE-0032','CASE-0069','CASE-0115','CASE-0138','CASE-0145'):
        m=Memory()
        with running(t,m) as server:
            pkt=request(cmd=0x1401,head=100,points=2,payload=b'\xef\xbe\x34\x12')
            assert one(server.server_address[1],pkt)[9:11]==b'\0\0'
            assert m.read_words(100,2)==[0xBEEF,0x1234]
            eventually(lambda:t.snapshot()['counters'].get('request_ok',0)==1)
        snapshot=t.snapshot()
        blob=json.dumps(snapshot,sort_keys=True)+capsys.readouterr().out
        assert 'BEEF' not in blob and '48879' not in blob and '1234' not in blob
        assert 'device' not in blob.lower() and 'payload' not in blob.lower()
        assert snapshot['sample'][0]['command']==0x1401
    elif case_id=='CASE-0033':
        with running(t) as server:
            port=server.server_address[1]
            for pkt in (request(points=1),request(cmd=0xffff,points=1),request(points=1)):
                one(port,pkt)
            eventually(lambda:sum(t.snapshot()['counters'].get(k,0) for k in ('request_ok','request_error'))==3)
            d=t.snapshot()['counters']
            assert d['request_ok']==2 and d['request_error']==1
    elif case_id=='CASE-0051':
        with running(t) as server:
            for _ in range(80):one(server.server_address[1],request(points=1))
            eventually(lambda:t.snapshot()['counters'].get('request_ok',0)==80)
        snap=t.snapshot()
        assert snap['counters']['request_ok']==80 and len(snap['sample'])<=32
        assert snap['sample_dropped']>=48
    elif case_id=='CASE-0066':
        m=Memory()
        with running(t,m) as server:
            s=socket.create_connection(server.server_address,timeout=2)
            pkt=request(cmd=0x1401,points=1,payload=b'\x34\x12')
            s.sendall(pkt[:-1])
            s.close()
            eventually(lambda:t.snapshot()['counters'].get('eof_mid_frame',0)>=1)
            assert m.read_words(0,1)==[0]
            assert t.snapshot()['counters'].get('request_ok',0)==0
    elif case_id in ('CASE-0116','CASE-0139'):
        snap=malformed_stress_evidence
        assert snap['counters']['framing_error']==1000
        assert len(snap['sample'])<=32 and snap['sample_dropped']>=968
        assert '0102' not in json.dumps(snap)
    elif case_id=='CASE-0143':
        if sys.platform!='linux':
            pytest.skip('Linux SIGTERM local contract; other OS requires manual evidence')
        with socket.socket() as tmp:
            tmp.bind(('127.0.0.1',0));port=tmp.getsockname()[1]
        proc=subprocess.Popen([sys.executable,'-m','virtual_plc','--host','127.0.0.1',
                               '--port',str(port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            def is_ready():
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):return True
                except OSError:return False
            eventually(is_ready,limit=4)
            start=time.monotonic(); proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=3)
            assert proc.returncode==0 and time.monotonic()-start<3
            assert not is_ready()
        finally:
            if proc.poll() is None:proc.kill();proc.wait(timeout=3)
    else:
        raise AssertionError('unimplemented CASE-ID')
