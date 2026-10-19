"""Isolated Q-profile 3E Binary batch D(word)/M(bit) wire codec.

PROTOTYPE: 0xC059 is a configurable-simulator INTERNAL placeholder for any
complete-but-unsupported command. It is NOT a verified vendor error map.
"""
from __future__ import annotations
import struct
from .memory import Memory

REQUEST_HEADER=b'\x50\x00'
REPLY_HEADER=b'\xd0\x00'
# Distinctly unverified and restricted to loopback prototype
SIMULATED_ERROR=0xC059
MAX_BODY=4096

class FrameError(Exception):
    """Fatal frame framing violation: close connection with no memory side effect."""


def reply(route:bytes,code:int,data:bytes=b'')->bytes:
    body=struct.pack('<H',code)+data
    return REPLY_HEADER + route + struct.pack('<H',len(body)) + body


def nibble_unpack(raw:bytes,points:int)->list[int]:
    if len(raw)!=(points+1)//2:
        raise ValueError('wrong number of packed bits')
    bits=[]
    for byte in raw:
        h,l=byte>>4,byte&15
        if h not in (0,1) or l not in (0,1):raise ValueError('invalid bit nibble')
        bits.extend((h,l))
    if points&1 and raw[-1]&15:raise ValueError('odd trailing nibble not zero')
    return bits[:points]


def nibble_pack(bits:list[int])->bytes:
    return bytes((bits[i]<<4) | (bits[i+1] if i+1<len(bits) else 0) for i in range(0,len(bits),2))


def process(route:bytes,body:bytes,memory:Memory)->bytes:
    # complete frame with invalid command fields returns an SLMP error structure.
    # structurally incomplete requests are fatal and never mutate state.
    if len(body)<12:
        raise FrameError('request body must include 12-byte command header')
    _,cmd,sub=struct.unpack_from('<HHH',body,0)
    head=int.from_bytes(body[6:9],'little')
    dev=body[9]
    qty=struct.unpack_from('<H',body,10)[0]
    payload=body[12:]
    try:
        if cmd not in (0x0401,0x1401):raise ValueError('unsupported command')
        if (sub,dev) not in ((0,0xA8),(1,0x90)):
            raise ValueError('unsupported device/subcommand')
        if not 1 <= qty <= 960:
            raise ValueError('unsupported quantity')
        is_write=cmd==0x1401
        if not is_write and payload:
            raise ValueError('read trailing payload')
        if sub==0:
            if is_write:
                if len(payload)!=qty*2:raise ValueError('malformed word data')
                values=list(struct.unpack('<'+'H'*qty,payload))
                memory.write_words(head,values)
                data=b''
            else:
                values=memory.read_words(head,qty)
                data=struct.pack('<'+'H'*qty,*values)
        else:
            if is_write:
                values=nibble_unpack(payload,qty)
                memory.write_bits(head,values)
                data=b''
            else:
                data=nibble_pack(memory.read_bits(head,qty))
        return reply(route,0,data)
    except ValueError:
        # failure response: responding-station 5 bytes followed by command/subcmd.
        return reply(route,SIMULATED_ERROR,route + struct.pack('<HH',cmd,sub))
