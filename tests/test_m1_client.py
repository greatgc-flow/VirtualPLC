"""Real pymcprotocol 0.3.0 client-compat cells; T17 uses manual-derived bytes."""

import pytest
import pymcprotocol

from tables import COMMANDS, DEVICES, PROFILES, applicable


M1_DEVICES = {"D", "M", "X", "Y", "B", "W", "R", "ZR", "SM", "SD"}
CELLS = [
    (device, command.unit)
    for command in COMMANDS
    if command.name.startswith("batch_write") and applicable(command, PROFILES[0], "3E", "binary")[0]
    for device in DEVICES
    if device.name in M1_DEVICES and (command.unit == "word" or device.kind == "bit")
]


@pytest.mark.parametrize("device, unit", CELLS, ids=[f"{d.name}-{u}" for d, u in CELLS])
def test_t1_t4_all_applicable_batch_cells(client, memory, device, unit):
    # Hex devices use '20' = 32 points; decimal devices use '32'.
    address = device.name + ("20" if device.base == 16 else "32")
    if unit == "word":
        values = [0, 32767, -32768, -1]
        client.batchwrite_wordunits(address, values)
        assert client.batchread_wordunits(address, len(values)) == values
        assert memory.read_words(device.name, 32, len(values)) == [0, 32767, 32768, 65535]
    else:
        values = [1, 0, 1, 0, 1]
        client.batchwrite_bitunits(address, values)
        assert client.batchread_bitunits(address, len(values)) == values
        assert memory.read_bits(device.name, 32, len(values)) == values


@pytest.mark.parametrize("seed", ["T1", "T2"])
def test_migrated_roundtrip_inputs(client, scenarios, seed):
    row = next(row for row in scenarios if row["seed"] == seed)
    assert row["oracle"] == "client-compat"
    action = row["action"]
    unit = "word" if seed == "T1" else "bit"
    getattr(client, f"batchwrite_{unit}units")(action["device"], action["values"])
    assert getattr(client, f"batchread_{unit}units")(action["device"], len(action["values"])) == action["values"]


def test_t3_word_view_over_m(client):
    client.batchwrite_bitunits("M16", [1] + [0] * 14 + [1])
    assert client.batchread_wordunits("M16", 1) == [-32767]


@pytest.mark.parametrize("text", ["A", "Ab09" * 240], ids=["T14-length-1", "T14-length-960"])
def test_t14_echo_boundaries(client, text):
    assert client.echo_test(text) == (len(text), text)


def test_t15_cputype(client):
    # Explicit synthetic identity, not a claim about a physical Q CPU.
    assert client.read_cputype() == ("VirtualPLC-Q\x00\x00\x00\x00", "ffff")


@pytest.mark.unverified
@pytest.mark.parametrize("operation, expected_request, reply, expected_result", [
    ("read", "50 00 00 ff ff 03 00 0c 00 04 00 01 04 00 00 64 00 00 a8 03 00",
     "d0 00 00 ff ff 03 00 08 00 00 00 95 19 02 12 30 11", [0x1995, 0x1202, 0x1130]),
    ("write", "50 00 00 ff ff 03 00 12 00 04 00 01 14 00 00 64 00 00 a8 03 00 95 19 02 12 30 11",
     "d0 00 00 ff ff 03 00 02 00 00 00", None),
    ("bits", "50 00 00 ff ff 03 00 0f 00 04 00 01 14 01 00 0a 00 00 90 05 00 10 10 10",
     "d0 00 00 ff ff 03 00 02 00 00 00", None),
])
def test_t17_client_encoder_against_hand_authored_bytes(monkeypatch, operation, expected_request, reply, expected_result):
    """No server: intercept the real client's encoder, never manufacture requests."""
    instance = pymcprotocol.Type3E(plctype="Q")
    sent = []
    monkeypatch.setattr(instance, "_send", sent.append)
    monkeypatch.setattr(instance, "_recv", lambda: bytes.fromhex(reply))
    if operation == "read":
        result = instance.batchread_wordunits("D100", 3)
    elif operation == "write":
        result = instance.batchwrite_wordunits("D100", [0x1995, 0x1202, 0x1130])
    else:
        result = instance.batchwrite_bitunits("M10", [1, 0, 1, 0, 1])
    assert sent == [bytes.fromhex(expected_request)]
    assert result == expected_result
