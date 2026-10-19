"""M4 explicit CASE-ID contracts. Independent from older suite/live packet oracle.

Only IDs in SELECTED are measured. All other catalog IDs remain NOT_RUN.
No external network access: 127.0.0.1 only.
"""
from __future__ import annotations
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import struct
import threading
import time
import pytest
from virtual_plc.memory import Memory
from virtual_plc.protocol import SIMULATED_ERROR
from virtual_plc.server import Server, IDLE_TIMEOUT

ROOT = Path(__file__).resolve().parents[1]
CATALOG = {json.loads(s)['id']: json.loads(s) for s in
           (ROOT/'suite/catalog/test_cases.jsonl').read_text().splitlines() if s.strip()}
DEFAULT_ROUTE = bytes.fromhex('00 ff ff 03 00')
SELECTED = [
    'CASE-0001','CASE-0002','CASE-0003','CASE-0004','CASE-0005',
    'CASE-0008','CASE-0013','CASE-0015','CASE-0017','CASE-0021',
    'CASE-0022','CASE-0026','CASE-0034','CASE-0035','CASE-0036',
    'CASE-0037','CASE-0049','CASE-0050','CASE-0056','CASE-0061',
    'CASE-0062','CASE-0063','CASE-0067','CASE-0070','CASE-0071',
    'CASE-0072','CASE-0073','CASE-0074','CASE-0075','CASE-0076',
    'CASE-0077','CASE-0078','CASE-0079','CASE-0080','CASE-0082',
    'CASE-0083','CASE-0085','CASE-0086','CASE-0087','CASE-0091',
    'CASE-0093','CASE-0098','CASE-0099','CASE-0100','CASE-0101',
    'CASE-0102','CASE-0103','CASE-0107','CASE-0108','CASE-0112',
    'CASE-0114','CASE-0117','CASE-0118','CASE-0119','CASE-0120',
    'CASE-0122','CASE-0127','CASE-0134','CASE-0135','CASE-0136',
    'CASE-0137','CASE-0148','CASE-0030','CASE-0042',
    'CASE-0043','CASE-0053','CASE-0052','CASE-0094','CASE-0096',
    'CASE-0097','CASE-0113','CASE-0125','CASE-0140'
]
assert len(SELECTED) == len(set(SELECTED)) and all(
    CATALOG[c]['runner'] == 'runtime_adapter' and CATALOG[c]['phase']=='P0'
    for c in SELECTED)


def packet(*, cmd=0x0401, sub=0, addr=100, device=0xA8, count=1,
           payload=b'', route=DEFAULT_ROUTE):
    data=(struct.pack('<HHH',0x10,cmd,sub) + addr.to_bytes(3,'little')
          + bytes([device]) + struct.pack('<H',count) + payload)
    return b'\x50\x00' + route + struct.pack('<H',len(data)) + data


def recv_exact(sock,n):
    result=bytearray()
    while len(result)<n:
        more=sock.recv(n-len(result))
        if not more:raise EOFError('response truncated')
        result.extend(more)
    return bytes(result)


def transact(sock,req=b'', expected_route=DEFAULT_ROUTE):
    if req:sock.sendall(req)
    head=recv_exact(sock,9)
    assert head[:2] == b'\xd0\x00' and head[2:7] == expected_route
    body=recv_exact(sock,int.from_bytes(head[7:9],'little'))
    assert len(body)>=2
    return int.from_bytes(body[:2],'little'),body[2:],head


def conn(port):
    sock=socket.create_connection(('127.0.0.1',port),timeout=2)
    sock.settimeout(2)
    return sock


@contextmanager
def server_ctx():
    with Server(('127.0.0.1',0)) as srv:
        t=threading.Thread(target=srv.serve_forever,
            kwargs={'poll_interval':0.01},daemon=True)
        t.start()
        try:yield srv.server_address[1]
        finally:
            srv.shutdown()
            t.join(timeout=3)
            assert not t.is_alive()


def write(port,addr=100,values=(0xABCD,)):
    with conn(port) as s:
        status,rest,_=transact(s,packet(cmd=0x1401,addr=addr,count=len(values),
            payload=struct.pack('<'+'H'*len(values),*values)))
        assert status==0 and rest==b''


def read(port,addr=100,count=1):
    with conn(port) as s:
        code,raw,_=transact(s,packet(addr=addr,count=count))
        assert code==0 and len(raw)==count*2
        return struct.unpack('<'+'H'*count,raw)


def bit_write(port,addr,bits):
    data=bytes(((bits[i]<<4) | (bits[i+1] if i+1<len(bits) else 0))
               for i in range(0,len(bits),2))
    with conn(port) as s:
        code,_,_=transact(s,packet(cmd=0x1401,sub=1,addr=addr,
            device=0x90,count=len(bits),payload=data))
        assert code==0


def error_no_side_effect(port,req,check_addr=100):
    initial=read(port,check_addr)
    with conn(port) as s:
        code,details,head=transact(s,req)
        assert code!=0 and code==SIMULATED_ERROR
        assert int.from_bytes(head[7:9],'little')==2+len(details)
        assert len(details)==9  # echoed route, command, subcommand
        assert details[:5]==DEFAULT_ROUTE
        cmd,sub=struct.unpack_from('<HH',req,11)
        assert details[5:]==struct.pack('<HH',cmd,sub)
    assert read(port,check_addr)==initial


def closed(sock, timeout=2):
    sock.settimeout(timeout)
    try:
        assert sock.recv(1)==b''
    except (ConnectionResetError,ConnectionAbortedError,BrokenPipeError):
        pass


def test_case_identity_partition():
    assert len(SELECTED)==73
    assert all(CATALOG[c]['runner']=='runtime_adapter' for c in SELECTED)


@pytest.mark.parametrize('case_id', SELECTED, ids=SELECTED)
def test_m4_p0_contract(case_id,record_property):
    record_property('case_id',case_id)
    if case_id in {'CASE-0008','CASE-0013','CASE-0015','CASE-0017','CASE-0062','CASE-0067','CASE-0096','CASE-0097','CASE-0094'}:
        m=Memory()
        if case_id=='CASE-0008':
            m.write_words(0,[0,65535]);assert m.read_words(0,2)==[0,65535]
        elif case_id=='CASE-0013':
            prior=m.snapshot()
            for a,v in [(-1,[1]),(9999,[1,2]),(0,[65536])]:
                with pytest.raises(ValueError):m.write_words(a,v)
            assert m.snapshot()==prior
        elif case_id=='CASE-0015':
            m.write_words(20,[42]*96);assert m.read_words(20,96)==[42]*96
        elif case_id=='CASE-0017':
            pre=m.snapshot();m.write_bits(0,[1]);post=m.snapshot()
            assert pre['M'][0]==0 and post['M'][0]==1 and post['version']==pre['version']+1
        elif case_id=='CASE-0062':
            m.write_words(9999,[0xFFFF]);snap=m.snapshot()
            with pytest.raises(ValueError):m.write_words(9999,[1,2])
            assert m.read_words(9999,1)==[0xFFFF] and m.snapshot()==snap
        elif case_id=='CASE-0067':
            snap=m.snapshot()
            with pytest.raises(ValueError):m.write_words(0,[65536])
            assert m.snapshot()==snap
        elif case_id=='CASE-0096':
            snap=m.snapshot()
            with pytest.raises(ValueError):m.write_words(0,[123,456,65536])
            assert m.snapshot()==snap
        elif case_id in {'CASE-0094','CASE-0097'}:
            a,b=[0x1111]*32,[0x2222]*32
            barrier=threading.Barrier(3)
            failure=[]
            def churn(v):
                barrier.wait(timeout=2)
                for _ in range(300):m.write_words(20,v)
            x=threading.Thread(target=churn,args=(a,));y=threading.Thread(target=churn,args=(b,))
            x.start();y.start();barrier.wait(timeout=2)
            for _ in range(300):
                observed=m.read_words(20,32)
                if observed not in ([0]*32,a,b):failure.append(observed)
            x.join(timeout=3);y.join(timeout=3)
            assert not (x.is_alive() or y.is_alive()) and not failure
        return
    if case_id in {'CASE-0026','CASE-0049','CASE-0108','CASE-0134','CASE-0135'}:
        hosts=['0.0.0.0','::','plc.example.invalid','192.0.2.1']
        for host in hosts:
            with pytest.raises(ValueError):Server((host,0))
        return
    with server_ctx() as port:
        if case_id in {'CASE-0030','CASE-0052','CASE-0140'}:
            import random
            rng=random.Random(20261020)
            base=packet(cmd=0x1401,payload=b'\x34\x12')
            raw=[]
            if case_id=='CASE-0030':raw=[base[:7]+b'\xff\xff'+base[9:]]
            elif case_id=='CASE-0140':raw=[base[:n] for n in range(1,10)]
            else:raw=[base[:7]+int(n).to_bytes(2,'little')+base[9:] for n in [0,1,2,3,4,6,8,9,10,11,4097,65535]]
            if case_id=='CASE-0052':
                raw.extend(bytes([rng.randrange(1,256),rng.randrange(256)])+base[2:] for _ in range(60))
            for invalid in raw:
                with conn(port) as s:
                    s.sendall(invalid)
                    if len(invalid)<9:s.shutdown(socket.SHUT_WR)
                    closed(s)
            assert read(port,100)==(0,)
        elif case_id in {'CASE-0042','CASE-0113'}:
            with conn(port) as s:
                begin=time.monotonic()
                s.sendall(packet()[:1])
                if case_id=='CASE-0113':
                    for _ in range(2):
                        time.sleep(0.42)
                        s.sendall(b'\x00')
                closed(s,timeout=2)
                assert time.monotonic()-begin < IDLE_TIMEOUT+0.55
            assert read(port,100)==(0,)
        elif case_id in {'CASE-0043','CASE-0125'}:
            from virtual_plc.server import MAX_SESSIONS
            assert MAX_SESSIONS==16
            held=[]
            try:
                for _ in range(MAX_SESSIONS):
                    s=conn(port)
                    assert transact(s,packet())[0]==0
                    held.append(s)
                with conn(port) as refused:
                    closed(refused)
                if case_id=='CASE-0125':
                    assert transact(held[0],packet())[0]==0
            finally:
                for s in held:s.close()
            assert read(port,100)==(0,)
        elif case_id=='CASE-0053':
            assert read(port,100)==(0,)
        elif case_id in {'CASE-0001','CASE-0070'}:
            assert read(port,100)==(0,)
        elif case_id=='CASE-0002':
            with conn(port) as s:
                for _ in range(2):assert transact(s,packet())[0]==0
        elif case_id in {'CASE-0003','CASE-0075'}:
            with conn(port) as s:
                for b in packet():s.sendall(bytes([b]))
                assert transact(s)[0]==0
        elif case_id in {'CASE-0004','CASE-0076','CASE-0102'}:
            with conn(port) as s:
                if case_id=='CASE-0102':
                    req=(packet(addr=120) + packet(cmd=0x1401,addr=120,
                        payload=b'\x7b\x00') + packet(addr=120))
                    s.sendall(req)
                    assert transact(s)[1]==b'\x00\x00'
                    assert transact(s)[:2]==(0,b'')
                    assert transact(s)[1]==b'\x7b\x00'
                else:
                    count=2 if case_id=='CASE-0004' else 3
                    s.sendall(packet()*count)
                    for _ in range(count):assert transact(s)[:2]==(0,b'\x00\x00')
        elif case_id in {'CASE-0005','CASE-0061','CASE-0073','CASE-0074','CASE-0077','CASE-0112','CASE-0114'}:
            good=packet(cmd=0x1401,payload=b'\x99\x88')
            broken={
                'CASE-0005':b'\x00\x00'+good[2:],
                'CASE-0061':good[:7]+b'\x01\x00'+good[9:],
                'CASE-0073':good[:8],
                'CASE-0074':good[:9],
                'CASE-0077':good[:7]+b'\x01\x00'+good[9:],
                'CASE-0112':good[:7]+b'\xff\xff'+good[9:],
                'CASE-0114':b'\xaa\xbb'+good[2:]+packet(cmd=0x1401,payload=b'\x99\x88'),
            }[case_id]
            with conn(port) as s:
                s.sendall(broken)
                if case_id in {'CASE-0073','CASE-0074'}:s.shutdown(socket.SHUT_WR)
                closed(s)
            assert read(port,100)==(0,)
        elif case_id in {'CASE-0021','CASE-0101'}:
            with conn(port) as a,conn(port) as b:
                assert transact(a,packet(cmd=0x1401,payload=b'\xef\xbe'))[0]==0
                assert transact(b,packet())[:2]==(0,b'\xef\xbe')
        elif case_id=='CASE-0022':
            with conn(port) as s:
                s.sendall(packet(cmd=0x1401,payload=b'\x41\x00')+packet())
                assert transact(s)[:2]==(0,b'')
                assert transact(s)[:2]==(0,b'\x41\x00')
        elif case_id in {'CASE-0034','CASE-0035','CASE-0050','CASE-0086','CASE-0087','CASE-0091','CASE-0093','CASE-0098','CASE-0099','CASE-0100','CASE-0117','CASE-0118','CASE-0119','CASE-0120','CASE-0136','CASE-0137'}:
            requests={
                'CASE-0034':packet(cmd=0x1401,count=2,payload=b'\x01\x00'),
                'CASE-0035':packet(cmd=0x1401,sub=1,device=0x90,count=1,payload=b'\x20'),
                'CASE-0050':packet(cmd=0x1001),
                'CASE-0086':packet(cmd=0x1401,sub=1,device=0x90,count=2,payload=b'\x20'),
                'CASE-0087':packet(cmd=0x1401,sub=1,device=0x90,count=2,payload=b'\x1f'),
                'CASE-0091':packet(count=0),
                'CASE-0093':packet(device=0x9c),
                'CASE-0098':packet(cmd=0x0403),
                'CASE-0099':packet(device=0xff),
                'CASE-0100':packet(cmd=0x1001),
                'CASE-0117':packet(cmd=0x1401,count=3,payload=b'\x01\x00\x02\x00'),
                'CASE-0118':packet(cmd=0x1401,count=1,payload=b'\x01\x00\x02\x00'),
                'CASE-0119':packet(payload=b'\x12\x34'),
                'CASE-0120':packet(cmd=0x1401,sub=1,device=0x90,count=1,payload=b'\x11'),
                'CASE-0136':packet(cmd=0x1001),
                'CASE-0137':packet(cmd=0x1630),
            }
            error_no_side_effect(port,requests[case_id])
        elif case_id=='CASE-0036':
            with conn(port) as s:
                _,_,h=transact(s,packet())
                assert h[2:7]==DEFAULT_ROUTE
        elif case_id in {'CASE-0037','CASE-0122'}:
            invalid=bytes.fromhex('01 ff ff 03 00') if case_id=='CASE-0037' else bytes.fromhex('00 ff ff 03 01')
            with conn(port) as s:
                s.sendall(packet(cmd=0x1401,payload=b'\x45\x23',route=invalid))
                closed(s)
            assert read(port,100)==(0,)
        elif case_id=='CASE-0056':
            assert read(port,100)==(0,)
        elif case_id=='CASE-0063':
            bit_write(port,5,[1,0,1]);
            with conn(port) as s:
                code,raw,_=transact(s,packet(sub=1,device=0x90,addr=5,count=3))
                assert code==0 and raw==b'\x10\x10'
        elif case_id=='CASE-0071':
            write(port,123,(123,))
            with conn(port) as s:assert transact(s,packet(addr=123))[1]==b'\x7b\x00'
            assert read(port,123)==(123,)
        elif case_id=='CASE-0072':
            write(port,123,(987,))
            with conn(port) as s:
                s.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0))
            assert read(port,123)==(987,)
        elif case_id in {'CASE-0078','CASE-0079','CASE-0080'}:
            a,v={'CASE-0078':(0,0),'CASE-0079':(9999,65535),'CASE-0080':(100,0x1234)}[case_id]
            write(port,a,(v,));assert read(port,a)==(v,)
            if case_id=='CASE-0080':
                with conn(port) as s:assert transact(s,packet(addr=a))[1]==b'\x34\x12'
        elif case_id in {'CASE-0082','CASE-0083','CASE-0085'}:
            a,v={'CASE-0082':(0,0),'CASE-0083':(0,1),'CASE-0085':(9999,1)}[case_id]
            bit_write(port,a,[v]);
            with conn(port) as s:
                code,raw,_=transact(s,packet(sub=1,device=0x90,addr=a))
                assert code==0 and raw==bytes([v<<4])
        elif case_id=='CASE-0103':
            with conn(port) as s:
                s.sendall(packet(cmd=0x1401,count=2,payload=b'\x10\x20\x30\x40')[:-1]);s.shutdown(socket.SHUT_WR)
                closed(s)
            assert read(port,100)==(0,)
        elif case_id=='CASE-0107':
            with pytest.raises(OSError):Server(('127.0.0.1',port))
        elif case_id=='CASE-0127':
            with conn(port) as s:
                time.sleep(IDLE_TIMEOUT+0.25)
                closed(s,timeout=1)
        elif case_id=='CASE-0148':
            # New process/model defaults are volatile zero, not persisted.
            write(port,111,(123,))
            assert read(port,111)==(123,)
            with server_ctx() as restarted:
                assert read(restarted,111)==(0,)
        else:
            raise AssertionError(f'no executable oracle implemented for {case_id}')
