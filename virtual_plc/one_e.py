"""Opt-in MELSEC iQ-F SLMP 1E batch adapter; not an FX5 hardware profile.

JY997D56001-K pp.41-49, 119-127, 137-138. 1E has no generic
data-length header: the first command byte determines a bounded request size.
This module does not alter the existing 3E/4E codec or PLC memory ownership.
"""

from .memory import OutOfRange

# Deliberately narrow, manual-described FX5 CPU device subset. Other devices
# are refused, rather than inheriting the synthetic Q CPU's entire catalog.
DEVICES = {
    "M": ("bit", 7679), "X": ("bit", 255), "Y": ("bit", 255),
    "D": ("word", 7999),
}
READ_MAX = {0: 256, 1: 64}
WRITE_MAX = {2: 160, 3: 64}
ERROR = {
    "bit_points": 0xC051, "word_points": 0xC052,
    "address": 0xC056, "device": 0xC05B,
    "request": 0xC05C, "bit_data": 0xC060,
}
MAX_1E_REQUEST = 512


def _command_and_wire(buffer):
    if not buffer:
        return None
    first = buffer[0]
    if first == 0x30:  # ASCII 00, 01, 02, 03; requires both bytes
        if len(buffer) < 2:
            return None
        if buffer[1] not in (0x30, 0x31, 0x32, 0x33):
            raise ValueError("unsupported or malformed 1E ASCII subheader")
        return buffer[1] - 0x30, "ascii"
    if first in (0, 1, 2, 3):
        return first, "binary"
    raise ValueError("unknown 1E subheader (3E/4E not accepted)")


def _hex_number(raw):
    if not raw or any(c not in b"0123456789ABCDEFabcdef" for c in raw):
        raise ValueError("invalid 1E hexadecimal field")
    return int(raw, 16)


def frame_size_1e(buffer):
    """Size one bounded 1E batch request, or None if its fixed header is partial.

    Invalid/unsupported subheaders fail CLOSED; no guess at unknown command
    lengths and no fallback to the 3E/4E parser.
    """
    item = _command_and_wire(buffer)
    if item is None:
        return None
    command, wire = item
    header = 24 if wire == "ascii" else 12
    if len(buffer) < header:
        return None
    count = _hex_number(buffer[20:22]) if wire == "ascii" else buffer[10]
    if command == 0 and count == 0:  # vendor special count=00 means 256 bit points
        count = 256
    # Invalid count still yields a response error if the payload can be framed.
    if command < 2:
        data_size = 0
    elif command == 2:
        data_size = count if wire == "ascii" else (count + 1) // 2
    else:
        data_size = count * (4 if wire == "ascii" else 2)
    result = header + data_size
    if result > MAX_1E_REQUEST:
        raise ValueError("1E request exceeds bounded maximum")
    return result


def _parse(buffer):
    layout = _command_and_wire(buffer)
    if layout is None:
        raise ValueError("short 1E command")
    command, wire = layout
    if frame_size_1e(buffer) != len(buffer):
        raise ValueError("1E frame length mismatch")
    if wire == "ascii":
        if buffer[2:4].upper() != b"FF" or _hex_number(buffer[4:8]) != 0:
            raise ValueError("1E PC number or monitoring timer invalid")
        name = bytes.fromhex(buffer[8:12].decode("ascii")).decode("ascii").strip()
        head = _hex_number(buffer[12:20])
        count = _hex_number(buffer[20:22])
        if buffer[22:24] != b"00":
            raise ValueError("1E fixed field must be zero")
        data = buffer[24:]
    else:
        if buffer[1] != 0xff or buffer[2:4] != b"\x00\x00":
            raise ValueError("1E PC number or monitoring timer invalid")
        name = buffer[8:10][::-1].decode("ascii").strip()
        head = int.from_bytes(buffer[4:8], "little")
        count = buffer[10]
        if buffer[11] != 0:
            raise ValueError("1E fixed field must be zero")
        data = buffer[12:]
    if command == 0 and count == 0:
        count = 256
    return command, wire, name, head, count, data


def _response(command, wire, code=0, payload=b""):
    if wire == "ascii":
        prefix = f"{command | 0x80:02X}".encode()
        if code:
            return prefix + b"5B" + f"{code:04X}".encode()
        return prefix + b"00" + payload
    prefix = bytes((command | 0x80,))
    if code:
        return prefix + b"\x5b" + code.to_bytes(2, "little")
    return prefix + b"\x00" + payload


def _word_to_bits(word):
    return [(word >> bit) & 1 for bit in range(16)]


def dispatch_1e(frame, memory, max_points=None):
    """Return a complete 1E answer for a validly framed request.

    Caller MUST hold Server._request_lock when invoking this function.
    No physical PLC, external module connection or firmware parity is implied.
    """
    command, wire, name, head, points, data = _parse(frame)
    device = DEVICES.get(name)
    if device is None:
        return _response(command, wire, ERROR["device"])
    kind, maximum = device
    bit_command = command in (0, 2)
    if bit_command and kind != "bit":
        return _response(command, wire, ERROR["request"])
    cap = (READ_MAX if command < 2 else WRITE_MAX)[command]
    if not bit_command and kind == "bit":
        cap = 32 if command == 1 else 10
    count = points if kind == "word" or bit_command else points * 16
    if points < 1 or points > cap or (max_points is not None and count > max_points):
        return _response(command, wire, ERROR["bit_points" if bit_command else "word_points"])
    if not bit_command and kind == "bit" and head % 16:
        return _response(command, wire, ERROR["request"])
    if head + count - 1 > maximum:
        return _response(command, wire, ERROR["address"])
    try:
        if command == 0:  # bit read; nibble packing (higher nibble = earlier bit)
            bits = memory.read_bits(name, head, points)
            payload = (bytes(48 + x for x in bits) if wire == "ascii"
                       else bytes((bits[i] << 4 | (bits[i + 1] if i + 1 < points else 0))
                                  for i in range(0, points, 2)))
        elif command == 1:  # word read; bit devices grouped in 16-point words
            if kind == "word":
                words = memory.read_words(name, head, points)
            else:
                bits = memory.read_bits(name, head, count)
                words = [sum(bit << k for k, bit in enumerate(bits[i:i + 16]))
                         for i in range(0, count, 16)]
            payload = (b"".join(f"{word:04X}".encode() for word in words)
                       if wire == "ascii" else b"".join(word.to_bytes(2, "little") for word in words))
        elif command == 2:  # bit write
            if wire == "ascii":
                if len(data) != points or any(c not in b"01" for c in data):
                    return _response(command, wire, ERROR["bit_data"])
                bits = [c - 48 for c in data]
            else:
                if len(data) != (points + 1) // 2:
                    return _response(command, wire, ERROR["bit_data"])
                bits = [n for byte in data for n in (byte >> 4, byte & 0x0f)]
                if any(n not in (0, 1) for n in bits[:points]) or any(bits[points:]):
                    return _response(command, wire, ERROR["bit_data"])
                bits = bits[:points]
            memory.write_bits(name, head, bits)
            payload = b""
        else:  # command 03: 16-bit words (or aligned groups of 16 bits)
            if wire == "ascii":
                if len(data) != points * 4:
                    return _response(command, wire, ERROR["request"])
                words = [_hex_number(data[i:i + 4]) for i in range(0, len(data), 4)]
            else:
                if len(data) != points * 2:
                    return _response(command, wire, ERROR["request"])
                words = [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]
            if kind == "word":
                memory.write_words(name, head, words)
            else:
                bits = [bit for word in words for bit in _word_to_bits(word)]
                memory.write_bits(name, head, bits)
            payload = b""
    except (OutOfRange, ValueError):
        return _response(command, wire, ERROR["request"])
    return _response(command, wire, payload=payload)
