"""Fixed-width CPU-name bytes, client-visible padding, and request fill tolerance."""

import socket
from types import SimpleNamespace

import pytest

from test_m3_m4_client import TRANSPORTS, connected
from test_m3_m4_raw import packet, receive
from test_m6_client import connected_profile
from test_m6_profiles_memory import IDENTITIES


PADS = [None, 0, 32, 255, "!"]


@pytest.fixture(scope="module")
def endpoints():
    from virtual_plc.server import Server

    servers = {}
    def create(profile, pad):
        key = profile, pad
        if key not in servers:
            server = Server(profile=profile, **({} if pad is None else {"text_pad": pad}))
            server.start()
            servers[key] = server
        return servers[key]
    yield create
    for server in servers.values():
        server.stop()


@pytest.mark.parametrize("profile", IDENTITIES)
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("pad", PADS)
def test_raw_cpu_name_fill_all_transports(endpoints, profile, frame, wire, pad):
    server = endpoints(profile, pad)
    name, code = IDENTITIES[profile]
    fill = 0 if pad is None else ord(pad) if isinstance(pad, str) else pad
    expected_name = name.encode() + bytes([fill]) * (16 - len(name))
    expected_code = f"{code:04X}".encode() if wire == "ascii" else code.to_bytes(2, "little")
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(packet(frame, wire, 0x0101, data=b""))
        assert receive(connection, frame, wire) == (0, expected_name + expected_code)


@pytest.mark.parametrize("profile", IDENTITIES)
@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("pad", [None, 0, 32, " "])
def test_real_client_keeps_nuls_and_removes_spaces(endpoints, profile, frame, wire, pad):
    server = endpoints(profile, pad)
    name, code = IDENTITIES[profile]
    expected_name = name if pad in (32, " ") else name + "\x00" * (16 - len(name))
    with connected_profile(server, frame, wire) as client:
        assert client.read_cputype() == (expected_name, format(code, "04X" if wire == "ascii" else "04x"))


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_arbitrary_non_utf8_pad_is_emitted_without_hiding_client_decode_error(endpoints, frame, wire):
    with connected_profile(endpoints("Q", 255), frame, wire) as client:
        with pytest.raises(UnicodeDecodeError):
            client.read_cputype()


@pytest.mark.parametrize("profile", ["Q", "iQ-R"])
@pytest.mark.parametrize("frame", ["3E", "4E"])
@pytest.mark.parametrize("pad", [0, 32, 255, "!"])
@pytest.mark.parametrize("command", [0x0401, 0x1401, 0x0403, 0x1402])
def test_ascii_device_code_accepts_configured_fill_and_client_star(endpoints, profile, frame, pad, command):
    server = endpoints(profile, pad)
    fill = ord(pad) if isinstance(pad, str) else pad
    width = 4 if profile == "iQ-R" else 2
    address = b"00000000" if profile == "iQ-R" else b"000000"
    sub = 2 if profile == "iQ-R" else 0
    with socket.create_connection(server.address, timeout=1) as connection:
        for suffix in (b"*" * (width - 1), bytes([fill]) * (width - 1)):
            server.memory.write_words("D", 0, [0x1234])
            descriptor = b"d" + suffix + address
            data = (descriptor + b"0001" if command in (0x0401, 0x1401) else b"0100" + descriptor)
            if command in (0x1401, 0x1402):
                data += b"5678"
            connection.sendall(packet(frame, "ascii", command, sub, data))
            assert receive(connection, frame, "ascii") == (0, b"1234" if command in (0x0401, 0x0403) else b"")
            assert server.memory.read_words("D", 0, 1) == ([0x1234] if command in (0x0401, 0x0403) else [0x5678])


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("pad", [0, 32, "Z"])
def test_length_delimited_echo_and_password_are_not_trimmed(server_factory, frame, wire, pad):
    character = chr(pad) if isinstance(pad, int) else pad
    password = "Ab1" + character
    server = server_factory(text_pad=pad, password=password)
    with connected(server, frame, wire) as client:
        assert client.echo_test("A0Z") == (3, "A0Z")
        client.remote_lock(password=password)
        assert server.locked
        client.remote_unlock(password=password)
        assert not server.locked


def test_all_single_bytes_and_latin1_characters_are_valid():
    from virtual_plc.server import Server

    for value in range(256):
        assert Server(text_pad=value).text_pad == value
        assert Server(text_pad=chr(value)).text_pad == value
    assert Server().text_pad == 0


@pytest.mark.parametrize("pad", [-1, 256, 1.5, None, "", "ab", "\u0100", b" ", [], True])
def test_invalid_text_pad_rejected(pad):
    from virtual_plc.server import Server

    with pytest.raises(ValueError, match="text_pad"):
        Server(text_pad=pad)


@pytest.mark.parametrize("argument,expected", [(None, 0), ("0x00", 0), ("0x20", 32), ("255", 255), ("32", 32)])
def test_cli_text_pad(monkeypatch, argument, expected):
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
    cli.main([] if argument is None else ["--text-pad", argument])
    assert seen["text_pad"] == expected


@pytest.mark.parametrize("argument", ["-1", "256", "0x100", "junk", "1.5", " "])
def test_invalid_cli_text_pad_is_rejected_before_bind(monkeypatch, argument):
    from virtual_plc import __main__ as cli

    def forbidden(*args, **kwargs):
        pytest.fail("invalid padding must not bind a socket")
    # Keep the real constructor's validation, but prevent start/bind.
    monkeypatch.setattr(cli.Server, "start", forbidden)
    with pytest.raises(SystemExit) as error:
        cli.main(["--text-pad", argument])
    assert error.value.code == 2
