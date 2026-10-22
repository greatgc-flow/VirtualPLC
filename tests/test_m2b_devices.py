"""M2b table-generated batch/random coverage and independent timer storage."""

import pytest

from tables import CLIENT_NAMES, COMMANDS, DEVICES, PROFILES, applicable


CELLS = [
    (device, command)
    for command in COMMANDS
    if command.name in {"batch_write_word", "batch_write_bit", "random_write", "random_write_bit"}
    and applicable(command, PROFILES[0], "3E", "binary")[0]
    for device in DEVICES
    if command.unit == "word" or device.kind == "bit"
]


@pytest.mark.parametrize("device,command", CELLS, ids=[f"{d.name}-{c.name}" for d, c in CELLS])
def test_generated_device_roundtrips(client, memory, device, command):
    spelling = CLIENT_NAMES.get(device.name, device.name)

    def address(head):
        return spelling + (format(head, "x") if device.base == 16 else str(head))

    if command.name == "batch_write_word":
        client.batchwrite_wordunits(address(32), [0x1234, -1])
        assert client.batchread_wordunits(address(32), 2) == [0x1234, -1]
        assert memory.read_words(device.name, 32, 2) == [0x1234, 65535]
    elif command.name == "batch_write_bit":
        client.batchwrite_bitunits(address(32), [1, 0, 1])
        assert client.batchread_bitunits(address(32), 3) == [1, 0, 1]
        assert memory.read_bits(device.name, 32, 3) == [1, 0, 1]
    elif command.name == "random_write":
        client.randomwrite([address(32)], [-1], [address(64)], [0x12345678])
        assert client.randomread([address(32)], [address(64)]) == ([-1], [0x12345678])
        assert memory.read_words(device.name, 64, 2) == [0x5678, 0x1234]
    else:
        client.randomwrite_bitunits([address(32), address(34)], [1, 1])
        assert client.batchread_bitunits(address(32), 3) == [1, 0, 1]
        assert memory.read_bits(device.name, 32, 3) == [1, 0, 1]


@pytest.mark.parametrize("device", DEVICES, ids=[d.name for d in DEVICES])
def test_profile_codes_bases_and_synthetic_ranges(device):
    from virtual_plc.profiles import MAX_POINT, PROFILES as RUNTIME_PROFILES

    spec = RUNTIME_PROFILES["Q"].devices[device.name]
    assert (spec.code, spec.base, spec.kind) == (device.code, device.base, device.kind)
    assert (spec.minimum, spec.maximum) == (0, MAX_POINT)


@pytest.mark.parametrize("group", [("TS", "TC", "TN"), ("CS", "CC", "CN"), ("SS", "SC", "SN")])
def test_timer_counter_contacts_coils_values_are_independent(memory, group):
    contact, coil, value = group
    memory.write_bits(contact, 0, [1])
    assert memory.read_bits(coil, 0, 1) == [0]
    assert memory.read_words(value, 0, 1) == [0]
    memory.write_bits(coil, 0, [1])
    memory.write_words(value, 0, [123])
    assert memory.read_bits(contact, 0, 1) == [1]
    assert memory.read_bits(coil, 0, 1) == [1]
    assert memory.read_words(value, 0, 1) == [123]
    memory.write_bits(coil, 0, [0])
    assert memory.read_words(value, 0, 1) == [123]  # No timer/counter execution.
    assert memory.read_bits(contact, 0, 1) == [1]


@pytest.mark.parametrize("device", DEVICES, ids=[d.name for d in DEVICES])
def test_custom_point_ranges_validate_whole_word_view(memory_factory, device):
    memory = memory_factory(limits={device.name: (0, 31)})
    head = 16 if device.kind == "bit" else 31
    memory.write_words(device.name, head, [0xFFFF])
    with pytest.raises(ValueError):
        memory.write_words(device.name, head, [0, 1])
    assert memory.read_words(device.name, head, 1) == [0xFFFF]
