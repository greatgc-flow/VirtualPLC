"""M18 cross-platform evidence ZIP hardening (synthetic, not Windows attestation).

Tests are deterministic and require neither external data nor a running PLC.
Paths with Windows drive syntax, ADS or Win32 device names must be blocked even
on Linux, before extraction, to keep portable evidence ingestion fail-closed.
"""
from pathlib import Path
import zipfile
import pytest
from scripts import m16_provenance_gate as gate

@pytest.mark.parametrize('member',[ 
    'C:escape.txt', 'C:/root/escape.txt', 'client_run/file:stream',
    'NUL', 'client_run/NUL.txt', 'client_run/CON', 'client_run/AUX.json',
    'client_run/COM1.log', 'client_run/LPT9', 'client_run/CONIN$.dat',
    'client_run/trailing.', 'client_run/trailing ', 'client_run//repeat',
    'client_run/./segment', 'client_run/../traversal',
    'client_run/hidden\tcontrol',
])
def test_portable_archive_path_is_rejected(member):
    with pytest.raises(ValueError, match='unsafe path'):
        gate.portable_member_name(member)

@pytest.mark.parametrize('member',[
    'M14_EVIDENCE.json','client_run/console.log',
    'client_run/raw_capture/CASE-0027.json','runner_stdout.bin',
])
def test_normal_evidence_member_accepted(member):
    assert gate.portable_member_name(member)==member


def test_windows_unsafe_extra_zip_entry_is_rejected_before_extraction(tmp_path):
    source=tmp_path/'bad.zip'
    with zipfile.ZipFile(source,'w') as z:
        z.writestr('M14_EVIDENCE.json',b'{}')
        z.writestr('client_run/NUL.txt',b'evil')
    with pytest.raises(ValueError, match='unsafe path'):
        gate.inspect_archive(source)


def test_private_result_inside_public_checkout_rejected(tmp_path):
    source_root=tmp_path/'checkout';source_root.mkdir()
    zip_file=tmp_path/'incoming.zip'
    result=source_root/'result.json'
    with pytest.raises(ValueError,match='public repository'):
        gate.protected_intake_result(zip_file,result,source_root=source_root)
    assert not result.exists()


def test_private_result_symlinked_to_public_checkout_rejected(tmp_path):
    source_root=tmp_path/'checkout';source_root.mkdir()
    link=tmp_path/'symlink'
    try:
        link.symlink_to(source_root,target_is_directory=True)
    except (OSError,NotImplementedError):
        pytest.skip('symlinks not supported on test runner')
    with pytest.raises(ValueError,match='public repository'):
        gate.protected_intake_result(tmp_path/'incoming.zip',link/'result.json',source_root=source_root)


def test_never_overwrite_input_archive_with_result(tmp_path):
    source_root=tmp_path/'checkout';source_root.mkdir()
    archive=tmp_path/'input.zip'
    with pytest.raises(ValueError,match='unsafe'):
        gate.protected_intake_result(archive,archive,source_root=source_root)


def test_result_outside_checkout_accepted(tmp_path):
    source_root=tmp_path/'checkout';source_root.mkdir()
    source=tmp_path/'incoming.zip'
    target=tmp_path/'review'/'audit.json'
    assert gate.protected_intake_result(source,target,source_root=source_root)==target.resolve()


def test_main_does_not_create_private_result_within_repo(tmp_path,capsys):
    from scripts.m14_windows_evidence import ROOT
    dest=ROOT/'M18_DO_NOT_CREATE_PRIVATE_AUDIT.json'
    assert not dest.exists()
    rc=gate.main(['--zip',str(tmp_path/'missing.zip'),'--result',str(dest)])
    assert rc==2 and not dest.exists()
    assert 'HOLD' in capsys.readouterr().out
