"""Executable red-phase system tests. Requires a real test server, not shipped here."""
from __future__ import annotations
import json, socket, struct, time, random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from suite.support.wire import (
 request,word_payload,pack_bits,unpack_bits,connect_loopback,transact,
 recv_response,assert_success,assert_protocol_error
)
ROOT=Path(__file__).resolve().parents[2]
CASES=[json.loads(line) for line in (ROOT/'catalog/test_cases.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
LIVE=[case for case in CASES if case['runner']=='live_executable']


def read_words(port,head,qty):
    with connect_loopback(port) as sock:
        rep=transact(sock,request(head=head,points=qty))
        assert rep['endcode']==0, f"read endcode {rep['endcode']:04X}"
        assert len(rep['data'])==qty*2
        assert rep['length']==2+qty*2
        return list(struct.unpack('<'+'H'*qty,rep['data']))

def write_words(port,head,values):
    with connect_loopback(port) as sock:
        rep=transact(sock,request(cmd=0x1401,head=head,points=len(values),payload=word_payload(values)))
        assert_success(rep)

def read_bits(port,head,qty):
    with connect_loopback(port) as sock:
        rep=transact(sock,request(sub=1,head=head,device=0x90,points=qty))
        assert rep['endcode']==0, f"read endcode {rep['endcode']:04X}"
        assert rep['length']==2+len(rep['data'])
        return unpack_bits(rep['data'],qty)

def write_bits(port,head,bits):
    with connect_loopback(port) as sock:
        rep=transact(sock,request(cmd=0x1401,sub=1,head=head,device=0x90,points=len(bits),payload=pack_bits(bits)))
        assert_success(rep)

def fatal_packet(variant):
    base=request(cmd=0x1401,head=777,points=2,payload=word_payload([0x1111,0x2222]))
    if variant=='bad_subheader':return b'\x00\x00'+base
    if variant=='garbage_prefix':return b'\x99\x98\x97'+base
    if variant=='length_too_short':return base[:7]+b'\x01\x00'+base[9:]
    if variant=='length_ffff':return base[:7]+b'\xff\xff'+base[9:]
    if variant=='truncated_header':return base[:8]
    if variant=='truncated_payload':return base[:-1]
    if variant=='unapproved_4e':return bytes.fromhex('54 00 00 00 00 00')+base[2:]
    raise ValueError(variant)

def error_packet(params):
    cmd=params.get('cmd',0x0401);sub=params.get('sub',0);head=params.get('head',777)
    dev=params.get('dev',0xA8);points=params.get('points',1)
    if 'payload_hex' in params:payload=bytes.fromhex(params['payload_hex'])
    elif 'values' in params:payload=word_payload(params['values'])
    else:payload=b''
    return request(cmd=cmd,sub=sub,head=head,device=dev,points=points,payload=payload),cmd,sub

@pytest.mark.parametrize('case',LIVE,ids=lambda c:c['id']+'-'+c['actions']['behavior'])
def test_live_protocol_case(case,server,record_property):
    record_property('case_id',case['id'])
    port=server['port'];a=case['actions'];behavior=a['behavior']
    if behavior=='word_roundtrip':
        write_words(port,a['head'],a['values'])
        assert read_words(port,a['head'],len(a['values']))==a['values']
    elif behavior=='bit_roundtrip':
        write_bits(port,a['head'],a['bits'])
        assert read_bits(port,a['head'],len(a['bits']))==a['bits']
    elif behavior=='framing':
        write_words(port,777,[0x2345]);count=3 if a['method']=='coalesced_three' else 2
        packet=request(head=777,points=1)
        with connect_loopback(port) as sock:
            if a['method'].startswith('coalesced'):
                sock.sendall(packet*count)
            else:
                chunks=([bytes([b]) for b in packet] if a['method']=='bytewise' else
                        [packet[:len(packet)//2],packet[len(packet)//2:]] if a['method']=='half' else
                        [packet[:7],packet[7:14],packet[14:]])
                for b in chunks:sock.sendall(b)
                count=1
            for _ in range(count):assert_success(recv_response(sock),word_payload([0x2345]))
    elif behavior=='fatal_frame':
        # Fatal-frame policy: reject/close; no resynchronization, no side effects.
        write_words(port,777,[0xABCD])
        with connect_loopback(port,timeout=2.5) as sock:
            sock.sendall(fatal_packet(a['variant']))
            if a['variant'] in ('truncated_header','truncated_payload'):
                sock.shutdown(socket.SHUT_WR)
            # Receiver must get EOF or reset, not timeout / arbitrary success frame.
            try:
                value=sock.recv(1)
                assert value==b'',f'fatal packet unexpectedly returned bytes {value.hex()}'
            except (ConnectionResetError,BrokenPipeError):pass
        assert read_words(port,777,1)==[0xABCD]
    elif behavior=='error_reply':
        write_words(port,777,[0xCAFE])
        packet,cmd,sub=error_packet(a['case'])
        with connect_loopback(port) as sock:
            rep=transact(sock,packet)
            assert_protocol_error(rep,cmd,sub)
        assert read_words(port,777,1)==[0xCAFE]

    elif behavior=='multi_client_visibility':
        with connect_loopback(port) as aclient,connect_loopback(port) as bclient:
            assert_success(transact(aclient,request(cmd=0x1401,head=777,points=1,payload=word_payload([999]))))
            assert_success(transact(bclient,request(head=777,points=1)),word_payload([999]))
    elif behavior=='fifo_write_read':
        with connect_loopback(port) as sock:
            w=request(cmd=0x1401,head=777,points=1,payload=word_payload([333]))
            r=request(head=777,points=1)
            sock.sendall(w+r)
            assert_success(recv_response(sock))
            assert_success(recv_response(sock),word_payload([333]))
    elif behavior=='overlap_concurrent':
        va=[0x1111]*16;vb=[0x2222]*16
        def write(vals):
            with connect_loopback(port) as sock:
                for _ in range(10):
                    rep=transact(sock,request(cmd=0x1401,head=700,points=16,payload=word_payload(vals)))
                    assert_success(rep)
        with ThreadPoolExecutor(max_workers=3) as pool:
            f1=pool.submit(write,va);f2=pool.submit(write,vb)
            for _ in range(10):
                seen=read_words(port,700,16)
                assert seen in ([0]*16,va,vb),f'torn vector observed: {seen}'
            f1.result(timeout=5);f2.result(timeout=5)
        assert read_words(port,700,16) in (va,vb)

    elif behavior=='fuzz_fatal_prefix':
        write_words(port,777,[0xABCD]); rng=random.Random(a['seed'])
        for k in range(128):
            head=bytes([rng.randrange(256),rng.randrange(256)])
            if head==b'\x50\x00':head=b'\x00\x50'
            pkt=head+request(head=777,points=1)[2:]
            with connect_loopback(port,timeout=1.5) as sock:
                sock.sendall(pkt)
                try:assert sock.recv(1)==b'',f'not closed on fatal header at seed iter={k}'
                except ConnectionResetError:pass
        assert read_words(port,777,1)==[0xABCD]
    elif behavior=='fuzz_invalid_command':
        write_words(port,777,[0xABCD])
        for k in range(64):
            cmd=0xE000+k
            with connect_loopback(port,timeout=1.5) as sock:
                rep=transact(sock,request(cmd=cmd,head=777,points=1))
                assert_protocol_error(rep,cmd,0)
        assert read_words(port,777,1)==[0xABCD]
    else:pytest.fail('unknown action behavior: '+behavior)
