"""Test the real-client gate itself without claiming to run the real client."""
from pathlib import Path
import hashlib
import pytest
from scripts.m10_wheel_gate import verify_wheel, run, EXPECTED, WHEEL


def test_no_wheel_fails_closed(tmp_path):
    with pytest.raises(ValueError, match='missing expected'):
        verify_wheel(tmp_path / WHEEL)


def test_wrong_bytes_fail_closed(tmp_path):
    path = tmp_path / WHEEL
    path.write_bytes(b'not the real wheel')
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        verify_wheel(path)


def test_no_output_on_untrusted_wheel(tmp_path):
    path = tmp_path / WHEEL
    path.write_bytes(b'bad')
    output = tmp_path / 'output'
    with pytest.raises(ValueError):
        run(path, output)
    assert not output.exists()


def test_existing_destination_never_overwritten(tmp_path):
    output = tmp_path / 'output'
    output.mkdir()
    original = output / 'keep'
    original.write_text('preserve')
    with pytest.raises(FileExistsError):
        run(tmp_path / WHEEL, output)
    assert original.read_text() == 'preserve'


def test_known_wheel_hash_format():
    assert len(EXPECTED) == 64 and all(x in '0123456789abcdef' for x in EXPECTED)
