"""ASCII dword ordering is endpoint policy; literal fields are independent oracles."""

import socket
from types import SimpleNamespace

import pytest

from test_m3_m4_client import TRANSPORTS
from test_m3_m4_raw import packet, receive
from test_m6_client import connected_profile


PROFILES = ["Q", "L", "QnA", "iQ-L", "iQ-R"]
ORDERS = [None, "swapped", "client"]  # None exercises the omitted option.


@pytest.fixture(scope="module")
def endpoints():
    from virtual_plc.server import Server

    servers = {}
    def create(profile, order):
        key = profile, order
        if key not in servers:
            options = {} if order is None else {"ascii_dword_order": order}
            server = Server(profile=profile, **options)
            server.start()
            servers[key] = server
        return servers[key]
    yield create
    for server in servers.values():
        server.stop()


def descriptor(profile, wire, head):
    if wire == "ascii":
        return (f"D***{head:08d}" if profile == "iQ-R" else f"D*{head:06d}").encode()
    return head.to_bytes(4 if profile == "iQ-R" else 3, "little") + (b"\xa8\x00" if profile == "iQ-R" else b"\xa8")


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("order", ORDERS)
def test_raw_mixed_random_values_and_memory(endpoints, profile, frame, wire, order):
    server = endpoints(profile, order)
    swapped = wire == "ascii" and order != "client"
    sub = 2 if profile == "iQ-R" else 0
    heads = [descriptor(profile, wire, head) for head in (32, 64, 66)]
    counts = b"0102" if wire == "ascii" else b"\x01\x02"
    read = packet(frame, wire, 0x0403, sub, counts + b"".join(heads))
    server.memory.write_words("D", 32, [0xBEEF])
    server.memory.write_words("D", 64, [0x5678, 0x1234, 0xC3D4, 0xA1B2])
    expected = (b"BEEF" + (b"56781234C3D4A1B2" if swapped else b"12345678A1B2C3D4")) if wire == "ascii" else bytes.fromhex("ef be 78 56 34 12 d4 c3 b2 a1")
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(read)
        assert receive(connection, frame, wire) == (0, expected)
        values = [b"beef", b"12345678", b"a1b2c3d4"] if wire == "ascii" else [bytes.fromhex("ef be"), bytes.fromhex("78 56 34 12"), bytes.fromhex("d4 c3 b2 a1")]
        write = counts + b"".join(head + value for head, value in zip(heads, values))
        connection.sendall(packet(frame, wire, 0x1402, sub, write))
        assert receive(connection, frame, wire) == (0, b"")
        words = [0x1234, 0x5678, 0xA1B2, 0xC3D4] if swapped else [0x5678, 0x1234, 0xC3D4, 0xA1B2]
        assert server.memory.read_words("D", 64, 4) == words
        assert server.memory.read_words("D", 32, 1) == [0xBEEF]
        # Batch word responses retain ordinary word order, including native families.
        count = b"0004" if wire == "ascii" else b"\x04\x00"
        connection.sendall(packet(frame, wire, 0x0401, sub, heads[1] + count))
        expected_words = b"12345678A1B2C3D4" if swapped else b"56781234C3D4A1B2"
        assert receive(connection, frame, wire) == (0, expected_words if wire == "ascii" else bytes.fromhex("78 56 34 12 d4 c3 b2 a1"))
        connection.sendall(read)
        assert receive(connection, frame, wire) == (0, b"BEEF12345678A1B2C3D4" if wire == "ascii" else expected)


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("order", ORDERS)
def test_real_client_roundtrip_and_batch_words(endpoints, profile, frame, wire, order):
    server = endpoints(profile, order)
    swapped = wire == "ascii" and order != "client"
    with connected_profile(server, frame, wire) as client:
        client.randomwrite(["D32"], [123], ["D64"], [0x12345678])
        assert client.randomread(["D32"], ["D64"]) == ([123], [0x12345678])
        assert client.batchread_wordunits("D64", 2) == ([0x1234, 0x5678] if swapped else [0x5678, 0x1234])
        client.batchwrite_wordunits("D64", [0x5678, 0x1234])
        assert client.randomread([], ["D64"]) == ([], [0x56781234 if swapped else 0x12345678])


@pytest.mark.unverified
@pytest.mark.parametrize("device", ["LTN", "LSTN", "LCN", "LZ"])
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("order", ORDERS)
def test_native_dword_word_halves(endpoints, device, frame, wire, order):
    server = endpoints("iQ-R", order)
    swapped = wire == "ascii" and order != "client"
    with connected_profile(server, frame, wire) as client:
        client.randomwrite([], [], [device + "7", device + "8"], [0x12345678, -1])
        assert server.memory.read_words(device, 7, 4) == ([0x1234, 0x5678, 65535, 65535] if swapped else [0x5678, 0x1234, 65535, 65535])
        assert client.randomread([], [device + "7", device + "8"]) == ([], [0x12345678, -1])


@pytest.mark.parametrize("value", [None, "", "big", "SWAPPED", []])
def test_invalid_order_rejected_before_bind(value):
    from virtual_plc.server import Server

    with pytest.raises(ValueError, match="ascii_dword_order"):
        Server(ascii_dword_order=value)


def test_default_order_is_swapped():
    from virtual_plc.server import Server

    assert Server().ascii_dword_order == "swapped"


@pytest.mark.parametrize("order", ORDERS)
def test_cli_dword_order(monkeypatch, order):
    from virtual_plc import __main__ as cli

    seen = {}
    def create(host, port, **options):
        seen.update(options)
        return SimpleNamespace(address=(host, port), start=lambda: None, stop=lambda: None)
    def interrupt(timeout):
        assert timeout == 0.5
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, "Server", create)
    monkeypatch.setattr(cli.threading, "Event", lambda: SimpleNamespace(wait=interrupt))
    cli.main([] if order is None else ["--ascii-dword-order", order])
    assert seen["ascii_dword_order"] == (order or "swapped")


def test_cli_rejects_invalid_order():
    from virtual_plc.__main__ import main

    with pytest.raises(SystemExit) as error:
        main(["--ascii-dword-order", "big"])
    assert error.value.code == 2
