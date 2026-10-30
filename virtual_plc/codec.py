"""MC 3E/4E framing and binary/ASCII conversion for both wire classes.

ASCII uses the explicit compat numbering policy: fixed-width decimal addresses.
Command handlers operate on canonical binary payloads for every transport.
"""

from dataclasses import dataclass, replace
import struct

HEADER_SIZE = 9  # subheader 2 + route 5 + length 2
MIN_BODY = 6  # timer 2 + command 2 + subcommand 2 (binary bytes)
FRAMES = ("3E", "4E")
WIRES = ("binary", "ascii")


@dataclass(frozen=True)
class Layout:
    frame: str
    wire: str

    @property
    def scale(self):
        return 2 if self.wire == "ascii" else 1

    @property
    def header_size(self):
        return (HEADER_SIZE + (4 if self.frame == "4E" else 0)) * self.scale

    def number(self, value, size):
        binary = value.to_bytes(size, "little")  # also checks field overflow
        return f"{value:0{size * 2}X}".encode() if self.wire == "ascii" else binary


class LengthError(ValueError):
    """A fixed-width field is truncated or a payload has extra bytes."""


class Reader:
    """Exact-width numeric fields; ASCII hex permits either case, no whitespace."""

    def __init__(self, data, wire, offset=0):
        self.data, self.wire, self.offset = data, wire, offset

    def take(self, size):
        result = self.data[self.offset:self.offset + size]
        if len(result) != size:
            raise LengthError("short field")
        self.offset += size
        return result

    def number(self, size):
        value = self.take(size * (2 if self.wire == "ascii" else 1))
        if self.wire == "ascii":
            if any(char not in b"0123456789abcdefABCDEF" for char in value):
                raise ValueError("invalid hexadecimal field")
            return int(value, 16)
        return int.from_bytes(value, "little")


def _layout(buffer):
    if len(buffer) < 2:
        return None
    if buffer[:2] in (b"\x50\x00", b"\x54\x00"):
        return Layout("4E" if buffer[0] == 0x54 else "3E", "binary")
    if len(buffer) < 4 and buffer[:2] in (b"50", b"54"):
        return None
    if buffer[:4] in (b"5000", b"5400"):
        return Layout("4E" if buffer[:4] == b"5400" else "3E", "ascii")
    raise ValueError("unknown frame header")


@dataclass(frozen=True)
class Request:
    route: tuple  # (network, pc, io, station)
    timer: int
    command: int
    subcommand: int
    data: bytes
    frame: str = "3E"
    wire: str = "binary"
    serial: int = 0


def frame_size(buffer):
    """Total size of the frame starting at buffer, or None until its header is complete."""
    layout = _layout(buffer)
    if layout is None or len(buffer) < layout.header_size:
        return None
    reader = Reader(buffer, layout.wire, layout.header_size - 2 * layout.scale)
    return layout.header_size + reader.number(2)


def decode_request(frame):
    layout = _layout(frame)
    if layout is None or len(frame) < layout.header_size + MIN_BODY * layout.scale:
        raise ValueError("short request")
    if frame_size(frame) != len(frame):
        raise ValueError("frame length mismatch")
    reader = Reader(frame, layout.wire, 2 * layout.scale)
    serial = 0
    if layout.frame == "4E":
        serial = reader.number(2)
        if reader.number(2) != 0:
            raise ValueError("nonzero 4E reserved field")
    route = tuple(reader.number(size) for size in (1, 1, 2, 1))
    reader.number(2)  # length checked above
    timer, command, subcommand = (reader.number(2) for _ in range(3))
    return Request(route, timer, command, subcommand, frame[reader.offset:], layout.frame, layout.wire, serial)


def encode_response(request, end_code=0, data=b"", *, ascii_dword_order="swapped"):
    layout = Layout(request.frame, request.wire)
    if request.wire == "ascii" and data and end_code == 0:
        data = _ascii_response_data(request, data, ascii_dword_order)
    if end_code != 0:
        error_info = (b"".join(layout.number(value, size) for value, size in zip(request.route, (1, 1, 2, 1)))
                      + layout.number(request.command, 2) + layout.number(request.subcommand, 2))
        body = layout.number(end_code, 2) + error_info
    else:
        body = layout.number(end_code, 2) + data
    prefix = b"\xd4\x00" if request.frame == "4E" else b"\xd0\x00"
    if request.wire == "ascii":
        prefix = prefix.hex().upper().encode()
    if request.frame == "4E":
        prefix += layout.number(request.serial, 2) + layout.number(0, 2)
    route = b"".join(layout.number(value, size) for value, size in zip(request.route, (1, 1, 2, 1)))
    return prefix + route + layout.number(len(body), 2) + body


def read_device(reader, profile, *, text_pad=0, ascii_numbering="compat"):
    """Read a descriptor using only the selected profile, never guess its class."""
    wire = profile.wire
    if reader.wire == "ascii":
        device = profile.device_by_ascii(reader.take(wire.ascii_code_size).decode("latin-1"), text_pad=text_pad)
        digits = reader.take(wire.ascii_address_size)
        if device is None:
            raise ValueError("unknown device")
        valid = (b"0123456789abcdefABCDEF" if ascii_numbering == "manual" and device.base == 16 else b"0123456789")
        if any(char not in valid for char in digits):
            raise ValueError("invalid address digits")
        head = int(digits, device.base if ascii_numbering == "manual" else 10)
    else:
        head = reader.number(wire.address_size)
        device = profile.device_by_code(reader.number(wire.code_size))
    if device is None:
        raise ValueError("unknown device")
    return device, head


def normalize_request(request, profile, *, ascii_dword_order="swapped", text_pad=0, ascii_numbering="compat"):
    """Convert an ASCII command payload to the existing binary handler format.

    A payload error is returned by dispatch as an end code, not a framing close.
    Exact field widths reject overlong client addresses without truncating them.
    """
    if request.wire == "binary":
        return request
    reader = Reader(request.data, "ascii")
    wire = profile.wire

    def descriptor():
        device, head = read_device(reader, profile, text_pad=text_pad, ascii_numbering=ascii_numbering)
        return head.to_bytes(wire.address_size, "little") + device.code.to_bytes(wire.code_size, "little")

    command, subcommand = request.command, request.subcommand
    data = bytearray()
    if command in (0x0401, 0x1401):
        data += descriptor()
        points = reader.number(2)
        data += points.to_bytes(2, "little")
        if command == 0x1401:
            if subcommand == wire.bit_subcommand:
                data += pack_bits([char - 48 for char in reader.take(points)])
            else:
                data += pack_words([reader.number(2) for _ in range(points)])
    elif command in (0x0403, 0x1402):
        bit = subcommand == wire.bit_subcommand
        counts = [reader.number(1) for _ in range(1 if bit else 2)]
        data += bytes(counts)
        for count, width in zip(counts, (wire.bit_value_size,) if bit else (2, 4)):
            for _ in range(count):
                data += descriptor()
                if command == 0x1402:
                    value = _ascii_dword_value(reader.number(width), width, ascii_dword_order)
                    data += value.to_bytes(width, "little")
    elif command == 0x0619:
        size = reader.number(2)
        data += size.to_bytes(2, "little") + reader.take(size)
    if reader.offset != len(reader.data):
        raise ValueError("payload length mismatch or overwidth address")
    return replace(request, data=bytes(data))


def _ascii_dword_value(value, width, order):
    """Exchange the two word halves only for an ASCII dword in swapped mode."""
    return ((value & 0xFFFF) << 16) | (value >> 16) if width == 4 and order == "swapped" else value


def _ascii_response_data(request, data, ascii_dword_order):
    reader = Reader(data, "binary")
    layout = Layout(request.frame, "ascii")
    if request.command == 0x0101:
        return reader.take(16) + layout.number(reader.number(2), 2)
    if request.command == 0x0619:
        return layout.number(reader.number(2), 2) + data[2:]
    if request.command == 0x0401 and request.subcommand in (1, 3):
        points = Reader(request.data, "ascii", len(request.data) - 4).number(2)
        return bytes(48 + bit for bit in unpack_bits(data, points))
    counts = ((len(data) // 2, 2),)
    if request.command == 0x0403:
        sizes = Reader(request.data, "ascii")
        counts = ((sizes.number(1), 2), (sizes.number(1), 4))
    return b"".join(layout.number(_ascii_dword_value(reader.number(width), width, ascii_dword_order), width)
                    for count, width in counts for _ in range(count))


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
