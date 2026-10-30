"""Tests for Server ascii_numbering option ('compat' vs 'manual') for issue #6."""

import socket

import pytest

from test_m1_server_raw import receive_exact
from test_m3_m4_raw import packet, receive
from virtual_plc.commands import EndCode
from virtual_plc.memory import Memory
from virtual_plc.server import Server


def test_default_ascii_numbering_is_compat():
    server = Server()
    assert server.ascii_numbering == "compat"


@pytest.mark.parametrize("invalid", ["invalid", "hex", "decimal", "", 123, None])
def test_invalid_ascii_numbering_rejected(invalid):
    with pytest.raises(ValueError, match="ascii_numbering"):
        Server(ascii_numbering=invalid)


def test_manual_policy_reads_hex_addresses():
    memory = Memory("Q")
    # X is base 16 bit device; head 0x1F = 31
    memory.write_bits("X", 31, [1])
    # W is base 16 word device; head 0x10A = 266
    memory.write_words("W", 266, [0xBEEF])

    with Server(memory=memory, ascii_numbering="manual", port=0) as server:
        with socket.create_connection(server.address, timeout=1) as conn:
            # Read X00001F (uppercase)
            conn.sendall(packet("3E", "ascii", 0x0401, 1, b"X*00001F0001"))
            status, data = receive(conn, "3E", "ascii")
            assert status == EndCode.OK
            assert data == b"1"

            # Read X00001f (lowercase)
            conn.sendall(packet("3E", "ascii", 0x0401, 1, b"X*00001f0001"))
            status, data = receive(conn, "3E", "ascii")
            assert status == EndCode.OK
            assert data == b"1"

            # Read W00010A (uppercase)
            conn.sendall(packet("3E", "ascii", 0x0401, 0, b"W*00010A0001"))
            status, data = receive(conn, "3E", "ascii")
            assert status == EndCode.OK
            assert data == b"BEEF"

            # Read W00010a (lowercase)
            conn.sendall(packet("3E", "ascii", 0x0401, 0, b"W*00010a0001"))
            status, data = receive(conn, "3E", "ascii")
            assert status == EndCode.OK
            assert data == b"BEEF"


def test_compat_rejects_hex_letters():
    memory = Memory("Q")
    with Server(memory=memory, ascii_numbering="compat", port=0) as server:
        with socket.create_connection(server.address, timeout=1) as conn:
            conn.sendall(packet("3E", "ascii", 0x0401, 1, b"X*00001F0001"))
            status, _ = receive(conn, "3E", "ascii")
            assert status == EndCode.REQUEST_DATA_ERROR

            conn.sendall(packet("3E", "ascii", 0x0401, 0, b"W*00010A0001"))
            status, _ = receive(conn, "3E", "ascii")
            assert status == EndCode.REQUEST_DATA_ERROR


def test_base10_device_rejects_letters_in_manual():
    memory = Memory("Q")
    with Server(memory=memory, ascii_numbering="manual", port=0) as server:
        with socket.create_connection(server.address, timeout=1) as conn:
            # D is base 10; letters like 'A' must be rejected
            conn.sendall(packet("3E", "ascii", 0x0401, 0, b"D*00001A0001"))
            status, _ = receive(conn, "3E", "ascii")
            assert status == EndCode.REQUEST_DATA_ERROR


def test_cli_ascii_numbering_flag(capsys, monkeypatch):
    from types import SimpleNamespace
    from virtual_plc import __main__ as cli

    seen = {}

    def create(host, port, **options):
        seen.update(options)
        return SimpleNamespace(address=(host, port), start=lambda: None, stop=lambda: None)

    def interrupt(timeout):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "Server", create)
    monkeypatch.setattr(cli.threading, "Event", lambda: SimpleNamespace(wait=interrupt))

    assert cli.main(["--ascii-numbering", "manual"]) == 0
    assert seen["ascii_numbering"] == "manual"

    err = capsys.readouterr().err
    assert "ascii_numbering=manual" in err

    assert cli.main([]) == 0
    assert seen["ascii_numbering"] == "compat"

    with pytest.raises(SystemExit) as error:
        cli.main(["--ascii-numbering", "invalid"])
    assert error.value.code == 2


def test_binary_wire_unaffected():
    memory = Memory("Q")
    memory.write_bits("X", 31, [1])
    with Server(memory=memory, ascii_numbering="manual", port=0) as server:
        with socket.create_connection(server.address, timeout=1) as conn:
            # 3E binary batch read X31 (head=31 -> 1F 00 00, dev=0x9C, points=1)
            conn.sendall(packet("3E", "binary", 0x0401, 1, b"\x1f\x00\x00\x9c\x01\x00"))
            status, data = receive(conn, "3E", "binary")
            assert status == EndCode.OK
            assert data == b"\x10"
