"""Invariants for future generated client-compat tests."""

from itertools import product

from tables import CLIENT_NAMES, COMMANDS, DEVICES, PROFILES, Command, Profile, applicable


def test_device_invariants():
    assert len({device.name for device in DEVICES}) == len(DEVICES)
    assert len({device.code for device in DEVICES}) == len(DEVICES)
    assert {device.name for device in DEVICES if device.base == 16} == {
        "X", "Y", "B", "W", "SB", "SW", "DX", "DY", "ZR"
    }
    assert all(device.base in {10, 16} for device in DEVICES)
    assert all(device.kind in {"bit", "word"} for device in DEVICES)


def test_codes_and_bases_match_pinned_client():
    from pymcprotocol.mcprotocolconst import DeviceConstants

    for device in DEVICES:
        assert device.code == getattr(DeviceConstants, device.name + "_DEVICE")
        client_name = CLIENT_NAMES.get(device.name, device.name)
        assert (device.code, device.base) == DeviceConstants.get_binary_devicecode("Q", client_name)
        assert device.kind == DeviceConstants.get_devicetype("Q", client_name)


def test_profiles_and_subcommands():
    assert {profile.name for profile in PROFILES} == {"Q", "L", "QnA", "iQ-L", "iQ-R"}
    assert len(PROFILES) == 5
    for profile in PROFILES:
        assert profile.wire_class == ("iQ-R" if profile.name == "iQ-R" else "Q-class")
        for command in COMMANDS:
            expected = 0 if command.unit is None else {
                ("Q-class", "word"): 0x0000,
                ("Q-class", "bit"): 0x0001,
                ("iQ-R", "word"): 0x0002,
                ("iQ-R", "bit"): 0x0003,
            }[profile.wire_class, command.unit]
            assert command.subcommand(profile) == expected


def test_m1_applicability_matrix():
    included = []
    for command, profile, frame, wire in product(COMMANDS, PROFILES, ("3E", "4E"), ("binary", "ascii")):
        allowed, reason = applicable(command, profile, frame, wire)
        assert allowed == (profile.name == "Q" and frame == "3E" and wire == "binary")
        assert (reason is None) if allowed else bool(reason)
        if allowed:
            included.append(command)
    assert included == list(COMMANDS)


def test_unknown_dimensions_have_reasons():
    for args in (
        (Command("unknown", 0xFFFF), PROFILES[0], "3E", "binary"),
        (COMMANDS[0], Profile("Q", "iQ-R"), "3E", "binary"),
        (COMMANDS[0], PROFILES[0], "1E", "binary"),
        (COMMANDS[0], PROFILES[0], "3E", "unknown"),
    ):
        allowed, reason = applicable(*args)
        assert not allowed and reason
