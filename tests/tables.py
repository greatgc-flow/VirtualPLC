"""Q generator inputs, not runtime capabilities or independent byte oracles.

Device codes/bases are copied from pymcprotocol/mcprotocolconst.py:
https://raw.githubusercontent.com/senrust/pymcprotocol/master/src/pymcprotocol/mcprotocolconst.py
Codes and parser spellings are checked against the installed pinned client.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    wire_class: str


@dataclass(frozen=True)
class Device:
    name: str
    code: int
    base: int
    kind: str


@dataclass(frozen=True)
class Command:
    name: str
    code: int
    unit: str | None = None

    def subcommand(self, profile: Profile) -> int:
        """Addressed word/bit commands use 0/1 on Q-class, 2/3 on iQ-R."""
        if profile.wire_class not in {"Q-class", "iQ-R"}:
            raise ValueError("Unknown wire class")
        if self.unit is None:
            return 0
        if self.unit not in {"word", "bit"}:
            raise ValueError("Unknown command unit")
        return (2 if profile.wire_class == "iQ-R" else 0) + (self.unit == "bit")


PROFILES = (
    Profile("Q", "Q-class"),
    Profile("L", "Q-class"),
    Profile("QnA", "Q-class"),
    Profile("iQ-L", "Q-class"),
    Profile("iQ-R", "iQ-R"),
)

DEVICES = (
    Device("SM", 0x91, 10, "bit"),
    Device("SD", 0xA9, 10, "word"),
    Device("X", 0x9C, 16, "bit"),
    Device("Y", 0x9D, 16, "bit"),
    Device("M", 0x90, 10, "bit"),
    Device("B", 0xA0, 16, "bit"),
    Device("D", 0xA8, 10, "word"),
    Device("W", 0xB4, 16, "word"),
    Device("SB", 0xA1, 16, "bit"),
    Device("SW", 0xB5, 16, "word"),
    Device("DX", 0xA2, 16, "bit"),
    Device("DY", 0xA3, 16, "bit"),
    Device("R", 0xAF, 10, "word"),
    Device("ZR", 0xB0, 16, "word"),
    Device("L", 0x92, 10, "bit"),
    Device("F", 0x93, 10, "bit"),
    Device("V", 0x94, 10, "bit"),
    Device("TS", 0xC1, 10, "bit"),
    Device("TC", 0xC0, 10, "bit"),
    Device("TN", 0xC2, 10, "word"),
    Device("SS", 0xC7, 10, "bit"),
    Device("SC", 0xC6, 10, "bit"),
    Device("SN", 0xC8, 10, "word"),
    Device("CS", 0xC4, 10, "bit"),
    Device("CC", 0xC3, 10, "bit"),
    Device("CN", 0xC5, 10, "word"),
)

IQR_EXTRA_DEVICES = (
    Device("LTS", 0x51, 10, "bit"), Device("LTC", 0x50, 10, "bit"),
    Device("LTN", 0x52, 10, "dword"),
    Device("LSTS", 0x59, 10, "bit"), Device("LSTC", 0x58, 10, "bit"),
    Device("LSTN", 0x5A, 10, "dword"),
    Device("LCS", 0x55, 10, "bit"), Device("LCC", 0x54, 10, "bit"),
    Device("LCN", 0x56, 10, "dword"), Device("LZ", 0x62, 10, "dword"),
    Device("RD", 0x2C, 10, "word"),
)


def devices_for(profile):
    return DEVICES + (IQR_EXTRA_DEVICES if profile.wire_class == "iQ-R" else ())

# The 0.3.0 parser uses ST* while its constants (and Q storage) use S*.
CLIENT_NAMES = {"SS": "STS", "SC": "STC", "SN": "STN"}

COMMANDS = (
    Command("batch_read_word", 0x0401, "word"),
    Command("batch_read_bit", 0x0401, "bit"),
    Command("batch_write_word", 0x1401, "word"),
    Command("batch_write_bit", 0x1401, "bit"),
    Command("echo", 0x0619),
    Command("cputype", 0x0101),
    Command("random_read", 0x0403, "word"),
    Command("random_write", 0x1402, "word"),
    Command("random_write_bit", 0x1402, "bit"),
)

CONTROL_COMMANDS = (
    Command("run", 0x1001), Command("stop", 0x1002), Command("pause", 0x1003),
    Command("latchclear", 0x1005), Command("reset", 0x1006),
    Command("unlock", 0x1630), Command("lock", 0x1631),
)


def applicable(command: Command, profile: Profile, frame: str, wire: str, *, milestone=2, device=None) -> tuple[bool, str | None]:
    """Return seed eligibility and an explicit exclusion reason.

    frame is 3E/4E; wire is binary/ascii. milestone preserves earlier seed scopes.
    Negative tests such as T8 deliberately construct excluded requests.
    Shared wire classes do not imply shared per-profile capabilities.
    """
    if command not in COMMANDS + CONTROL_COMMANDS:
        return False, "Command is outside the batch/random/echo/cputype scope"
    if command in CONTROL_COMMANDS and milestone < 5:
        return False, "CPU control and authentication are deferred to M5"
    if profile not in PROFILES:
        return False, "Unknown profile or inconsistent wire class"
    if frame not in {"3E", "4E"}:
        return False, "Unknown frame type"
    if wire not in {"binary", "ascii"}:
        return False, "Unknown wire encoding"
    if profile.wire_class == "iQ-R" and milestone < 6:
        return False, "iQ-R addressing is deferred to M6"
    if profile.name != "Q" and milestone < 6:
        return False, "M1 targets Q; other Q-class profile capabilities remain unspecified"
    if device is not None and device not in devices_for(profile):
        return False, "Device is unavailable on this profile"
    if device is not None and device.name == "LSTC":
        return False, "LSTC has a constant but no pinned client lookup; raw-socket tests only"
    if device is not None and command.unit == "bit" and device.kind != "bit":
        return False, "Bit access to word devices is invalid"
    if frame == "4E" and milestone < 4:
        return False, "4E framing is deferred to M4"
    if wire == "ascii" and milestone < 3:
        return False, "ASCII encoding is deferred to M3"
    return True, None
