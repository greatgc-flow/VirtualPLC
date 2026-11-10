"""#79: optional stored-cell cap (Memory(max_cells=N) / --max-cells N).

Simulator safety policy, not PLC behavior: only NEW stored points count,
overwrites are always allowed, and a request that would exceed the cap is
rejected as a whole (C056) without changing memory.
"""
import json
import socket
import struct

import pytest

import virtual_plc.__main__ as cli
from virtual_plc import Memory, OutOfRange, Server
from virtual_plc.memory import CellCapExceeded


def test_default_is_uncapped():
    memory = Memory()
    assert memory.max_cells is None
    memory.write_words("D", 0, list(range(960)))
    assert memory.stored_cells == 960


@pytest.mark.parametrize("bad", [0, -1, True, 1.5, "3"])
def test_max_cells_must_be_positive_int_or_none(bad):
    with pytest.raises(ValueError, match="max_cells"):
        Memory(max_cells=bad)


def test_n_plus_one_distinct_addresses_raise_and_storage_does_not_grow():
    memory = Memory(max_cells=3)
    memory.write_words("D", 0, [1, 2, 3])
    before = memory.dump()
    with pytest.raises(CellCapExceeded) as error:
        memory.write_words("D", 3, [4])
    assert isinstance(error.value, OutOfRange)
    assert memory.dump() == before and memory.stored_cells == 3


def test_overwrites_and_zero_overwrites_are_always_allowed():
    memory = Memory(max_cells=2)
    memory.write_words("D", 0, [1, 2])
    memory.write_words("D", 0, [0, 0])
    memory.write_words("D", 1, [7])
    assert memory.read_words("D", 0, 2) == [0, 7]
    with pytest.raises(CellCapExceeded):
        memory.write_words("D", 5, [0])  # a new key counts even when the value is zero


def test_partially_new_batch_is_rejected_whole():
    memory = Memory(max_cells=3)
    memory.write_words("D", 0, [9])
    with pytest.raises(CellCapExceeded):
        memory.write_words("D", 0, [1, 2, 3, 4])  # 3 new keys -> 4 > 3
    assert memory.dump() == {"D": {"0": [9]}}


def test_bit_device_word_view_counts_sixteen_points_and_dword_counts_native_points():
    memory = Memory(max_cells=16)
    memory.write_words("M", 0, [0xFFFF])
    assert memory.stored_cells == 16
    with pytest.raises(CellCapExceeded):
        memory.write_bits("M", 16, [1])
    dwords = Memory("iQ-R", max_cells=1)
    dwords.write_words("LCN", 0, [1, 2])  # two halves of one native dword point
    assert dwords.stored_cells == 1
    with pytest.raises(CellCapExceeded):
        dwords.write_words("LCN", 1, [1, 2])


def test_write_atomic_checks_cap_for_whole_request():
    memory = Memory(max_cells=2)
    with pytest.raises(CellCapExceeded):
        memory.write_atomic([("D", 0, "word", [1]), ("M", 0, "bit", [1]), ("D", 1, "word", [2])])
    assert memory.stored_cells == 0
    memory.write_atomic([("D", 0, "word", [1]), ("D", 0, "word", [5]), ("M", 0, "bit", [1])])
    assert memory.dump() == {"D": {"0": [5]}, "M": {"0": [1]}}


def test_clear_frees_cells():
    memory = Memory(max_cells=1)
    memory.write_words("D", 0, [1])
    memory.clear({}, "all")
    memory.write_words("D", 1, [1])
    assert memory.dump() == {"D": {"1": [1]}}


def test_snapshot_exceeding_cap_is_rejected_without_change():
    memory = Memory(max_cells=3)
    memory.write_words("D", 0, [1])
    with pytest.raises(ValueError):
        memory.load({"D": {"10": [1, 2, 3]}})
    assert memory.dump() == {"D": {"0": [1]}}
    memory.load({"D": {"10": [1, 2]}})
    assert memory.stored_cells == 3


# Raw 3E binary helpers (test-only arithmetic).
def _frame(command, subcommand, data):
    body = struct.pack("<HHH", 4, command, subcommand) + data
    return b"\x50\x00\x00\xff\xff\x03\x00" + struct.pack("<H", len(body)) + body


def _device(head, code):
    return head.to_bytes(3, "little") + bytes([code])


def _exact(connection, count):
    data = b""
    while len(data) < count:
        chunk = connection.recv(count - len(data))
        assert chunk
        data += chunk
    return data


def _end_code(connection, frame):
    connection.sendall(frame)
    header = _exact(connection, 9)
    body = _exact(connection, int.from_bytes(header[7:9], "little"))
    return int.from_bytes(body[:2], "little")


D, M = 0xA8, 0x90


def test_3e_batch_and_random_writes_return_c056_and_leave_memory_unchanged():
    memory = Memory(max_cells=4)  # Server's SD203 mirror takes one cell
    with Server(memory=memory, port=0) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            ok = _frame(0x1401, 0, _device(0, D) + struct.pack("<H", 2) + struct.pack("<HH", 1, 2))
            assert _end_code(client, ok) == 0
            before = memory.dump()
            over = _frame(0x1401, 0, _device(2, D) + struct.pack("<H", 2) + struct.pack("<HH", 3, 4))
            assert _end_code(client, over) == 0xC056
            # Random word write: overwrite D0, then two new keys -> second new key exceeds.
            random_words = _frame(0x1402, 0, bytes([3, 0]) + _device(0, D) + struct.pack("<H", 9)
                                  + _device(5, D) + struct.pack("<H", 5) + _device(6, D) + struct.pack("<H", 6))
            assert _end_code(client, random_words) == 0xC056
            random_bits = _frame(0x1402, 1, bytes([2]) + _device(0, M) + b"\x01" + _device(1, M) + b"\x01")
            assert _end_code(client, random_bits) == 0xC056
            assert memory.dump() == before
            # Overwrites still succeed when the cap is full.
            fill = _frame(0x1401, 0, _device(2, D) + struct.pack("<H", 1) + struct.pack("<H", 3))
            assert _end_code(client, fill) == 0
            assert _end_code(client, ok) == 0
    assert memory.stored_cells == 4


def _exchange_1e(client, frame, size):
    client.sendall(frame)
    return _exact(client, size)


def test_1e_batch_and_random_writes_return_c056_and_leave_memory_unchanged():
    memory = Memory("Q", max_cells=2)  # SD203 + one cell
    with Server(memory=memory, port=0, slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            # ASCII 03H batch word write: D0 x1 then D1..D2 x2.
            assert _exchange_1e(client, b"03FF00004420000000000100" + b"0001", 4) == b"8300"
            before = memory.dump()
            assert _exchange_1e(client, b"03FF00004420000000010200" + b"00020003", 8) == b"835BC056"
            # ASCII 05H random word write of a new D5.
            assert _exchange_1e(client, b"05FF00000100" + b"442000000005" + b"1234", 8) == b"855BC056"
            assert memory.dump() == before
            assert _exchange_1e(client, b"03FF00004420000000000100" + b"0009", 4) == b"8300"
    assert memory.read_words("D", 0, 1) == [9]


def _exit_code(arguments):
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    return error.value.code


@pytest.mark.parametrize("value", ["0", "-5"])
def test_cli_rejects_nonpositive_max_cells(capsys, value):
    assert _exit_code(["--port", "0", "--max-cells", value]) == 2
    assert "max_cells" in capsys.readouterr().err


def test_cli_init_exceeding_cap_exits_2(tmp_path, monkeypatch, capsys):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"D": {"0": [1, 2, 3]}}), encoding="utf-8")
    monkeypatch.setattr(cli.Server, "start", lambda self: pytest.fail("must not bind"))
    assert _exit_code(["--port", "0", "--init", str(seed), "--max-cells", "2"]) == 2
    assert capsys.readouterr().err.strip().endswith("; see: virtual-plc guide memory")


def test_cli_max_cells_reaches_server_memory(monkeypatch):
    seen = []

    def start(self):
        seen.append(self.memory)
        raise OSError("stop here")

    monkeypatch.setattr(cli.Server, "start", start)
    assert cli.main(["--port", "0", "--max-cells", "10"]) == 1
    assert seen[0].max_cells == 10
