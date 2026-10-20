"""M12 independent fault matrix, NOT a substitute for the real pymcprotocol wheel.

No new P0 case IDs are asserted here; these are regression/protocol probes.
All network I/O is loopback-only. Tests use deterministic seeds.
"""
from __future__ import annotations
import random
import socket
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from virtual_plc.memory import Memory
from virtual_plc.protocol import process, SIMULATED_ERROR, FrameError, MAX_BODY
from virtual_plc.server import Server

ROUTE = bytes.fromhex('00ffff0300')

def request(*, command=0x0401, sub=0, device=0xA8, head=50, qty=1, payload=b'', timer=0x10):
    return struct.pack('<HHH', timer, command, sub) + head.to_bytes(3, 'little') + bytes((device,)) + struct.pack('<H', qty) + payload

def decoded(mem, **fields):
    packet = process(ROUTE, request(**fields), mem)
    assert packet[:2] == b'\xd0\x00'
    assert packet[2:7] == ROUTE
    assert int.from_bytes(packet[7:9], 'little') == len(packet) - 9
    return int.from_bytes(packet[9:11], 'little'), packet[11:]

@pytest.mark.parametrize('head,qty', [
    (0,1),(0,960),(1,960),(9999,1),(9040,960),
    (17,1),(17,2),(17,5),(17,16),(17,257),
])
def test_word_read_independent_byte_order(head,qty):
    mem=Memory()
    vals=[((i*257)^0xC3A5)&0xFFFF for i in range(qty)]
    mem.write_words(head,vals)
    status,wire=decoded(mem,head=head,qty=qty)
    assert status==0
    assert wire==b''.join(v.to_bytes(2,'little') for v in vals)

@pytest.mark.parametrize('size', [1,2,3,4,5,6,7,8,9,10,63,64,255,256,959,960])
def test_bit_packing_against_independent_bit_pairs(size):
    mem=Memory()
    rng=random.Random(size*1129)
    vals=[rng.randrange(2) for _ in range(size)]
    mem.write_bits(100,vals)
    status,raw=decoded(mem,sub=1,device=0x90,head=100,qty=size)
    expected=bytes((vals[i]*16+(vals[i+1] if i+1<size else 0))
                   for i in range(0,size,2))
    assert status==0
    assert raw==expected

@pytest.mark.parametrize('invalid', [
    {'head':10000}, {'head':9999,'qty':2}, {'head':10000,'qty':960},
    {'qty':0}, {'qty':961}, {'qty':65535},
    {'command':0xFFFF}, {'command':0x0000},
    {'device':0x90}, {'sub':1,'device':0xA8}, {'sub':2},
    {'payload':b'\x00'},
    {'command':0x1401,'qty':2,'payload':b'\x12\x34'},
    {'command':0x1401,'qty':1,'payload':b'\x12\x34\x56'},
    {'command':0x1401,'sub':1,'device':0x90,'qty':1,'payload':b'\x12'},
    {'command':0x1401,'sub':1,'device':0x90,'qty':2,'payload':b'\x22'},
    {'command':0x1401,'sub':1,'device':0x90,'qty':3,'payload':b'\x10'},
])
def test_rejected_command_does_not_mutate_any_device(invalid):
    mem=Memory()
    mem.write_words(50,[0xAABB])
    mem.write_bits(50,[1])
    before=mem.snapshot()
    code,_=decoded(mem,**invalid)
    assert code==SIMULATED_ERROR
    assert mem.snapshot()==before

@pytest.mark.parametrize('missing', [b'',b'\0',b'\0'*3,b'\0'*11])
def test_incomplete_command_never_mutates(missing):
    mem=Memory()
    before=mem.snapshot()
    with pytest.raises(FrameError):
        process(ROUTE,missing,mem)
    assert mem.snapshot()==before

def test_concurrent_whole_vector_reads_stay_consistent():
    mem=Memory()
    a=[0x1111]*100
    b=[0xEEEE]*100
    def writer(values):
        for _ in range(600):
            mem.write_words(100,values)
    with ThreadPoolExecutor(max_workers=3) as workers:
        f1=workers.submit(writer,a)
        f2=workers.submit(writer,b)
        for _ in range(400):
            code,data=decoded(mem,head=100,qty=100)
            assert code==0
            assert data in (bytes(200),b'\x11\x11'*100,b'\xee\xee'*100)
        f1.result(timeout=5)
        f2.result(timeout=5)

def _exact(sock,n):
    chunks=[]
    while n:
        packet=sock.recv(n)
        if not packet:raise EOFError('closed early')
        chunks.append(packet)
        n-=len(packet)
    return b''.join(chunks)

@pytest.fixture
def running():
    server=Server(('127.0.0.1',0))
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01},daemon=True)
    thread.start()
    try:
        yield server,server.server_address[1]
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
        assert not thread.is_alive()

def _exchange(sock,body,fragments=None):
    pkt=b'\x50\x00'+ROUTE+len(body).to_bytes(2,'little')+body
    if fragments:
        for start,end in fragments:
            sock.sendall(pkt[start:end])
    else: sock.sendall(pkt)
    header=_exact(sock,9)
    assert header[:2]==b'\xd0\x00'
    return _exact(sock,int.from_bytes(header[7:9],'little'))

def test_wire_max_supported_word_read(running):
    _,port=running
    with socket.create_connection(('127.0.0.1',port),timeout=2) as sock:
        sock.settimeout(2)
        body=_exchange(sock,request(qty=960))
        assert body==b'\x00\x00'+bytes(960*2)

def test_wire_bytewise_partial_frame_and_followup(running):
    _,port=running
    with socket.create_connection(('127.0.0.1',port),timeout=2) as sock:
        sock.settimeout(2)
        body=request(qty=3)
        pkt_size=9+len(body)
        for index in range(pkt_size):
            fragment=[(index,index+1)]
            if index==0:
                # Send first byte manually; remaining byte fragments below.
                pkt=b'\x50\x00'+ROUTE+len(body).to_bytes(2,'little')+body
            sock.sendall(pkt[index:index+1])
        hdr=_exact(sock,9)
        assert int.from_bytes(hdr[7:9],'little')==8
        assert _exact(sock,8)==b'\0'*8
        assert _exchange(sock,request(qty=1))==b'\0'*4

def test_network_response_isolated_after_invalid_command(running):
    _,port=running
    with socket.create_connection(('127.0.0.1',port),timeout=2) as sock:
        sock.settimeout(2)
        error=_exchange(sock,request(command=0xFFFF))
        assert int.from_bytes(error[:2],'little')==SIMULATED_ERROR
        assert _exchange(sock,request(qty=1))==b'\0'*4
