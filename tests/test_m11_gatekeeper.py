"""M11 audit defenses. Not vendor/client attestations and not P0 CASE-ID evidence."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

from scripts.m11_gatekeeper import get_readiness, M10_REMAINING


def test_remaining_exact_16_not_promoted():
    outcome = get_readiness()
    assert outcome['release'] == 'HOLD'
    assert outcome['p0_attested'] == 0
    assert outcome['new_p0_verified'] == 0
    assert outcome['p0_not_run_or_unattested'] == 16
    assert set(outcome['m10_remaining_case_ids']) == M10_REMAINING


def test_wheel_incorrect_hash_fails(tmp_path):
    wheel = tmp_path / 'pymcprotocol-0.3.0-py3-none-any.whl'
    wheel.write_bytes(b'fabricated client data')
    with pytest.raises(ValueError, match='hash mismatch'):
        get_readiness(wheel=wheel)


def test_wrong_wheel_name_fails(tmp_path):
    wheel = tmp_path / 'pymcprotocol-0.3.0.tar.gz'
    wheel.write_bytes(b'no')
    with pytest.raises(ValueError, match='wheel name'):
        get_readiness(wheel=wheel)


def test_unattested_windows_junit_remains_hold(tmp_path):
    report = tmp_path / 'junit.xml'
    report.write_bytes(b'<testsuite tests="1"><testcase name="dummy"/></testsuite>')
    outcome = get_readiness(windows_junit=report)
    assert outcome['external_gate_status']['windows'].startswith('UNATTESTED')
    assert outcome['p0_attested'] == 0


def test_model_declaration_not_vendor_proof(tmp_path):
    profile = tmp_path / 'profile.json'
    profile.write_text(json.dumps({'model': 'TEST_PROFILE', 'firmware': 'unknown',
                                  'source_url': 'https://example.org/manual'}))
    outcome = get_readiness(model_profile=profile)
    assert outcome['external_gate_status']['manufacturer'].endswith('UNATTESTED')
    assert outcome['p0_attested'] == 0


def test_invalid_model_schema_rejected(tmp_path):
    profile = tmp_path / 'profile.json'
    profile.write_text('{}')
    with pytest.raises(ValueError, match='profile missing'):
        get_readiness(model_profile=profile)


@pytest.mark.parametrize('sha', ['xyz', 'G'*40, '0'*39])
def test_malformed_commit_rejected(sha):
    with pytest.raises(ValueError, match='commit SHA'):
        get_readiness(source_head=sha)


def test_cli_refuses_evidence_overwrite(tmp_path):
    dest = tmp_path / 'run'
    dest.mkdir()
    cmd = [sys.executable, '-m', 'scripts.m11_gatekeeper', '--out', str(dest)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    assert result.returncode == 1
    assert 'refusing overwrite' in result.stderr


def test_cli_writes_identical_console_file_and_no_attestation(tmp_path):
    dest = tmp_path / 'run'
    cmd = [sys.executable, '-m', 'scripts.m11_gatekeeper', '--out', str(dest)]
    result = subprocess.run(cmd, capture_output=True, timeout=5)
    assert result.returncode == 2  # blocked is not success
    assert result.stdout == (dest/'console.txt').read_bytes()
    assert result.stdout == (dest/'result.json').read_bytes()
    output = json.loads(result.stdout)
    assert output['p0_attested'] == 0


def test_forged_wheel_does_not_create_evidence(tmp_path):
    file = tmp_path / 'pymcprotocol-0.3.0-py3-none-any.whl'
    file.write_bytes(b'no')
    dest = tmp_path / 'out'
    result = subprocess.run([sys.executable, '-m', 'scripts.m11_gatekeeper',
        '--wheel', str(file), '--out', str(dest)], capture_output=True, timeout=5)
    assert result.returncode == 2
    assert not dest.exists()
