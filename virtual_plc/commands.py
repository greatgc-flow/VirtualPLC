"""Q binary MC command dispatch and validation."""

from enum import IntEnum
import struct

from .codec import pack_bits, pack_words, unpack_bits, unpack_words
from .memory import OutOfRange

ECHO_MAX = 960


class EndCode(IntEnum):
    OK = 0x0000
    POINTS_OUT_OF_RANGE = 0xC051
    ADDRESS_OUT_OF_RANGE = 0xC056
    UNSUPPORTED_COMMAND = 0xC059
    REQUEST_DATA_ERROR = 0xC05C
    DATA_LENGTH_MISMATCH = 0xC061


# DESIGN §7 rows: no manual cross-check yet.
ERROR_CODES = {
    code.value: {"name": code.name, "source": "design", "status": "unverified"} for code in EndCode
}


class CommandError(Exception):
    """A request rejected with the end code in args[0]."""


def batch(request, memory, max_points):
    """Batch read (0401) or write (1401); the subcommand selects bit or word units."""
    if len(request.data) < 6:
        raise CommandError(EndCode.REQUEST_DATA_ERROR)
    head = int.from_bytes(request.data[:3], "little")
    device = memory.profile.device_by_code(request.data[3])
    points = int.from_bytes(request.data[4:6], "little")
    payload = request.data[6:]
    bit, write = request.subcommand == 1, request.command == 0x1401
    if device is None:
        raise CommandError(EndCode.REQUEST_DATA_ERROR)
    if not 0 < points <= max_points:
        raise CommandError(EndCode.POINTS_OUT_OF_RANGE)
    expected = ((points + 1) // 2 if bit else 2 * points) if write else 0
    if len(payload) != expected:
        raise CommandError(EndCode.DATA_LENGTH_MISMATCH)
    try:
        if write:
            values = unpack_bits(payload, points) if bit else unpack_words(payload)
            (memory.write_bits if bit else memory.write_words)(device.name, head, values)
            return b""
        if bit:
            return pack_bits(memory.read_bits(device.name, head, points))
        return pack_words(memory.read_words(device.name, head, points))
    except OutOfRange:
        raise CommandError(EndCode.ADDRESS_OUT_OF_RANGE)
    except ValueError:
        raise CommandError(EndCode.REQUEST_DATA_ERROR)


def random_access(request, memory, max_points):
    """Random word/dword read/write or bit write; validate all entries first.

    Counts are uint8, so a purported 256-entry list cannot match its payload.
    Writes contain interleaved device/value entries, words before dwords.
    The server holds its request lock through validation and application.
    """
    data = request.data
    bit = request.subcommand == 1
    write = request.command == 0x1402
    count_size = 1 if bit else 2
    if len(data) < count_size:
        raise CommandError(EndCode.DATA_LENGTH_MISMATCH)
    groups = ((data[0], 1),) if bit else ((data[0], 2), (data[1], 4))
    expected = count_size + sum(count * (4 + (width if write else 0)) for count, width in groups)
    if len(data) != expected:
        raise CommandError(EndCode.DATA_LENGTH_MISMATCH)
    entries = []
    offset = count_size
    try:
        for count, width in groups:
            for _ in range(count):
                head = int.from_bytes(data[offset:offset + 3], "little")
                device = memory.profile.device_by_code(data[offset + 3])
                offset += 4
                if device is None:
                    raise ValueError("unknown device code")
                memory._check(device.name, head, 1 if bit else width // 2, "bit" if bit else "word")
                values = None
                if write:
                    payload = data[offset:offset + width]
                    offset += width
                    if bit:
                        if payload[0] not in (0, 1):
                            raise ValueError("bit must be 0 or 1")
                        values = [payload[0]]
                    else:
                        values = unpack_words(payload)
                entries.append((device.name, head, width, values))
        # Nothing above mutates storage. Overlaps are applied in wire order.
        result = bytearray()
        for device, head, width, values in entries:
            if write:
                (memory.write_bits if bit else memory.write_words)(device, head, values)
            else:
                result += pack_words(memory.read_words(device, head, width // 2))
        return bytes(result)
    except OutOfRange:
        raise CommandError(EndCode.ADDRESS_OUT_OF_RANGE)
    except ValueError:
        raise CommandError(EndCode.REQUEST_DATA_ERROR)


def echo(request, memory, max_points):
    length, text = int.from_bytes(request.data[:2], "little"), request.data[2:]
    if len(request.data) < 2 or length != len(text):
        raise CommandError(EndCode.DATA_LENGTH_MISMATCH)
    if not 0 < length <= ECHO_MAX or not text.isalnum():
        raise CommandError(EndCode.REQUEST_DATA_ERROR)
    return request.data


def cputype(request, memory, max_points):
    profile = memory.profile
    return profile.cpu_name.ljust(16).encode("ascii") + struct.pack("<H", profile.cpu_code)


# Extension point: (command, subcommand) -> handler(request, memory, max_points) -> response data.
HANDLERS = {
    (0x0401, 0): batch, (0x0401, 1): batch, (0x1401, 0): batch, (0x1401, 1): batch,
    (0x0619, 0): echo, (0x0101, 0): cputype,
    (0x0403, 0): random_access, (0x1402, 0): random_access, (0x1402, 1): random_access,
}


def dispatch(request, memory, max_points):
    """Return (end_code, data); a rejected request leaves memory unchanged."""
    handler = HANDLERS.get((request.command, request.subcommand))
    try:
        if handler is None:
            raise CommandError(EndCode.UNSUPPORTED_COMMAND)
        return EndCode.OK, handler(request, memory, max_points)
    except CommandError as error:
        return error.args[0], b""
