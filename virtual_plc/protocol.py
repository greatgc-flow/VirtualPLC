"""Loopback-only 3E Binary Q-profile D/M batch command prototype.

SIMULATED_ERROR is a placeholder, not an officially verified PLC end code.
Do not claim real-device fidelity before G0-E/G0-C verification.
"""
from __future__ import annotations
import struct
from .memory import Memory

REQUEST_HEADER = b"\x50\x00"
REPLY_HEADER = b"\xd0\x00"
SIMULATED_ERROR = 0xC059
MAX_BODY = 4096

class FrameError(Exception):
    """Fatal framing violation: close connection without changing memory."""

def reply(route: bytes, code: int, data: bytes = b"") -> bytes:
    body = struct.pack("<H", code) + data
    return REPLY_HEADER + route + struct.pack("<H", len(body)) + body

def nibble_unpack(raw: bytes, points: int) -> list[int]:
    if len(raw) != (points + 1) // 2:
        raise ValueError("wrong packed bit count")
    bits = []
    for byte in raw:
        high, low = byte >> 4, byte & 15
        if high not in (0, 1) or low not in (0, 1):
            raise ValueError("invalid bit nibble")
        bits.extend((high, low))
    if points % 2 and raw[-1] & 15:
        raise ValueError("odd trailing nibble must be zero")
    return bits[:points]

def nibble_pack(bits: list[int]) -> bytes:
    return bytes((bits[i] << 4) | (bits[i + 1] if i + 1 < len(bits) else 0)
                 for i in range(0, len(bits), 2))

def process(route: bytes, body: bytes, memory: Memory) -> bytes:
    if len(body) < 12:
        raise FrameError("incomplete command")
    _, cmd, sub = struct.unpack_from("<HHH", body, 0)
    head = int.from_bytes(body[6:9], "little")
    device = body[9]
    count = struct.unpack_from("<H", body, 10)[0]
    payload = body[12:]
    try:
        if cmd not in (0x0401, 0x1401):
            raise ValueError("unsupported command")
        if (sub, device) not in ((0, 0xA8), (1, 0x90)):
            raise ValueError("unsupported subcommand/device")
        if not 1 <= count <= 960:
            raise ValueError("unsupported point count")
        write = cmd == 0x1401
        if not write and payload:
            raise ValueError("unexpected read payload")
        if sub == 0:
            if write:
                if len(payload) != count * 2:
                    raise ValueError("incorrect word payload size")
                memory.write_words(head, list(struct.unpack("<" + "H" * count, payload)))
                data = b""
            else:
                data = struct.pack("<" + "H" * count, *memory.read_words(head, count))
        else:
            if write:
                memory.write_bits(head, nibble_unpack(payload, count))
                data = b""
            else:
                data = nibble_pack(memory.read_bits(head, count))
        return reply(route, 0, data)
    except ValueError:
        # Provisional simulator error payload; vendor-specific policy remains OPEN.
        return reply(route, SIMULATED_ERROR, route + struct.pack("<HH", cmd, sub))
