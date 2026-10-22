"""Profile tables and explicitly unverified native-dword storage policy."""

import pymcprotocol
from pymcprotocol.mcprotocolconst import DeviceConstants, DeviceCodeError
import pytest

from tables import CLIENT_NAMES, COMMANDS, CONTROL_COMMANDS, IQR_EXTRA_DEVICES, PROFILES, applicable, devices_for


pytestmark = pytest.mark.unverified
IDENTITIES = {"Q": ("VirtualPLC-Q", 0xFFFF), "L": ("VirtualPLC-L", 0xFFFE),
              "QnA": ("VirtualPLC-QnA", 0xFFFD), "iQ-L": ("VirtualPLC-iQ-L", 0xFFFC),
              "iQ-R": ("VirtualPLC-iQ-R", 0xFFFB)}
NATIVE = ["LTN", "LSTN", "LCN", "LZ"]


@pytest.mark.parametrize("profile", PROFILES, ids=[p.name for p in PROFILES])
def test_named_profile_metadata_matches_client_wire_class(profile):
    from virtual_plc.profiles import PROFILES as RUNTIME

    spec = RUNTIME[profile.name]
    assert spec.wire_class == profile.wire_class
    assert (spec.cpu_name, spec.cpu_code) == IDENTITIES[profile.name]
    iqr = profile.name == "iQ-R"
    wire = spec.wire
    assert (wire.address_size, wire.code_size, wire.ascii_code_size, wire.ascii_address_size) == ((4, 2, 4, 8) if iqr else (3, 1, 2, 6))
    assert (wire.word_subcommand, wire.bit_subcommand, wire.bit_value_size) == ((2, 3, 2) if iqr else (0, 1, 1))
    assert (wire.password_min, wire.password_max) == ((6, 32) if iqr else (4, 4))
    assert set(spec.devices) == {d.name for d in devices_for(profile)}
    for device in devices_for(profile):
        actual = spec.devices[device.name]
        assert (actual.code, actual.kind, actual.base) == (device.code, device.kind, device.base)
        assert (actual.minimum, actual.maximum) == (0, 0xFFFFFFFF if iqr else 0xFFFFFF)
        assert actual.code == getattr(DeviceConstants, device.name + "_DEVICE")
        if device.name != "LSTC":
            name = CLIENT_NAMES.get(device.name, device.name)
            assert DeviceConstants.get_binary_devicecode(profile.name, name) == (device.code, device.base)


def test_client_ltn_classification_and_unreachable_lstc_are_explicit():
    assert DeviceConstants.get_devicetype("iQ-R", "LTN") == "bit"  # Client inconsistency, not storage policy.
    assert DeviceConstants.LSTC_DEVICE == 0x58
    for wire in ("binary", "ascii"):
        client = pymcprotocol.Type3E(plctype="iQ-R")
        client.setaccessopt(commtype=wire)
        with pytest.raises(DeviceCodeError):
            client._make_devicedata("LSTC0")
        with pytest.raises(DeviceCodeError):
            client._make_devicedata("Z0")
    assert not hasattr(DeviceConstants, "Z_DEVICE")


def test_explicit_profile_device_exclusions():
    for profile in PROFILES:
        for command in COMMANDS + CONTROL_COMMANDS:
            allowed, reason = applicable(command, profile, "4E", "ascii", milestone=6)
            assert allowed and reason is None
        for device in IQR_EXTRA_DEVICES:
            allowed, reason = applicable(COMMANDS[0], profile, "3E", "binary", milestone=6, device=device)
            assert allowed == (profile.name == "iQ-R" and device.name != "LSTC")
            assert reason is None if allowed else bool(reason)
    for device in IQR_EXTRA_DEVICES:
        if device.kind != "bit":
            assert applicable(COMMANDS[1], PROFILES[-1], "3E", "binary", milestone=6, device=device)[0] is False


@pytest.mark.parametrize("device", NATIVE)
def test_native_dword_word_stream_and_low_half_preservation(device):
    from virtual_plc.memory import Memory

    memory = Memory("iQ-R")
    memory.write_words(device, 7, [0x5678, 0x1234, 0xABCD, 0xEEEE])
    assert memory.read_words(device, 7, 4) == [0x5678, 0x1234, 0xABCD, 0xEEEE]
    assert memory.read_words(device, 8, 2) == [0xABCD, 0xEEEE]
    memory.write_words(device, 7, [1])
    assert memory.read_words(device, 7, 2) == [1, 0x1234]
    with pytest.raises(ValueError):
        memory.write_bits(device, 7, [1])


@pytest.mark.parametrize("device", NATIVE)
def test_native_range_checks_use_points_and_validate_whole_write(device):
    from virtual_plc.memory import Memory

    memory = Memory("iQ-R", limits={device: (0, 9)})
    memory.write_words(device, 9, [0x1111, 0x2222])
    with pytest.raises(ValueError):
        memory.write_words(device, 9, [1, 2, 3])
    assert memory.read_words(device, 9, 2) == [0x1111, 0x2222]
    with pytest.raises(ValueError):
        memory.write_words(device, 9, [1, 65536])
    assert memory.read_words(device, 9, 2) == [0x1111, 0x2222]


def test_profile_selection_rejects_conflicting_memory():
    from virtual_plc.memory import Memory
    from virtual_plc.server import Server

    with pytest.raises(ValueError):
        Server(profile="L", memory=Memory("Q"))
