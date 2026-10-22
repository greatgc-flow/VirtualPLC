"""MC protocol 3E binary frame encoding and decoding (M1)."""

from dataclasses import dataclass
import struct

HEADER_SIZE = 9  # subheader 2 + route 5 + length 2
MIN_BODY = 6  # timer 2 + command 2 + subcommand 2


@dataclass(frozen=True)
class Request:
    route: tuple  # (network, pc, io, station)
    timer: int
    command: int
    subcommand: int
    data: bytes


def frame_size(buffer):
    """Total size of the frame starting at buffer, or None until its header is complete."""
    if len(buffer) < HEADER_SIZE:
        return None
    return HEADER_SIZE + int.from_bytes(buffer[7:9], "little")


def decode_request(frame):
    if len(frame) < HEADER_SIZE + MIN_BODY or frame[:2] != b"\x50\x00":
        raise ValueError("not a 3E binary request")
    if frame_size(frame) != len(frame):
        raise ValueError("frame length mismatch")
    network, pc, io, station = struct.unpack("<BBHB", frame[2:7])
    timer, command, subcommand = struct.unpack("<HHH", frame[9:15])
    return Request((network, pc, io, station), timer, command, subcommand, frame[15:])


def encode_response(request, end_code=0, data=b""):
    return (b"\xd0\x00" + struct.pack("<BBHB", *request.route)
            + struct.pack("<HH", 2 + len(data), end_code) + data)


def pack_words(values):
    if not all(0 <= value <= 0xFFFF for value in values):
        raise ValueError("word out of range")
    return struct.pack(f"<{len(values)}H", *values)


def unpack_words(data):
    if len(data) % 2:
        raise ValueError("odd word payload")
    return list(struct.unpack(f"<{len(data) // 2}H", data))


def pack_bits(values):
    if not all(value in (0, 1) for value in values):
        raise ValueError("bit must be 0 or 1")
    padded = list(values) + [0] * (len(values) % 2)
    return bytes(high << 4 | low for high, low in zip(padded[::2], padded[1::2]))


def unpack_bits(data, count):
    if len(data) != (count + 1) // 2:
        raise ValueError("bit payload length mismatch")
    nibbles = [nibble for byte in data for nibble in (byte >> 4, byte & 15)]
    bits, padding = nibbles[:count], nibbles[count:]
    if any(bit > 1 for bit in bits) or any(padding):
        raise ValueError("bad bit nibble")
    return bits
