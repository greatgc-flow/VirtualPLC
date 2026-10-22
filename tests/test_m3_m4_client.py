"""Client-compat matrix: every command/device cell on all four transports."""

from contextlib import contextmanager
from itertools import product

import pymcprotocol
import pytest

from tables import CLIENT_NAMES, COMMANDS, DEVICES, PROFILES, applicable


TRANSPORTS = list(product(("3E", "4E"), ("binary", "ascii")))
CELLS = [
    (frame, wire, command, device)
    for frame, wire, command in product(("3E", "4E"), ("binary", "ascii"), COMMANDS)
    if applicable(command, PROFILES[0], frame, wire, milestone=4)[0]
    for device in (DEVICES if command.unit else (None,))
    if applicable(command, PROFILES[0], frame, wire, milestone=4, device=device)[0]
]


@pytest.fixture(scope="module")
def endpoint():
    from virtual_plc.memory import Memory
    from virtual_plc.server import Server

    memory = Memory()
    server = Server(port=0, memory=memory)
    server.start()
    try:
        yield server, memory
    finally:
        server.stop()


@contextmanager
def connected(server, frame, wire, serial=0xBEEF):
    client = (pymcprotocol.Type4E if frame == "4E" else pymcprotocol.Type3E)()
    client.setaccessopt(commtype=wire)
    client.soc_timeout = 0.5
    if frame == "4E":
        client.set_subheaderserial(serial)
    client.connect(*server.address)
    try:
        yield client
    finally:
        client.close()


@pytest.mark.parametrize("frame,wire,command,device", CELLS,
    ids=[f"{f}-{w}-{c.name}-{d.name if d else 'none'}" for f, w, c, d in CELLS])
def test_all_command_device_cells(endpoint, frame, wire, command, device):
    server, memory = endpoint
    with connected(server, frame, wire) as client:
        if device is None:
            if command.name == "echo":
                assert client.echo_test("Ab09") == (4, "Ab09")
            else:
                assert client.read_cputype() == ("VirtualPLC-Q", "FFFF" if wire == "ascii" else "ffff")
            return
        name = CLIENT_NAMES.get(device.name, device.name)

        def address(head):
            return name + (format(head, "x") if device.base == 16 else str(head))

        if command.name.startswith("batch_"):
            unit = command.unit
            values = [1, 0, 1] if unit == "bit" else [-1, -32768, 0x1234]
            read = getattr(client, f"batchread_{unit}units")
            if command.name.startswith("batch_write"):
                getattr(client, f"batchwrite_{unit}units")(address(32), values)
            else:
                getattr(memory, f"write_{unit}s")(device.name, 32, [v & 0xFFFF for v in values])
            assert read(address(32), 3) == values
            assert getattr(memory, f"read_{unit}s")(device.name, 32, 3) == [v & 0xFFFF for v in values]
        elif command.name in {"random_read", "random_write"}:
            if command.name == "random_write":
                client.randomwrite([address(32)], [-2], [address(64)], [0x12345678])
            else:
                memory.write_words(device.name, 32, [65534])
                memory.write_words(device.name, 64, [0x5678, 0x1234])
            assert client.randomread([address(32)], [address(64)]) == ([-2], [0x12345678])
            assert memory.read_words(device.name, 64, 2) == [0x5678, 0x1234]
        else:
            memory.write_bits(device.name, 32, [0, 1, 0])
            client.randomwrite_bitunits([address(32), address(33), address(34)], [1, 0, 1])
            assert client.batchread_bitunits(address(32), 3) == [1, 0, 1]


def test_explicit_matrix_exclusions():
    for profile, frame, wire, command in product(PROFILES, ("3E", "4E"), ("binary", "ascii"), COMMANDS):
        allowed, reason = applicable(command, profile, frame, wire, milestone=4)
        assert allowed == (profile.name == "Q")
        assert reason is None if allowed else bool(reason)
    assert {c.name for _, _, c, _ in CELLS} == {c.name for c in COMMANDS}
    assert {(f, w) for f, w, _, _ in CELLS} == set(TRANSPORTS)
    for command, device in product(COMMANDS, DEVICES):
        allowed, reason = applicable(command, PROFILES[0], "4E", "ascii", milestone=4, device=device)
        assert allowed == (command.unit != "bit" or device.kind == "bit")
        assert reason is None if allowed else bool(reason)


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_echo_limits_and_signed_random_values(endpoint, frame, wire):
    server, memory = endpoint
    with connected(server, frame, wire) as client:
        for text in ("A", "aB09" * 240):
            assert client.echo_test(text) == (len(text), text)
        client.randomwrite(["D0"], [-32768], ["D2", "D4"], [-2147483648, -1])
        assert client.randomread(["D0"], ["D2", "D4"]) == ([-32768], [-2147483648, -1])
        assert memory.read_words("D", 2, 4) == [0, 32768, 65535, 65535]


@pytest.mark.parametrize("frame", ["3E", "4E"])
def test_x0a_uses_decimal_ascii_address(endpoint, frame):
    server, memory = endpoint
    memory.write_bits("X", 10, [0])
    memory.write_bits("X", 16, [0])
    with connected(server, frame, "ascii") as client:
        assert client._make_devicedata("X0A") == b"X*000010"
        client.batchwrite_bitunits("X0A", [1])
        assert client.batchread_bitunits("X0A", 1) == [1]
    assert memory.read_bits("X", 10, 1) == [1]
    assert memory.read_bits("X", 16, 1) == [0]


@pytest.mark.parametrize("frame", ["3E", "4E"])
@pytest.mark.parametrize("operation", ["batch-read", "batch-write", "random-read", "random-write", "random-bit"])
def test_ascii_overwidth_address_is_rejected_without_mutation(endpoint, frame, operation):
    server, memory = endpoint
    memory.write_words("D", 100000, [7, 8])
    memory.write_words("D", 1000000, [9, 10])
    memory.write_words("D", 0, [11])
    memory.write_bits("M", 0, [0])
    with connected(server, frame, "ascii") as client:
        from pymcprotocol.mcprotocolerror import MCProtocolError

        with pytest.raises(MCProtocolError):
            if operation == "batch-read":
                client.batchread_wordunits("D1000000", 1)
            elif operation == "batch-write":
                client.batchwrite_wordunits("D1000000", [42])
            elif operation == "random-read":
                client.randomread(["D0"], ["D1000000"])
            elif operation == "random-write":
                client.randomwrite(["D0"], [42], ["D1000000"], [123])
            else:
                client.randomwrite_bitunits(["M0", "M1000000"], [1, 1])
        assert client.echo_test("OK") == (2, "OK")
    assert memory.read_words("D", 100000, 2) == [7, 8]
    assert memory.read_words("D", 1000000, 2) == [9, 10]
    assert memory.read_words("D", 0, 1) == [11]
    assert memory.read_bits("M", 0, 1) == [0]
