"""Shared MC command handlers, parameterized by profile wire class."""

from enum import IntEnum
import struct

from .codec import LengthError, Reader, normalize_request, pack_bits, pack_words, read_device, unpack_bits, unpack_words
from .memory import OutOfRange
from .profiles import WIRE_CLASSES

ECHO_MAX = 960
LOCK_GATED = {0x1001, 0x1002, 0x1003, 0x1005, 0x1006}
CPU_STATES = {"STOP": 0, "RUN": 1, "PAUSE": 2}  # SD203 layout: design, unverified.


class EndCode(IntEnum):
    OK = 0x0000
    POINTS_OUT_OF_RANGE = 0xC051
    ADDRESS_OUT_OF_RANGE = 0xC056
    UNSUPPORTED_COMMAND = 0xC059
    REQUEST_DATA_ERROR = 0xC05C
    DATA_LENGTH_MISMATCH = 0xC061
    LOCKED = 0xC200
    WRONG_PASSWORD = 0xC201
    INVALID_STATE = 0xC202


# DESIGN §7 rows: no manual cross-check yet.
ERROR_CODES = {
    code.value: {"name": code.name, "source": "memory" if code in (EndCode.LOCKED, EndCode.WRONG_PASSWORD) else "design",
                 "status": "unverified"} for code in EndCode
}


class CommandError(Exception):
    """A request rejected with the end code in args[0]."""


def batch(request, memory, max_points, control=None):
    """Batch read (0401) or write (1401); the subcommand selects bit or word units."""
    wire = memory.profile.wire
    if len(request.data) < wire.descriptor_size + 2:
        raise CommandError(EndCode.REQUEST_DATA_ERROR)
    reader = Reader(request.data, "binary")
    device, head = read_device(reader, memory.profile)
    points = reader.number(2)
    payload = request.data[reader.offset:]
    bit, write = request.subcommand == wire.bit_subcommand, request.command == 0x1401
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


def random_access(request, memory, max_points, control=None):
    """Random word/dword read/write or bit write; validate all entries first.

    Counts are uint8, so a purported 256-entry list cannot match its payload.
    Writes contain interleaved device/value entries, words before dwords.
    The server holds its request lock through validation and application.
    """
    data = request.data
    wire = memory.profile.wire
    bit = request.subcommand == wire.bit_subcommand
    write = request.command == 0x1402
    count_size = 1 if bit else 2
    if len(data) < count_size:
        raise CommandError(EndCode.DATA_LENGTH_MISMATCH)
    groups = ((data[0], wire.bit_value_size),) if bit else ((data[0], 2), (data[1], 4))
    expected = count_size + sum(count * (wire.descriptor_size + (width if write else 0)) for count, width in groups)
    if len(data) != expected:
        raise CommandError(EndCode.DATA_LENGTH_MISMATCH)
    entries = []
    offset = count_size
    try:
        for count, width in groups:
            for _ in range(count):
                reader = Reader(data, "binary", offset)
                device, head = read_device(reader, memory.profile)
                offset = reader.offset
                memory.check(device.name, head, 1 if bit else width // 2, "bit" if bit else "word")
                values = None
                if write:
                    payload = data[offset:offset + width]
                    offset += width
                    if bit:
                        value = int.from_bytes(payload, "little")
                        if value not in (0, 1):
                            raise ValueError("bit must be 0 or 1")
                        values = [value]
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


def echo(request, memory, max_points, control=None):
    length, text = int.from_bytes(request.data[:2], "little"), request.data[2:]
    if len(request.data) < 2 or length != len(text):
        raise CommandError(EndCode.DATA_LENGTH_MISMATCH)
    if not 0 < length <= ECHO_MAX or not text.isalnum():
        raise CommandError(EndCode.REQUEST_DATA_ERROR)
    return request.data


def cputype(request, memory, max_points, control=None):
    profile = memory.profile
    return profile.cpu_name.ljust(16).encode("ascii") + struct.pack("<H", profile.cpu_code)


def control_request(request, memory, max_points, control=None):
    """Agreed M5 policies, using the same field reader for every transport."""
    command = request.command
    auth = command in (0x1630, 0x1631)
    if control is None or (auth and control.password is None):
        raise CommandError(EndCode.UNSUPPORTED_COMMAND)
    if control.locked and command in LOCK_GATED:
        raise CommandError(EndCode.LOCKED)
    reader = Reader(request.data, request.wire)
    mode = reader.number(2)  # password length for auth commands
    clear, fixed = (reader.number(1), reader.number(1)) if command == 0x1001 else (0, 0)
    password = reader.take(mode) if auth else b""
    if reader.offset != len(reader.data):
        raise LengthError("extra control data")
    if auth:
        wire = memory.profile.wire
        if not wire.password_min <= len(password) <= wire.password_max or not password.isascii():
            raise CommandError(EndCode.REQUEST_DATA_ERROR)
        if password.decode("ascii") != control.password:
            raise CommandError(EndCode.WRONG_PASSWORD)
        control.locked = command == 0x1631
        return b""
    if mode not in ((1, 3) if command in (0x1001, 0x1003) else (1,)) or clear not in (0, 1, 2) or fixed:
        raise CommandError(EndCode.REQUEST_DATA_ERROR)
    if (command == 0x1003 and control.state == "STOP") or (command in (0x1005, 0x1006) and control.state != "STOP"):
        raise CommandError(EndCode.INVALID_STATE)
    if command == 0x1001 and clear:
        memory.clear(control.latch_ranges, "non_latch" if clear == 1 else "all")
    if command == 0x1005:
        memory.clear(control.latch_ranges, "latch")
    else:
        if command == 0x1006:
            control.reset_count += 1
        control.set_state({0x1001: "RUN", 0x1003: "PAUSE"}.get(command, "STOP"))
    return b""


# Extension point: (command, subcommand) -> handler(request, memory, max_points, control).
HANDLERS = {
    (0x0619, 0): echo, (0x0101, 0): cputype,
}
# Data subcommands are selected by wire class, so mismatches cannot dispatch.
DATA_HANDLERS = {}
for wire_class, wire in WIRE_CLASSES.items():
    handlers = {}
    for command in (0x0401, 0x1401):
        handlers[command, wire.word_subcommand] = batch
        handlers[command, wire.bit_subcommand] = batch
    handlers[0x0403, wire.word_subcommand] = random_access
    handlers[0x1402, wire.word_subcommand] = random_access
    handlers[0x1402, wire.bit_subcommand] = random_access
    DATA_HANDLERS[wire_class] = handlers
HANDLERS.update({(command, 0): control_request for command in LOCK_GATED | {0x1630, 0x1631}})


def dispatch(request, memory, max_points, control=None):
    """Return (end_code, data); a rejected request leaves memory unchanged."""
    key = (request.command, request.subcommand)
    handler = HANDLERS.get(key) or DATA_HANDLERS[memory.profile.wire_class].get(key)
    try:
        if handler is None:
            raise CommandError(EndCode.UNSUPPORTED_COMMAND)
        # Control uses the shared Reader directly; data handlers consume canonical binary.
        parsed = request if handler is control_request else normalize_request(request, memory.profile)
        return EndCode.OK, handler(parsed, memory, max_points, control)
    except CommandError as error:
        return error.args[0], b""
    except LengthError:
        code = EndCode.DATA_LENGTH_MISMATCH if handler is control_request else EndCode.REQUEST_DATA_ERROR
        return code, b""
    except ValueError:
        return EndCode.REQUEST_DATA_ERROR, b""
