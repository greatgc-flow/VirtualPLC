"""Seed-replayable M11 differential D/M wire model, local-only.

These 24 samples strengthen internal consistency. They intentionally DO NOT
claim vendor-specific error-code validity, Windows portability, or actual
pymcprotocol interoperability; no new P0 CASE-ID is assigned.
"""
from __future__ import annotations
import random
import struct
import pytest
from virtual_plc.memory import Memory
from virtual_plc.protocol import process, SIMULATED_ERROR

ROUTE = bytes.fromhex('00 FF FF 03 00')


def pack(kind, write, address, values):
    sub, dev = (0, 0xA8) if kind == 'D' else (1, 0x90)
    payload = b''
    if write:
        if kind == 'D':
            payload = struct.pack('<' + 'H'*len(values), *values)
        else:
            payload = bytes((values[i] << 4) | (values[i+1] if i+1<len(values) else 0)
                            for i in range(0, len(values), 2))
    return (struct.pack('<HHH', 0x10, 0x1401 if write else 0x0401, sub)
            + address.to_bytes(3, 'little') + bytes([dev])
            + struct.pack('<H', len(values)) + payload)


def interpret(raw):
    assert raw[:2] == b'\xD0\x00'
    assert raw[2:7] == ROUTE
    n = int.from_bytes(raw[7:9], 'little')
    assert n == len(raw) - 9
    return int.from_bytes(raw[9:11], 'little'), raw[11:]


def decode(kind, payload, count):
    if kind == 'D':
        assert len(payload) == 2*count
        return list(struct.unpack('<' + 'H'*count, payload))
    assert len(payload) == (count + 1) // 2
    values = []
    for v in payload:
        values.extend((v >> 4, v & 15))
    return values[:count]


@pytest.mark.parametrize('seed', list(range(24)))
def test_model_round_trip_metamorphic(seed):
    rand = random.Random(0xC0FFEE + seed)
    mem = Memory(d_size=256, m_size=256)
    expected = {'D': [0]*256, 'M': [0]*256}
    for _ in range(120):
        kind = rand.choice(('D', 'M'))
        offset = rand.randrange(0, 256)
        count = rand.randint(1, min(48, 256-offset))
        data = [rand.randint(0, 65535 if kind == 'D' else 1) for _ in range(count)]
        write_reply = process(ROUTE, pack(kind, True, offset, data), mem)
        code, extra = interpret(write_reply)
        assert code == 0 and extra == b''
        expected[kind][offset:offset+count] = data
        read_reply = process(ROUTE, pack(kind, False, offset, data), mem)
        code, extra = interpret(read_reply)
        assert code == 0
        assert decode(kind, extra, count) == expected[kind][offset:offset+count]
        # Negative write crosses configured capacity: simulator error, no mutation.
        if rand.randrange(5) == 0:
            before = mem.snapshot()
            oversized = pack(kind, True, 255, data[:2] if len(data)>1 else data+[1])
            code, info = interpret(process(ROUTE, oversized, mem))
            assert code == SIMULATED_ERROR and len(info) == 9
            assert mem.snapshot() == before
    state = mem.snapshot()
    assert tuple(expected['D']) == state['D']
    assert tuple(expected['M']) == state['M']
