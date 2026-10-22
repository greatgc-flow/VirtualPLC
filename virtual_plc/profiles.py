"""Per-profile device capabilities, ranges, and CPU identity (Q binary)."""

from dataclasses import dataclass

# Synthetic ceiling (3-byte head address); authoritative per-series ranges are open (DESIGN §8).
MAX_POINT = 0xFFFFFF
LATCH = {"L": ((0, MAX_POINT),)}  # Synthetic default retention ranges, inclusive.


@dataclass(frozen=True)
class Device:
    name: str
    code: int
    kind: str
    base: int = 10
    minimum: int = 0
    maximum: int = MAX_POINT


@dataclass(frozen=True)
class Profile:
    name: str
    cpu_name: str
    cpu_code: int
    devices: dict
    latch_ranges: dict

    def device_by_code(self, code):
        return next((device for device in self.devices.values() if device.code == code), None)


# Codes match pymcprotocol mcprotocolconst.DeviceConstants.
Q_DEVICES = (
    ("SM", 0x91, "bit"), ("SD", 0xA9, "word"), ("X", 0x9C, "bit", 16), ("Y", 0x9D, "bit", 16),
    ("M", 0x90, "bit"), ("B", 0xA0, "bit", 16), ("D", 0xA8, "word"), ("W", 0xB4, "word", 16),
    ("SB", 0xA1, "bit", 16), ("SW", 0xB5, "word", 16), ("DX", 0xA2, "bit", 16), ("DY", 0xA3, "bit", 16),
    ("R", 0xAF, "word"), ("ZR", 0xB0, "word", 16),
    ("L", 0x92, "bit"), ("F", 0x93, "bit"), ("V", 0x94, "bit"),
    ("TS", 0xC1, "bit"), ("TC", 0xC0, "bit"), ("TN", 0xC2, "word"),
    ("SS", 0xC7, "bit"), ("SC", 0xC6, "bit"), ("SN", 0xC8, "word"),
    ("CS", 0xC4, "bit"), ("CC", 0xC3, "bit"), ("CN", 0xC5, "word"),
)

PROFILES = {
    "Q": Profile("Q", "VirtualPLC-Q", 0xFFFF, {row[0]: Device(*row) for row in Q_DEVICES}, LATCH),
}
