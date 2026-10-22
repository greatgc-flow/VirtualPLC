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
        if unit == "bit" and spec.kind == "word":
            raise ValueError(f"bit access to word device {device}")
        if unit == "word" and spec.kind == "bit":
            if head % 16:
                raise ValueError("word view of a bit device needs a head that is a multiple of 16")
            points = count * 16
        minimum, maximum = self._limits[device]
        if head < minimum or head + points - 1 > maximum:
            raise OutOfRange(f"{device}{head} x{points} outside {minimum}..{maximum}")
        return spec

    def _load(self, device, head, count):
        cells = self._cells[device]
        return [cells.get(head + i, 0) for i in range(count)]

    def _store(self, device, head, values):
        self._cells[device].update(enumerate(values, head))
