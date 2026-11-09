"""Pin 1E max_points units, including random writes and packed bit groups."""

import pytest

from virtual_plc.one_e import dispatch_1e
from virtual_plc.server import Server


@pytest.mark.parametrize("wire", ["binary", "ascii"])
@pytest.mark.parametrize("command,device,count,expected", [
    (4, "M", 16, 0), (4, "M", 17, 0xC053),
    (5, "D", 10, 0), (5, "M", 1, 0), (5, "M", 2, 0xC054),
    (1, "D", 16, 0), (1, "D", 17, 0xC052),
    (1, "M", 1, 0), (1, "M", 2, 0xC052),
    (3, "M", 1, 0), (3, "M", 2, 0xC052),
])
def test_1e_max_points_16(wire, command, device, count, expected):
    server = Server(slmp_1e=True, max_points=16, port=0)
    random = command in (4, 5)
    if wire == "ascii":
        prefix = f"{command:02X}FF0000".encode()
        name = f"{device:>2}".encode().hex().upper()
        value = b"00" if command == 4 else b"0000"
        if random:
            data = f"{count:02X}00".encode() + b"".join(
                f"{name}{i * 16:08X}".encode() + value for i in range(count))
        else:
            data = f"{name}00000000{count:02X}00".encode() + (value * count if command == 3 else b"")
    else:
        prefix = bytes([command, 0xFF, 0, 0])
        name = f"{device:>2}".encode()[::-1]
        value = bytes(1 if command == 4 else 2)
        if random:
            data = bytes([count, 0]) + b"".join((i * 16).to_bytes(4, "little") + name + value for i in range(count))
        else:
            data = bytes(4) + name + bytes([count, 0]) + (value * count if command == 3 else b"")
    with server._request_lock:
        result = dispatch_1e(prefix + data, server.memory, server._max_points)
    if wire == "ascii":
        assert result[2:4] == (b"5B" if expected else b"00")
        if expected:
            assert int(result[4:], 16) == expected
    else:
        assert result[1] == (0x5B if expected else 0)
        if expected:
            assert int.from_bytes(result[2:], "little") == expected
