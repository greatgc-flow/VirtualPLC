"""M9 provenance unit gates; never reinterpret an invalid historical manifest as valid."""
import hashlib
import json
import zipfile
from pathlib import Path
import pytest
from scripts.m9_audit_m8_zip import git_blob_sha, audit, PREFIX, PINNED


def test_git_blob_digest_known():
    assert git_blob_sha(b'test content\n') == 'd670460b4b4aece5915caf5c68d12f560a9fe3e4'


def test_missing_handoff_zip_fails():
    with pytest.raises(FileNotFoundError):
        audit(Path('/no/such/path/m8.zip'))


def test_pin_replacement_detected(tmp_path):
    original = json.loads(PINNED.read_text(encoding='utf-8'))
    original['paths']['README.md'] = '0' * 40
    replacement = tmp_path / 'pins.json'
    replacement.write_text(json.dumps(original))
    # A small invalid archive ensures path validation cannot be bypassed by a forged pin.
    archive_path = tmp_path / 'fake.zip'
    with zipfile.ZipFile(archive_path, 'w') as z:
        z.writestr(PREFIX+'SHA256_MANIFEST.json', json.dumps({'files': []}))
    with pytest.raises(ValueError):
        audit(archive_path, pinned_path=replacement)


def test_manifest_pin_matches_expected_head():
    data = json.loads(PINNED.read_text())
    assert data['head'] == 'ca5e08602e0b8389a65f63f5994867797850693d'
    assert len(data['paths']) == 7
    assert all(len(x) == 40 for x in data['paths'].values())
