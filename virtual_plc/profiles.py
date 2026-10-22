"""Named profiles and the two client wire classes; ranges/identities are synthetic."""

from dataclasses import dataclass, replace

# Synthetic ceiling (3-byte head address); authoritative per-series ranges are open (DESIGN §8).
MAX_POINT = 0xFFFFFF
LATCH = {"L": ((0, MAX_POINT),)}  # Synthetic default retention ranges, inclusive.


@dataclass(frozen=True)
class Wire:
    address_size: int
    code_size: int
    ascii_code_size: int
    ascii_address_size: int
    bit_value_size: int
    word_subcommand: int
    bit_subcommand: int
    password_min: int
    password_max: int

    @property
    def descriptor_size(self):
        return self.address_size + self.code_size


WIRE_CLASSES = {
    "Q-class": Wire(3, 1, 2, 6, 1, 0, 1, 4, 4),
    "iQ-R": Wire(4, 2, 4, 8, 2, 2, 3, 6, 32),
}


@dataclass(frozen=True)
class Device:
    name: str
    code: int
    kind: str
    base: int = 10
    minimum: int = 0
    maximum: int = MAX_POINT
    ascii_name: str | None = None


@dataclass(frozen=True)
class Profile:
    name: str
    cpu_name: str
    cpu_code: int
    devices: dict
    latch_ranges: dict
    wire_class: str = "Q-class"

    @property
    def wire(self):
        return WIRE_CLASSES[self.wire_class]

    def device_by_code(self, code):
        return next((device for device in self.devices.values() if device.code == code), None)

    def device_by_ascii(self, code):
        return next((device for device in self.devices.values()
                     if (device.ascii_name or device.name).ljust(self.wire.ascii_code_size, "*") == code.upper()), None)


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

IQR_DEVICES = (
    ("LTS", 0x51, "bit"), ("LTC", 0x50, "bit"), ("LTN", 0x52, "dword"),
    ("LSTS", 0x59, "bit"), ("LSTC", 0x58, "bit"), ("LSTN", 0x5A, "dword"),
    ("LCS", 0x55, "bit"), ("LCC", 0x54, "bit"), ("LCN", 0x56, "dword"),
    ("LZ", 0x62, "dword"), ("RD", 0x2C, "word"),
)


def _profile(name, code, wire_class):
    iqr = wire_class == "iQ-R"
    maximum = (1 << (8 * WIRE_CLASSES[wire_class].address_size)) - 1
    aliases = {"SS": "STS", "SC": "STC", "SN": "STN"} if iqr else {}
    devices = {row[0]: replace(Device(*row), maximum=maximum, ascii_name=aliases.get(row[0]))
               for row in Q_DEVICES + (IQR_DEVICES if iqr else ())}
    return Profile(name, "VirtualPLC-" + name, code, devices, {"L": ((0, maximum),)}, wire_class)


PROFILES = {name: _profile(name, code, wire_class) for name, code, wire_class in (
    ("Q", 0xFFFF, "Q-class"), ("L", 0xFFFE, "Q-class"), ("QnA", 0xFFFD, "Q-class"),
    ("iQ-L", 0xFFFC, "Q-class"), ("iQ-R", 0xFFFB, "iQ-R"),
)}
