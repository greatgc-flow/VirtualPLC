"""Sparse device storage and atomic request operations (M1)."""

from copy import deepcopy

from .profiles import PROFILES


class OutOfRange(ValueError):
    """Access outside the configured device range."""


def valid_span(device, span):
    return (
        device is not None
        and isinstance(span, (tuple, list))
        and len(span) == 2
        and all(type(value) is int for value in span)
        and device.minimum <= span[0] <= span[1] <= device.maximum
    )


class Memory:
    """Unsigned point storage per device family; bit devices hold one bit per point."""

    def __init__(self, profile="Q", limits=None):
        self.profile = PROFILES[profile]
        self._limits = {name: (spec.minimum, spec.maximum) for name, spec in self.profile.devices.items()}
        for name, span in (limits or {}).items():
            spec = self.profile.devices.get(name)
            if not valid_span(spec, span):
                raise ValueError("invalid memory limit")
            self._limits[name] = tuple(span)
        self._cells = {name: {} for name in self.profile.devices}

    def read_words(self, device, head, count):
        spec = self.check(device, head, count, "word")
        if spec.kind == "word":
            return self._load(device, head, count)
        if spec.kind == "dword":
            cells = self._cells[device]
            return [(cells.get(head + i // 2, 0) >> (16 * (i % 2))) & 0xFFFF for i in range(count)]
        bits = self._load(device, head, count * 16)
        return [sum(bit << i for i, bit in enumerate(bits[j:j + 16])) for j in range(0, len(bits), 16)]

    def read_bits(self, device, head, count):
        self.check(device, head, count, "bit")
        return self._load(device, head, count)

    def write_words(self, device, head, values):
        values = list(values)
        if not all(0 <= value <= 0xFFFF for value in values):
            raise ValueError("word out of range")
        spec = self.check(device, head, len(values), "word")
        if spec.kind == "dword":
            # Heads address native 32-bit points; word counts stream low/high halves.
            cells = self._cells[device]
            for i, value in enumerate(values):
                point, shift = head + i // 2, 16 * (i % 2)
                cells[point] = (cells.get(point, 0) & ~(0xFFFF << shift)) | (value << shift)
            return
        if spec.kind == "bit":
            values = [value >> i & 1 for value in values for i in range(16)]
        self._store(device, head, values)

    def write_bits(self, device, head, values):
        values = list(values)
        if not all(value in (0, 1) for value in values):
            raise ValueError("bit must be 0 or 1")
        self.check(device, head, len(values), "bit")
        self._store(device, head, values)

    def write_atomic(self, operations):
        """Stage and commit a group of bit/word writes as one request.

        operations: iterable of (device, head, "bit"|"word", values).
        Validate every value and range before replacing any storage. Repeated
        addresses are applied in request order (last value wins). The caller
        must hold the Server request lock during this operation.
        """
        staged = {}
        for device, head, unit, raw_values in operations:
            if unit not in ("bit", "word"):
                raise ValueError("write_atomic needs bit or word unit")
            values = list(raw_values)
            if any(type(v) is not int for v in values):
                raise ValueError("write_atomic values must be integers")
            max_value = 1 if unit == "bit" else 0xFFFF
            if any(not 0 <= v <= max_value for v in values):
                raise ValueError("write_atomic value out of range")
            spec = self.check(device, head, len(values), unit)
            if device not in staged:
                staged[device] = self._cells[device].copy()
            cells = staged[device]
            if spec.kind == "bit":
                if unit == "word":
                    values = [value >> i & 1 for value in values for i in range(16)]
                cells.update(enumerate(values, head))
            elif spec.kind == "dword":
                for i, value in enumerate(values):
                    point, shift = head + i // 2, 16 * (i % 2)
                    cells[point] = ((cells.get(point, 0) & ~(0xFFFF << shift))
                                    | (value << shift))
            else:
                cells.update(enumerate(values, head))
        # Single commit point under request lock; failures above leave state as-is.
        self._cells.update(staged)

    def check(self, device, head, count, unit):
        """Validate one access; `count` is in `unit`s. Returns the device spec."""
        spec = self.profile.devices.get(device)
        if spec is None or count <= 0:
            raise ValueError(f"invalid access to {device} x{count}")
        points = count
        if unit == "bit" and spec.kind != "bit":
            raise ValueError(f"bit access to word device {device}")
        if unit == "word" and spec.kind == "bit":
            if head % 16:
                raise ValueError("word view of a bit device needs a head that is a multiple of 16")
            points = count * 16
        if unit == "word" and spec.kind == "dword":
            points = (count + 1) // 2
        minimum, maximum = self._limits[device]
        if head < minimum or head + points - 1 > maximum:
            raise OutOfRange(f"{device}{head} x{points} outside {minimum}..{maximum}")
        return spec

    def _load(self, device, head, count):
        cells = self._cells[device]
        return [cells.get(head + i, 0) for i in range(count)]

    def _store(self, device, head, values):
        self._cells[device].update(enumerate(values, head))

    def clear(self, latch_ranges, mode):
        """Clear stored points only; the server holds its request lock.

        mode is latch, non_latch, or all. Special devices are always preserved.
        """
        for device, cells in self._cells.items():
            if device in {"SM", "SD"}:
                continue
            for head in list(cells):
                latched = any(low <= head <= high for low, high in latch_ranges.get(device, ()))
                if mode == "all" or (mode == "latch" and latched) or (mode == "non_latch" and not latched):
                    del cells[head]


    def dump(self):
        """Return stored points as JSON-compatible contiguous runs (native units).

        Call before start or after stop; direct Memory access is not synchronized.
        """
        result = {}
        for name, cells in self._cells.items():
            runs = {}
            previous = None
            for head, value in sorted(cells.items()):
                if previous is None or head != previous + 1:
                    values = []
                    runs[str(head)] = values
                values.append(value)
                previous = head
            if runs:
                result[name] = runs
        return result

    def load(self, data):
        """Validate a complete snapshot before overlaying it; use before start.

        Values are unsigned bits/words/native dwords, not client signed values.
        """
        if not isinstance(data, dict):
            raise ValueError("memory snapshot must be an object")
        staged = Memory(self.profile.name, self._limits)
        staged._cells = deepcopy(self._cells)
        for name, runs in data.items():
            spec = self.profile.devices.get(name)
            if spec is None or not isinstance(runs, dict):
                raise ValueError("invalid snapshot device or runs")
            for address, values in runs.items():
                if not isinstance(address, str) or not isinstance(values, list) or not values:
                    raise ValueError("snapshot runs need decimal address keys and nonempty lists")
                head = int(address, 10)
                maximum = {"bit": 1, "word": 65535, "dword": 0xFFFFFFFF}[spec.kind]
                if any(type(value) is not int or not 0 <= value <= maximum for value in values):
                    raise ValueError("snapshot value out of range")
                if spec.kind == "dword":
                    values = [half for value in values for half in (value & 0xFFFF, value >> 16)]
                (staged.write_bits if spec.kind == "bit" else staged.write_words)(name, head, values)
        self._cells = staged._cells
