"""M19 Windows archive namespace collision regression; synthetic evidence only.

No actual Windows, hardware or official wheel is involved.
"""
import zipfile
import pytest
from scripts import m16_provenance_gate as gate

@pytest.mark.parametrize('name', [
    'client_run/COM¹.txt', 'client_run/COM²', 'client_run/COM³.dat',
    'client_run/LPT¹', 'client_run/LPT².txt', 'client_run/LPT³.txt',
    'client_run/e\u0301.txt',  # NFD, not NFC
    'client_run/\u202Epayload.json', # bidi override
    'client_run/\u200bsecret', # zero-width format char
    'client_run/\ud800.txt', # unpaired surrogate
    'client_run/\ue000.dat', # private-use, nonportable
])
def test_ambiguous_member_rejected(name):
    with pytest.raises(ValueError, match='unsafe path'):
        gate.portable_member_name(name)

@pytest.mark.parametrize('name', [
    'client_run/é.txt', 'client_run/TEST.json',
    'client_run/CASE-0027.json', 'client_run/notes with spaces.txt',
])
def test_unambiguous_member_accepted(name):
    assert gate.portable_member_name(name) == name


def _archive(tmp_path, names):
    path=tmp_path/'incoming.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('M14_EVIDENCE.json',b'{}')
        for item in names:
            z.writestr(item, b'x')
    return path

@pytest.mark.parametrize('names', [
    ['client_run/CON.txt', 'client_run/ok.txt'],
    ['client_run/FILE.json', 'client_run/file.json'],
    ['client_run/ABC.txt', 'CLIENT_RUN/abc.TXT'],
    ['client_run/é.txt', 'client_run/É.txt'],
    ['client_run/scratch', 'client_run/scratch/data.json'],
    ['client_run/dir', 'client_run/dir/'],
    ['client_run/RAW', 'client_run/raw/capture.json'],
])
def test_path_alias_or_collision_rejected_before_manifest_read(tmp_path, names):
    path=_archive(tmp_path,names)
    with pytest.raises(ValueError,match='unsafe path|collision'):
        gate.inspect_archive(path)


def test_normal_noncolliding_members_reach_manifest_check(tmp_path):
    path=_archive(tmp_path,['client_run/console.log','client_run/result.json'])
    with pytest.raises(ValueError,match='unsupported M14 evidence manifest'):
        gate.inspect_archive(path)
