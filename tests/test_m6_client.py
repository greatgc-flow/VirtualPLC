"""Real pinned clients on all profiles; iQ-R uses all reachable device cells."""

from contextlib import contextmanager
from itertools import product

import pymcprotocol
import pytest

from tables import CLIENT_NAMES, COMMANDS, CONTROL_COMMANDS, PROFILES, applicable, devices_for
from test_m3_m4_client import TRANSPORTS
from test_m6_profiles_memory import IDENTITIES, NATIVE


@pytest.fixture(scope="module")
def endpoints():
    from virtual_plc.server import Server

    servers = {}
    def create(profile):
        if profile not in servers:
            servers[profile] = Server(profile=profile, port=0)
            servers[profile].start()
        return servers[profile]
    yield create
    for server in servers.values():
        server.stop()


@contextmanager
def connected_profile(server, frame, wire):
    client = (pymcprotocol.Type4E if frame == "4E" else pymcprotocol.Type3E)(plctype=server.memory.profile.name)
    client.setaccessopt(commtype=wire)
    client.soc_timeout = 1
    if frame == "4E":
        client.set_subheaderserial(0xBEEF)
    client.connect(*server.address)
    try:
        yield client
    finally:
        client.close()


CELLS = [
    (profile, frame, wire, command, device)
    for profile, (frame, wire), command in product(PROFILES, TRANSPORTS, COMMANDS)
    for device in (devices_for(profile) if profile.name == "iQ-R" and command.unit else
                   (next(d for d in devices_for(profile) if d.name == ("M" if command.unit == "bit" else "D")),)
                   if command.unit else (None,))
    if applicable(command, profile, frame, wire, milestone=6, device=device)[0]
]


@pytest.mark.parametrize("profile,frame,wire,command,device", CELLS,
    ids=[f"{p.name}-{f}-{w}-{c.name}-{d.name if d else 'none'}" for p, f, w, c, d in CELLS])
def test_profile_command_device_matrix(endpoints, profile, frame, wire, command, device):
    server = endpoints(profile.name)
    memory = server.memory
    with connected_profile(server, frame, wire) as client:
        if device is None:
            if command.name == "echo":
                assert client.echo_test("Ab09") == (4, "Ab09")
            else:
                name, code = IDENTITIES[profile.name]
                assert client.read_cputype() == (name, format(code, "04X" if wire == "ascii" else "04x"))
            return
        name = CLIENT_NAMES.get(device.name, device.name)
        def address(head):
            return name + (format(head, "x") if device.base == 16 else str(head))
        if command.name.startswith("batch_"):
            values = [1, 0, 1] if command.unit == "bit" else [-1, -32768, 0x1234]
            if command.name.startswith("batch_write"):
                getattr(client, f"batchwrite_{command.unit}units")(address(32), values)
            else:
                getattr(memory, f"write_{command.unit}s")(device.name, 32, [v & 0xFFFF for v in values])
            assert getattr(client, f"batchread_{command.unit}units")(address(32), 3) == values
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


CONTROL_CELLS = [(profile, frame, wire, command) for profile, (frame, wire), command in product(
    PROFILES, TRANSPORTS, CONTROL_COMMANDS
) if applicable(command, profile, frame, wire, milestone=6)[0]]


@pytest.mark.parametrize("profile,frame,wire,command", CONTROL_CELLS,
    ids=[f"{p.name}-{f}-{w}-{c.name}" for p, f, w, c in CONTROL_CELLS])
def test_profile_control_matrix(profile, frame, wire, command):
    from virtual_plc.server import Server

    password = "Ab1234" if profile.name == "iQ-R" else "Ab12"
    initial = "STOP" if command.name in {"latchclear", "reset"} else "RUN"
    server = Server(profile=profile.name, initial_state=initial, password=password, port=0)
    server.start()
    try:
        with connected_profile(server, frame, wire) as client:
            if command.name in {"unlock", "lock"}:
                if command.name == "unlock":
                    client.remote_lock(password=password)
                getattr(client, f"remote_{command.name}")(password=password)
            elif command.name == "run":
                client.remote_run(clear_mode=0, force_exec=True)
            else:
                getattr(client, f"remote_{command.name}")()
            assert client.echo_test("OK") == (2, "OK")
        assert server.state == {"run": "RUN", "stop": "STOP", "pause": "PAUSE"}.get(command.name, initial)
        assert server.locked == (command.name == "lock")
        assert server.reset_count == (1 if command.name == "reset" else 0)
    finally:
        server.stop()


@pytest.mark.unverified
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("device", NATIVE)
def test_native_random_dword_stride_is_one_point(endpoints, frame, wire, device):
    server = endpoints("iQ-R")
    with connected_profile(server, frame, wire) as client:
        client.randomwrite([], [], [device + "7", device + "8"], [0x12345678, -1])
        assert client.batchread_wordunits(device + "7", 4) == [0x5678, 0x1234, -1, -1]
        assert client.randomread([device + "8"], [device + "7", device + "8"]) == ([-1], [0x12345678, -1])
        client.randomwrite([device + "7"], [1], [], [])
        assert client.randomread([], [device + "7"]) == ([], [0x12340001])


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("length", [6, 32])
def test_iqr_password_boundaries(frame, wire, length):
    from virtual_plc.server import Server

    password = "aB09" * 8 if length == 32 else "aB0912"
    server = Server(profile="iQ-R", password=password, port=0)
    server.start()
    try:
        with connected_profile(server, frame, wire) as client:
            client.remote_lock(password=password)
            assert server.locked
            client.remote_unlock(password=password)
            client.remote_pause()
    finally:
        server.stop()


@pytest.mark.parametrize("password", ["12345", "x" * 33, "abcde\u00e9"])
def test_iqr_invalid_password_configuration(password):
    from virtual_plc.server import Server

    with pytest.raises(ValueError):
        Server(profile="iQ-R", password=password)


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_iqr_address_above_24_bits_and_decimal_ascii(endpoints, frame, wire):
    server = endpoints("iQ-R")
    with connected_profile(server, frame, wire) as client:
        client.batchwrite_wordunits("D16909060", [0x1234])
        assert client.batchread_wordunits("D16909060", 1) == [0x1234]
        client.batchwrite_bitunits("X0A", [1])
        assert server.memory.read_bits("X", 10, 1) == [1]
