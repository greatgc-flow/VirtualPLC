"""Check the client-compat oracle; missing installations must fail."""

import hashlib
from importlib.metadata import distribution
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


def test_oracle_pin():
    installed = distribution("pymcprotocol")
    assert installed.version == "0.3.0"
    pin = (ROOT / "tests/oracle_pin.txt").read_text(encoding="utf-8")
    requirement = next(line for line in pin.splitlines() if line.startswith("pymcprotocol=="))
    package, digest = requirement.split(" --hash=sha256:")
    assert package == "pymcprotocol==0.3.0"
    assert len(digest) == 64
    # A wheel hash cannot be reconstructed from unpacked installed files.
    # When retained by the documented setup, check both artifact and source.
    wheel = ROOT / ".venv/oracle/pymcprotocol-0.3.0-py3-none-any.whl"
    if wheel.exists():
        assert hashlib.sha256(wheel.read_bytes()).hexdigest() == digest
        with ZipFile(wheel) as archive:
            for name in archive.namelist():
                if name.startswith("pymcprotocol/") and name.endswith(".py"):
                    assert Path(installed.locate_file(name)).read_bytes() == archive.read(name)
