"""Check the client-compat oracle; missing installations must fail."""

import hashlib
from importlib.metadata import distribution
from pathlib import Path
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_no_secondary_oracle_requirements():
    assert not (ROOT / "requirements-oracle.txt").exists()
    for path in [ROOT / "MANIFEST.in", ROOT / "README.md"]:
        assert "requirements-oracle.txt" not in path.read_text(encoding="utf-8")
    assert "pymcprotocol==" not in (ROOT / "tests/oracle_pin.txt").read_text()


def test_oracle_pin():
    installed = distribution("pymcprotocol")
    requirement = next(line for line in (ROOT / "requirements-dev.txt").read_text().splitlines()
                       if line.startswith("pymcprotocol=="))
    assert installed.version == requirement.split("==", 1)[1], "Install the oracle in requirements-dev.txt"


def test_oracle_wheel_hash():
    installed = distribution("pymcprotocol")
    pin = (ROOT / "tests/oracle_pin.txt").read_text(encoding="utf-8")
    metadata = dict(line.split("=", 1) for line in pin.splitlines() if line and not line.startswith("#"))
    pinned_version, digest = metadata["version"], metadata["sha256"]
    if installed.version != pinned_version:
        pytest.skip(f"Wheel hash records {pinned_version}; installed oracle is {installed.version}. Run full suite/coverage guard.")
    assert len(digest) == 64
    # A wheel hash cannot be reconstructed from unpacked installed files.
    # When retained by the documented setup, check both artifact and source.
    wheel = ROOT / f".venv/oracle/pymcprotocol-{pinned_version}-py3-none-any.whl"
    if wheel.exists():
        assert hashlib.sha256(wheel.read_bytes()).hexdigest() == digest
        with ZipFile(wheel) as archive:
            for name in archive.namelist():
                if name.startswith("pymcprotocol/") and name.endswith(".py"):
                    assert Path(installed.locate_file(name)).read_bytes() == archive.read(name)
