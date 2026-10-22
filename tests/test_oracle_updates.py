"""A dependency bump must exercise compatibility without using a stale wheel hash."""

from types import SimpleNamespace

import pytest
import test_oracle_pin as oracle


def test_bumped_requirement_checks_version_and_skips_old_hash(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "requirements-dev.txt").write_text("pytest\npymcprotocol==9.9.9\n")
    (tmp_path / "tests/oracle_pin.txt").write_text("pymcprotocol==0.3.0 --hash=sha256:" + "0" * 64)
    monkeypatch.setattr(oracle, "ROOT", tmp_path)
    monkeypatch.setattr(oracle, "distribution", lambda name: SimpleNamespace(version="9.9.9"))
    oracle.test_oracle_pin()
    with pytest.raises(pytest.skip.Exception, match="Wheel hash records"):
        oracle.test_oracle_wheel_hash()
    monkeypatch.setattr(oracle, "distribution", lambda name: SimpleNamespace(version="9.9.8"))
    with pytest.raises(AssertionError, match="Install the oracle"):
        oracle.test_oracle_pin()
