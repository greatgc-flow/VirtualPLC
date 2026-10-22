"""M1 generator inputs, not runtime capabilities or independent byte oracles.

Device codes/bases are copied from pymcprotocol/mcprotocolconst.py:
https://raw.githubusercontent.com/senrust/pymcprotocol/master/src/pymcprotocol/mcprotocolconst.py
The 0.3.0 wheel must still be cross-checked when installation is available.
Only M1 devices plus the remaining hex-base families are listed here.
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
)

COMMANDS = (
    Command("batch_read_word", 0x0401, "word"),
    Command("batch_read_bit", 0x0401, "bit"),
    Command("batch_write_word", 0x1401, "word"),
    Command("batch_write_bit", 0x1401, "bit"),
    Command("echo", 0x0619),
    Command("cputype", 0x0101),
)


def applicable(command: Command, profile: Profile, frame: str, wire: str) -> tuple[bool, str | None]:
    """Return M1 seed eligibility and an explicit exclusion reason.

    frame is 3E/4E; wire is binary/ascii. This selects positive M1 cells.
    Negative tests such as T8 deliberately construct excluded requests.
    Shared wire classes do not imply shared per-profile capabilities.
    """
    if command not in COMMANDS:
        return False, "Command is outside the M1 batch/echo/cputype scope"
    if profile not in PROFILES:
        return False, "Unknown profile or inconsistent wire class"
    if frame not in {"3E", "4E"}:
        return False, "Unknown frame type"
    if wire not in {"binary", "ascii"}:
        return False, "Unknown wire encoding"
    if profile.wire_class == "iQ-R":
        return False, "iQ-R addressing is deferred to M6"
    if profile.name != "Q":
        return False, "M1 targets Q; other Q-class profile capabilities remain unspecified"
    if frame == "4E":
        return False, "4E framing is deferred to M4"
    if wire == "ascii":
        return False, "ASCII encoding is deferred to M3"
    return True, None
