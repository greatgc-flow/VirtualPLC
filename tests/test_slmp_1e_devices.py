"""1E FX5 device mapping tests derived from JY997D56001-K p.121.

Verifies batch read/write for newly supported 1E devices (TS, TN, CS, CN, R)
at first and last addresses in binary and ASCII, out-of-range address errors (C056),
and refusal of undefined/inaccessible devices with C05B.

Timers and counters: simulator policy: no PLC logic (plain storage only).
"""

import socket
import pytest

from virtual_plc import Server
from virtual_plc.memory import Memory


def req(command, *, wire="binary", device="D", head=0, count=1,
        payload=b"", pc=0xFF, timer=0, reserved=0):
    # bytes = raw logical 2-byte device code (binary wire sends it reversed)
    name = device if isinstance(device, bytes) else device.encode("ascii").ljust(2, b" ")
    if wire == "ascii":
        return (f"{command:02X}{pc:02X}{timer:04X}".encode()
                + name.hex().upper().encode() + f"{head:08X}{count:02X}{reserved:02X}".encode()
                + payload)
    return (bytes((command, pc)) + timer.to_bytes(2, "little")
            + head.to_bytes(4, "little") + name[::-1] + bytes((count, reserved))
            + payload)


def receive_exact(conn, count):
    data = b""
    while len(data) < count:
        chunk = conn.recv(count - len(data))
        if not chunk:
            raise AssertionError("1E response truncated")
        data += chunk
    return data


# Newly supported 1E devices per JY997D56001-K p.121:
# TS: bit, 0..511
# TN: word, 0..511
# CS: bit, 0..255
# CN: word, 0..255
# R:  word, 0..32767
NEW_DEVICES = [
    ("TS", "bit", 511),
    ("TN", "word", 511),
    ("CS", "bit", 255),
    ("CN", "word", 255),
    ("R", "word", 32767),
]


@pytest.mark.parametrize("device,kind,last_addr", NEW_DEVICES)
@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_1e_new_devices_batch_read_write_first_and_last_address(device, kind, last_addr, wire):
    """Batch read and write at first (0) and last address in binary and ASCII."""
    read_cmd = 0 if kind == "bit" else 1
    write_cmd = 2 if kind == "bit" else 3

    with Server(slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)

            for addr in (0, last_addr):
                if kind == "bit":
                    val_bin_payload = b"\x10"
                    val_asc_payload = b"1"
                    exp_bin_read = b"\x80\x00\x10"
                    exp_asc_read = b"80001"
                else:
                    val_bin_payload = b"\x34\x12"
                    val_asc_payload = b"1234"
                    exp_bin_read = b"\x81\x00\x34\x12"
                    exp_asc_read = b"81001234"

                # Write
                w_payload = val_asc_payload if wire == "ascii" else val_bin_payload
                client.sendall(req(write_cmd, wire=wire, device=device, head=addr, count=1, payload=w_payload))
                exp_write_ack = (f"{write_cmd | 0x80:02X}00".encode() if wire == "ascii"
                                 else bytes([write_cmd | 0x80, 0x00]))
                assert receive_exact(client, len(exp_write_ack)) == exp_write_ack

                # Read
                client.sendall(req(read_cmd, wire=wire, device=device, head=addr, count=1))
                exp_read = exp_asc_read if wire == "ascii" else exp_bin_read
                assert receive_exact(client, len(exp_read)) == exp_read


@pytest.mark.parametrize("device,kind,last_addr", NEW_DEVICES)
@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_1e_new_devices_out_of_range_address_error(device, kind, last_addr, wire):
    """Out-of-range address access returns C056 address error per one_e ERROR mapping."""
    read_cmd = 0 if kind == "bit" else 1
    write_cmd = 2 if kind == "bit" else 3
    out_of_range_addr = last_addr + 1

    with Server(slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)

            # Read out of range
            client.sendall(req(read_cmd, wire=wire, device=device, head=out_of_range_addr, count=1))
            exp_err = (f"{read_cmd | 0x80:02X}5BC056".encode() if wire == "ascii"
                       else bytes([read_cmd | 0x80, 0x5B, 0x56, 0xC0]))
            assert receive_exact(client, len(exp_err)) == exp_err

            # Write out of range
            payload = (b"1" if wire == "ascii" else b"\x10") if kind == "bit" else (b"1234" if wire == "ascii" else b"\x34\x12")
            client.sendall(req(write_cmd, wire=wire, device=device, head=out_of_range_addr, count=1, payload=payload))
            exp_err_w = (f"{write_cmd | 0x80:02X}5BC056".encode() if wire == "ascii"
                         else bytes([write_cmd | 0x80, 0x5B, 0x56, 0xC0]))
            assert receive_exact(client, len(exp_err_w)) == exp_err_w


# Undefined, inaccessible or ambiguous direct devices refused with 0xC05B:
# - Inaccessible (): L, F, B, W, TC, SS, SC, SN, CC, LCC, SB, SW, Z, LZ, DX, DY
# - Specific only (, direct device code specification refused): LCS/LS, LCN/LN, SM, SD
# - Unsupported in synthetic Q memory: S (step relay)
REFUSED_DEVICES = [
    ("S", 0), ("L", 1), ("F", 0), ("B", 1), ("W", 1),
    ("TC", 0), ("CC", 0), ("SS", 0), ("SC", 0), ("SN", 1),
    ("LS", 0), ("LN", 1), ("SM", 0), ("SD", 1), ("Z", 1),
    # Non-ASCII codes (binary wire 00 A8 / FF FF; ASCII "A800" / "FFFF").
    (b"\xa8\x00", 0), (b"\xa8\x00", 1), (b"\xff\xff", 0), (b"\xff\xff", 1),
]
HIGH_BYTE_CODES = [b"\xa8\x00", b"\xff\xff"]


def random_req(command, *, wire, device):
    """One-record 04H/05H random write naming a raw logical device code."""
    width = 1 if command == 4 else 2
    if wire == "ascii":
        return (f"{command:02X}FF00000100".encode()
                + device.hex().upper().encode() + b"00000000" + b"0" * (2 * width))
    return (bytes((command, 0xFF, 0, 0, 1, 0)) + (0).to_bytes(4, "little")
            + device[::-1] + bytes(width))


@pytest.mark.parametrize("device", HIGH_BYTE_CODES)
@pytest.mark.parametrize("command", [2, 3])
@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_1e_high_byte_device_codes_refused_on_batch_write(device, command, wire):
    payload = (b"0" if command == 2 else b"0000") if wire == "ascii" else (b"\x00" if command == 2 else b"\x00\x00")
    with Server(slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(req(command, wire=wire, device=device, payload=payload))
            exp = (f"{command | 0x80:02X}5BC05B".encode() if wire == "ascii"
                   else bytes([command | 0x80, 0x5B, 0x5B, 0xC0]))
            assert receive_exact(client, len(exp)) == exp


@pytest.mark.parametrize("device", HIGH_BYTE_CODES)
@pytest.mark.parametrize("command", [4, 5])
@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_1e_high_byte_device_codes_refused_on_random_write(device, command, wire):
    with Server(slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(random_req(command, wire=wire, device=device))
            exp = (f"{command | 0x80:02X}5BC05B".encode() if wire == "ascii"
                   else bytes([command | 0x80, 0x5B, 0x5B, 0xC0]))
            assert receive_exact(client, len(exp)) == exp


@pytest.mark.parametrize("device,cmd", REFUSED_DEVICES)
@pytest.mark.parametrize("wire", ["binary", "ascii"])
def test_1e_undefined_and_ambiguous_devices_refused_with_c05b(device, cmd, wire):
    """Undefined and ambiguous device codes must be refused with C05B."""
    with Server(slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(req(cmd, wire=wire, device=device, head=0, count=1))
            exp_err = (f"{cmd | 0x80:02X}5BC05B".encode() if wire == "ascii"
                       else bytes([cmd | 0x80, 0x5B, 0x5B, 0xC0]))
            assert receive_exact(client, len(exp_err)) == exp_err


def test_1e_timers_counters_plain_storage_policy_no_plc_logic():
    """simulator policy: no PLC logic - timers/counters have independent plain storage."""
    memory = Memory("Q")
    with Server(slmp_1e=True, memory=memory) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)

            # TS and TN are plain independent storage
            client.sendall(req(2, device="TS", head=10, count=1, payload=b"\x10"))
            assert receive_exact(client, 2) == b"\x82\x00"
            assert memory.read_bits("TS", 10, 1) == [1]
            assert memory.read_words("TN", 10, 1) == [0]

            client.sendall(req(3, device="TN", head=10, count=1, payload=b"\x56\x34"))
            assert receive_exact(client, 2) == b"\x83\x00"
            assert memory.read_words("TN", 10, 1) == [0x3456]
            assert memory.read_bits("TS", 10, 1) == [1]

            # CS and CN are plain independent storage
            client.sendall(req(2, device="CS", head=20, count=1, payload=b"\x10"))
            assert receive_exact(client, 2) == b"\x82\x00"
            assert memory.read_bits("CS", 20, 1) == [1]
            assert memory.read_words("CN", 20, 1) == [0]

            client.sendall(req(3, device="CN", head=20, count=1, payload=b"\x78\x56"))
            assert receive_exact(client, 2) == b"\x83\x00"
            assert memory.read_words("CN", 20, 1) == [0x5678]
            assert memory.read_bits("CS", 20, 1) == [1]


def test_1e_xy_octal_behavior_unchanged():
    """X/Y range is 0..255 (0..377 octal); head 255 passes, head 256 returns C056."""
    with Server(slmp_1e=True) as plc:
        with socket.create_connection(plc.address, timeout=2) as client:
            client.settimeout(2)

            # Head 255 valid
            client.sendall(req(0, device="X", head=255, count=1))
            assert receive_exact(client, 3) == b"\x80\x00\x00"
            client.sendall(req(0, device="Y", head=255, count=1))
            assert receive_exact(client, 3) == b"\x80\x00\x00"

            # Head 256 out of range -> C056
            client.sendall(req(0, device="X", head=256, count=1))
            assert receive_exact(client, 4) == b"\x80\x5b\x56\xc0"
            client.sendall(req(0, device="Y", head=256, count=1))
            assert receive_exact(client, 4) == b"\x80\x5b\x56\xc0"
