"""Per-profile device capabilities, ranges, and CPU identity (M1: Q only)."""

from dataclasses import dataclass

# Synthetic ceiling (3-byte head address); authoritative per-series ranges are open (DESIGN §8).
MAX_POINT = 0xFFFFFF


@dataclass(frozen=True)
class Device:
    name: str
    code: int
    kind: str


@dataclass(frozen=True)
class Profile:
    name: str
    cpu_name: str
    cpu_code: int
    devices: dict

    def device_by_code(self, code):
        return next((device for device in self.devices.values() if device.code == code), None)


# Codes match pymcprotocol mcprotocolconst.DeviceConstants.
Q_DEVICES = (
    ("SM", 0x91, "bit"), ("SD", 0xA9, "word"), ("X", 0x9C, "bit"), ("Y", 0x9D, "bit"),
    ("M", 0x90, "bit"), ("B", 0xA0, "bit"), ("D", 0xA8, "word"), ("W", 0xB4, "word"),
    ("SB", 0xA1, "bit"), ("SW", 0xB5, "word"), ("DX", 0xA2, "bit"), ("DY", 0xA3, "bit"),
    ("R", 0xAF, "word"), ("ZR", 0xB0, "word"),
)

PROFILES = {
    "Q": Profile("Q", "VirtualPLC-Q", 0xFFFF, {name: Device(name, code, kind) for name, code, kind in Q_DEVICES}),
}
