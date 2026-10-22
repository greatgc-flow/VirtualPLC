"""Sparse device storage and atomic request operations (M1)."""

from .profiles import PROFILES


class OutOfRange(ValueError):
    """Access outside the configured device range."""


class Memory:
    """Unsigned point storage per device family; bit devices hold one bit per point."""

    def __init__(self, profile="Q", limits=None):
        self.profile = PROFILES[profile]
        self._limits = {name: (spec.minimum, spec.maximum) for name, spec in self.profile.devices.items()}
        self._limits.update(limits or {})
        self._cells = {name: {} for name in self.profile.devices}

    def read_words(self, device, head, count):
        spec = self._check(device, head, count, "word")
        if spec.kind == "word":
            return self._load(device, head, count)
        if spec.kind == "dword":
            cells = self._cells[device]
            return [(cells.get(head + i // 2, 0) >> (16 * (i % 2))) & 0xFFFF for i in range(count)]
        bits = self._load(device, head, count * 16)
        return [sum(bit << i for i, bit in enumerate(bits[j:j + 16])) for j in range(0, len(bits), 16)]

    def read_bits(self, device, head, count):
        self._check(device, head, count, "bit")
        return self._load(device, head, count)

    def write_words(self, device, head, values):
        values = list(values)
        if not all(0 <= value <= 0xFFFF for value in values):
            raise ValueError("word out of range")
        spec = self._check(device, head, len(values), "word")
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
        self._check(device, head, len(values), "bit")
        self._store(device, head, values)

    def _check(self, device, head, count, unit):
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

    def _clear(self, latch_ranges, mode):
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
