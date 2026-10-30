"""Generated client argument, routing and cross-encoding regression coverage."""

from itertools import product
import socket

import pymcprotocol
import pytest

from test_m3_m4_client import TRANSPORTS
from test_m3_m4_raw import packet, receive
from test_m6_client import connected_profile, endpoints
from virtual_plc.codec import decode_request

PROFILES = ["Q", "L", "QnA", "iQ-L", "iQ-R"]
CELLS = list(product(PROFILES, TRANSPORTS))


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_connected_monitoring_timer_updates_socket_timeout(endpoints, frame, wire):
    with connected_profile(endpoints("Q"), frame, wire) as client:
        assert client._sock.gettimeout() == 1
        for seconds in (2, 16383, 1):
            client.setaccessopt(timer_sec=seconds)
            assert client.soc_timeout == seconds + 1
            assert client._sock.gettimeout() == seconds + 1
            assert client.echo_test("ABC") == (3, "ABC")
            client.setaccessopt(timer_sec=0)
            assert client._sock.gettimeout() == seconds + 1
            assert client.soc_timeout == seconds + 1
            assert client.echo_test("DEF") == (3, "DEF")


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
@pytest.mark.parametrize("seconds", [1, 16383])
def test_monitoring_timer_bytes_and_socket_timeout(monkeypatch, frame, wire, seconds):
    client = (pymcprotocol.Type3E if frame == "3E" else pymcprotocol.Type4E)()
    client.setaccessopt(commtype=wire, timer_sec=seconds)
    assert client.soc_timeout == seconds + 1
    client.setaccessopt(timer_sec=0)
    assert client.timer == seconds * 4 and client.soc_timeout == seconds + 1
    sent = []
    monkeypatch.setattr(client, "_send", sent.append)
    monkeypatch.setattr(client, "_recv", lambda: b"\xd0\x00" + b"\x00" * 7 + b"\x00\x00" if wire == "binary" and frame == "3E" else
                        b"\xd4\x00" + b"\x00" * 11 + b"\x00\x00" if wire == "binary" else
                        (b"D000" + b"0" * 18 if frame == "3E" else b"D400" + b"0" * 26))
    client.batchwrite_wordunits("D0", [1])
    offset = (9 if frame == "3E" else 13) * (2 if wire == "ascii" else 1)
    expected = (f"{4 * seconds:04X}".encode() if wire == "ascii" else (4 * seconds).to_bytes(2, "little"))
    assert sent[0][offset:offset + len(expected)] == expected
    assert decode_request(sent[0]).timer == seconds * 4


@pytest.mark.parametrize("value", [-1, 16384, 0.5, "1"])
def test_invalid_monitoring_timer_and_soc_timeout_is_not_an_option(value):
    client = pymcprotocol.Type3E()
    with pytest.raises(ValueError):
        client.setaccessopt(timer_sec=value)
    with pytest.raises(TypeError):
        client.setaccessopt(soc_timeout=2)


@pytest.mark.parametrize("profile,transport", CELLS)
def test_routes_echo_alias_memory_and_state(endpoints, profile, transport):
    frame, wire = transport
    server = endpoints(profile)
    with connected_profile(server, frame, wire) as client:
        original_recv = client._recv
        replies = []
        def capture():
            result = original_recv()
            replies.append(result)
            return result
        client._recv = capture
        for route in [(1, 1, 1, 1), (255, 255, 65535, 255)]:
            client.setaccessopt(network=route[0], pc=route[1], dest_moduleio=route[2], dest_modulesta=route[3])
            client.batchwrite_wordunits("D0", [123])
            encoded = (b"".join(f"{value:0{size*2}X}".encode() for value, size in zip(route, [1,1,2,1]))
                       if wire == "ascii" else b"".join(value.to_bytes(size, "little") for value, size in zip(route, [1,1,2,1])))
            offset = (6 if frame == "4E" else 2) * (2 if wire == "ascii" else 1)
            assert replies[-1][offset:offset + len(encoded)] == encoded
        client.setaccessopt(network=0, pc=0, dest_moduleio=0, dest_modulesta=0)
        assert (client.network, client.pc, client.dest_moduleio, client.dest_modulesta) == (255,255,65535,255)
        client.remote_stop()
    with connected_profile(server, frame, wire) as client:
        assert client.batchread_wordunits("D0", 1) == [123]
        assert server.state == "STOP"


@pytest.mark.parametrize("profile,transport", CELLS)
@pytest.mark.parametrize("kind", ["zero", "one", "max", "over"])
def test_random_count_extrema_and_bit_boundaries(endpoints, profile, transport, kind):
    from pymcprotocol.mcprotocolerror import MCProtocolError
    frame, wire = transport
    server = endpoints(profile)
    wire_spec = server.memory.profile.wire
    with connected_profile(server, frame, wire) as client:
        if kind == "zero":
            with pytest.raises(MCProtocolError) as err:
                client.randomwrite([], [], [], [])
            assert err.value.errorcode == "0xC054"
            with pytest.raises(MCProtocolError) as err:
                client.randomread([], [])
            assert err.value.errorcode == "0xC054"
            with pytest.raises(MCProtocolError) as err:
                client.randomwrite_bitunits([], [])
            assert err.value.errorcode == "0xC053"
        elif kind in ("one", "max"):
            # For 'max', test exact weighted mixed write boundary (e.g. Q: 90w+60dw=1920, iQ-R: 45w+30dw=960),
            # exact read boundary (Q: 192, iQ-R: 96), and exact bit write boundary (Q: 188, iQ-R: 94).
            if kind == "one":
                w_cnt, dw_cnt = 1, 1
                r_w_cnt, r_dw_cnt = 1, 1
                bit_cnt = 1
            else:
                w_cnt = 45 if profile == "iQ-R" else 90
                dw_cnt = 30 if profile == "iQ-R" else 60
                assert w_cnt * 12 + dw_cnt * 14 == wire_spec.random_write_weight_max
                r_w_cnt = wire_spec.random_read_max - dw_cnt
                r_dw_cnt = dw_cnt
                assert r_w_cnt + r_dw_cnt == wire_spec.random_read_max
                bit_cnt = wire_spec.random_bit_max
            words = [f"D{32+i}" for i in range(w_cnt)]
            dwords = [f"D{1024+2*i}" for i in range(dw_cnt)]
            word_values = ([-32768, 32767, -1] * 85)[:w_cnt]
            dword_values = ([-2147483648, 2147483647, -1] * 85)[:dw_cnt]
            client.randomwrite(words, word_values, dwords, dword_values)
            assert client.randomread(words, dwords) == (word_values, dword_values)
            if kind == "max":
                read_words = [f"D{32+i}" for i in range(r_w_cnt)]
                res_w, res_dw = client.randomread(read_words, dwords)
                assert len(res_w) == r_w_cnt and res_w[:w_cnt] == word_values and res_dw == dword_values
            bits = [f"M{i}" for i in range(bit_cnt)]
            values = [i % 2 for i in range(bit_cnt)]
            client.randomwrite_bitunits(bits, values)
            assert client.batchread_bitunits("M0", bit_cnt) == values
        else:
            # max+1 rejection (and 255 count rejection)
            w_over = (wire_spec.random_write_weight_max // 12) + 1
            with pytest.raises(MCProtocolError) as err:
                client.randomwrite([f"D{32+i}" for i in range(w_over)], [1] * w_over, [], [])
            assert err.value.errorcode == "0xC054"
            r_over = wire_spec.random_read_max + 1
            with pytest.raises(MCProtocolError) as err:
                client.randomread([f"D{32+i}" for i in range(r_over)], [])
            assert err.value.errorcode == "0xC054"
            b_over = wire_spec.random_bit_max + 1
            with pytest.raises(MCProtocolError) as err:
                client.randomwrite_bitunits([f"M{i}" for i in range(b_over)], [1] * b_over)
            assert err.value.errorcode == "0xC053"




@pytest.mark.parametrize("profile,transport", CELLS)
def test_random_overlap_and_mismatched_lists(endpoints, profile, transport):
    frame, wire = transport
    server = endpoints(profile)
    with connected_profile(server, frame, wire) as client:
        client.randomwrite(["D0", "D0", "D1"], [1, 2, 3], ["D0", "D1", "D0"],
                           [0x11112222, 0x33334444, 0x55556666])
        assert server.memory.read_words("D", 0, 3) == ([0x5555, 0x6666, 0x4444] if wire == "ascii" else [0x6666, 0x5555, 0x3333])
        client.randomwrite_bitunits(["M1", "M1", "M2", "M1"], [0, 1, 1, 0])
        assert client.batchread_bitunits("M1", 2) == [0, 1]
        original_send = client._send
        def forbidden(data):
            pytest.fail("mismatched lists must fail before sending")
        client._send = forbidden
        for args in [(["D0"], [], [], []), ([], [], ["D0"], []), ([], [1], [], [])]:
            with pytest.raises(ValueError):
                client.randomwrite(*args)
        with pytest.raises(ValueError):
            client.randomwrite_bitunits(["M0"], [])
        client._send = original_send
        assert client.echo_test("0A") == (2, "0A")


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("frame", ["3E", "4E"])
@pytest.mark.parametrize("order", ["client", "swapped"])
def test_cross_encoding_one_socket_and_one_way_sd203(profile, frame, order):
    from virtual_plc import Server
    with Server(profile=profile, ascii_dword_order=order) as server:
        with connected_profile(server, frame, "binary") as client:
            original = client._sock
            client.randomwrite([], [], ["D64"], [0x12345678])
            client.setaccessopt(commtype="ascii")
            assert client._sock is original
            assert client.batchread_wordunits("D64", 2) == [0x5678, 0x1234]
            assert client.randomread([], ["D64"]) == ([], [0x12345678 if order == "client" else 0x56781234])
            client.randomwrite([], [], ["D64"], [0x12345678])
            client.setaccessopt(commtype="binary")
            assert client.randomread([], ["D64"]) == ([], [0x12345678 if order == "client" else 0x56781234])
            client.remote_run(clear_mode=0)
            client.batchwrite_wordunits("SD203", [0])
            assert server.state == "RUN"
            client.remote_stop()
            assert client.batchread_wordunits("SD203", 1) == [0]
            client.remote_reset()
            assert client.echo_test("0A") == (2, "0A")


@pytest.mark.parametrize("profile,transport", CELLS)
def test_unicode_echo_case_width_and_reset_after_error(endpoints, profile, transport):
    from pymcprotocol.mcprotocolerror import MCProtocolError
    frame, wire = transport
    server = endpoints(profile)
    with connected_profile(server, frame, wire) as client:
        with pytest.raises(MCProtocolError):
            client.echo_test("é")  # str.isalnum accepts it; UTF-8 bytes do not form valid echo text.
        assert client.echo_test("0A") == (2, "0A")
        with pytest.raises(Exception):
            client.batchread_wordunits("d0", 1)  # client device names are case-sensitive
        client.batchwrite_bitunits("X0a", [1])
        assert client.batchread_bitunits("X0A", 1) == [1]
        client.remote_run(clear_mode=0)
        with socket.create_connection(server.address, timeout=1) as connection:
            data = b"0001" if wire == "ascii" else b"\x01\x00"
            connection.sendall(packet(frame, wire, 0x1006, 0, data))
            assert receive(connection, frame, wire)[0] != 0
            client.remote_stop()
            connection.sendall(packet(frame, wire, 0x1006, 0, data))
            assert receive(connection, frame, wire) == (0, b"")
            echo = b"00020A" if wire == "ascii" else b"\x02\x000A"
            connection.sendall(packet(frame, wire, 0x0619, data=echo))
            assert receive(connection, frame, wire) == (0, echo)
        client.remote_stop()
        client.remote_reset()
        assert client.echo_test("0A") == (2, "0A")


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_address_width_boundaries_and_raw_lowercase_device(frame, wire):
    from virtual_plc import Server
    for profile, maximum in [("Q", 999999 if wire == "ascii" else 0xFFFFFF),
                             ("iQ-R", 99999999 if wire == "ascii" else 0xFFFFFFFF)]:
        with Server(profile=profile) as server:
            with connected_profile(server, frame, wire) as client:
                client.batchwrite_wordunits(f"D{maximum}", [123])
                assert client.batchread_wordunits(f"D{maximum}", 1) == [123]
                if wire == "binary":
                    with pytest.raises((ValueError, OverflowError)):
                        client.batchwrite_wordunits(f"D{maximum+1}", [1])
                else:
                    from pymcprotocol.mcprotocolerror import MCProtocolError
                    with pytest.raises(MCProtocolError):
                        client.batchwrite_wordunits(f"D{maximum+1}", [1])
            if wire == "ascii":
                device = b"d***" if profile == "iQ-R" else b"d*"
                with socket.create_connection(server.address, timeout=1) as connection:
                    sub = 2 if profile == "iQ-R" else 0
                    connection.sendall(packet(frame, wire, 0x0401, sub, device + str(maximum).encode() + b"0001"))
                    assert receive(connection, frame, wire) == (0, b"007B")
                    connection.sendall(packet(frame, wire, 0x0401, sub, device + str(maximum+1).encode() + b"0001"))
                    assert receive(connection, frame, wire)[0] != 0
                    assert server.memory.read_words("D", maximum, 1) == [123]


@pytest.mark.parametrize("wire", ["binary", "ascii"])
@pytest.mark.parametrize("invalid", [-1, 65536])
def test_invalid_4e_serial_never_sends(wire, invalid, monkeypatch):
    client = pymcprotocol.Type4E()
    client.setaccessopt(commtype=wire)
    client.set_subheaderserial(65535)
    with pytest.raises(ValueError):
        client.set_subheaderserial(invalid)
    assert client.subheaderserial == 65535
    sent = []
    monkeypatch.setattr(client, "_send", sent.append)
    client.subheaderserial = invalid
    with pytest.raises((ValueError, OverflowError)):
        client.batchread_wordunits("D0", 1)
    assert sent == []


@pytest.mark.parametrize("frame,wire", TRANSPORTS)
def test_raw_zero_route_and_zero_monitoring_timer_alias_target(frame, wire, server):
    from test_m1_server_raw import receive_exact
    payload = b"00020A" if wire == "ascii" else b"\x02\x000A"
    encoded = packet(frame, wire, 0x0619, data=payload)
    route = b"00FF03FF00" if wire == "ascii" else b"\x00\xff\xff\x03\x00"
    zero_route = b"0" * 10 if wire == "ascii" else b"\x00" * 5
    encoded = bytearray(encoded.replace(route, zero_route, 1))
    scale = 2 if wire == "ascii" else 1
    header_size = (13 if frame == "4E" else 9) * scale
    encoded[header_size:header_size + 2 * scale] = b"0" * 4 if wire == "ascii" else b"\x00\x00"
    with socket.create_connection(server.address, timeout=1) as connection:
        connection.sendall(encoded)
        header = receive_exact(connection, header_size)
        offset = (6 if frame == "4E" else 2) * scale
        assert header[offset:offset + len(zero_route)] == zero_route
        length = int(header[-4:], 16) if wire == "ascii" else int.from_bytes(header[-2:], "little")
        assert receive_exact(connection, length) == ((b"0000" if wire == "ascii" else b"\x00\x00") + payload)
