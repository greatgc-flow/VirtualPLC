"""Test-side (NOT DUT) independent 3E binary wire helpers.
No dependency on server implementation. Local loopback only; bounded receives.
"""
from __future__ import annotations
import socket
import struct

REQ3E = bytes.fromhex('50 00')
RESP3E = bytes.fromhex('D0 00')
DEFAULT_ROUTE = bytes.fromhex('00 FF FF 03 00')
MAX_RX = 65535

def pack_bits(bits):
    if not all(type(x) is int and x in (0,1) for x in bits):
        raise ValueError('bit values must be integers 0/1')
    return bytes(((bits[i] << 4) | (bits[i+1] if i+1 < len(bits) else 0)) for i in range(0,len(bits),2))

def unpack_bits(data, count):
    if len(data) != (count+1)//2:
        raise ValueError('response payload length mismatch')
    vals=[]
    for v in data:
        hi,lo = v>>4,v&15
        if hi>1 or lo>1:raise ValueError('non-bit nibble')
        vals.extend((hi,lo))
    if count%2 and data and (data[-1]&15):raise ValueError('odd tail must be zero')
    return vals[:count]

def request(cmd=0x0401,sub=0,head=100,device=0xA8,points=1,payload=b'',route=DEFAULT_ROUTE,monitor=0x10):
    if len(route)!=5:raise ValueError('route length 5')
    if not 0<=head<2**24:raise ValueError('head range')
    if not 0<=points<=65535:raise ValueError('point range')
    body=struct.pack('<HHH',monitor,cmd,sub)+head.to_bytes(3,'little')+bytes([device])+struct.pack('<H',points)+payload
    return REQ3E+route+struct.pack('<H',len(body))+body

def word_payload(values):
    return b''.join(struct.pack('<H',v) for v in values)

def exact(sock,n):
    buf=bytearray()
    while len(buf)<n:
        block=sock.recv(n-len(buf))
        if not block:raise EOFError('connection closed before all expected bytes')
        buf+=block
    return bytes(buf)

def recv_response(sock, max_body=MAX_RX):
    hdr=exact(sock,9)
    if hdr[:2]!=RESP3E:raise AssertionError(f'not 3E response: {hdr[:2].hex()}')
    size=int.from_bytes(hdr[7:9],'little')
    if size<2 or size>max_body:raise AssertionError(f'invalid body size {size}')
    body=exact(sock,size)
    return {'raw':hdr+body,'route':hdr[2:7], 'length':size,'endcode':int.from_bytes(body[:2],'little'), 'data':body[2:]}

def transact(sock,packet):
    sock.sendall(packet)
    return recv_response(sock)

def assert_success(reply,expected_data=b''):
    assert reply['endcode']==0, f"expected success, got {reply['endcode']:04X}"
    assert reply['data']==expected_data, (reply['data'].hex(),expected_data.hex())
    assert reply['length']==2+len(expected_data)

def assert_protocol_error(reply,cmd,sub):
    assert reply['endcode']!=0, 'invalid decoded request wrongly returned success'
    # On 3E command failure response, the 5-byte responding station and original cmd/sub follow endcode.
    assert len(reply['data'])>=9, f"error payload too short {len(reply['data'])}"
    assert reply['data'][5:7]==struct.pack('<H',cmd), 'failed command not returned'
    assert reply['data'][7:9]==struct.pack('<H',sub), 'failed subcommand not returned'
    assert reply['length']==2+len(reply['data'])

def connect_loopback(port,timeout=2.0):
    sock=socket.create_connection(('127.0.0.1',port),timeout=timeout)
    sock.settimeout(timeout)
    return sock
