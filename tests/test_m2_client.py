"""M2 client-compat: mixed random access, byte-count boundaries, request order."""

from itertools import product

import pymcprotocol
import pytest


@pytest.mark.parametrize("word_count,dword_count", [
    (0, 0),
    (1, 0), (0, 1), (1, 1),
    (160, 0),    # Q word-only write max (160*12 = 1920)
    (0, 137),    # Q dword-only write max (137*14 = 1918 <= 1920)
    (90, 60),    # Q mixed exact weighted boundary (90*12 + 60*14 = 1920)
    (161, 0),    # Q word-only write max+1 (1932 > 1920)
    (0, 138),    # Q dword-only write max+1 (1932 > 1920)
    (90, 61),    # Q mixed write max+1 (1934 > 1920)
    (255, 0), (0, 255), (255, 255),
])
def test_mixed_random_count_boundaries(client, memory, word_count, dword_count):
    words = [f"D{32 + i}" for i in range(word_count)]
    dwords = [f"D{1024 + 2 * i}" for i in range(dword_count)]
    word_values = ([0, -1, 32767, -32768] * 64)[:word_count]
    dword_values = ([0x12345678, -1, 2147483647, -2147483648] * 64)[:dword_count]
    weight = word_count * 12 + dword_count * 14
    if word_count == dword_count == 0 or weight > 1920:
        # Manual SH-080008 p.98/105 & SH-081257 3.5: total points >= 1 and weight <= 1920 (C054, unverified assignment).
        with pytest.raises(pymcprotocol.mcprotocolerror.MCProtocolError) as err:
            client.randomwrite(words, word_values, dwords, dword_values)
        assert err.value.errorcode == "0xC054"
        if word_count == dword_count == 0 or word_count + dword_count > 192:
            with pytest.raises(pymcprotocol.mcprotocolerror.MCProtocolError) as err:
                client.randomread(words, dwords)
            assert err.value.errorcode == "0xC054"
        return
    client.randomwrite(words, word_values, dwords, dword_values)
    assert client.randomread(words, dwords) == (word_values, dword_values)
    if word_count:
        assert memory.read_words("D", 32, word_count) == [value & 0xFFFF for value in word_values]
    if dword_count:
        assert memory.read_words("D", 1024, 2 * dword_count) == [
            part for value in dword_values for part in (value & 0xFFFF, (value >> 16) & 0xFFFF)
        ]


@pytest.mark.parametrize("word_count,dword_count", [
    (192, 0), (0, 192), (96, 96),        # Q random read max (words + dwords == 192)
    (193, 0), (0, 193), (96, 97),        # Q random read max+1 (193 > 192)
])
def test_random_read_count_boundaries(client, memory, word_count, dword_count):
    words = [f"D{32 + i}" for i in range(word_count)]
    dwords = [f"D{1024 + 2 * i}" for i in range(dword_count)]
    if word_count + dword_count > 192:
        with pytest.raises(pymcprotocol.mcprotocolerror.MCProtocolError) as err:
            client.randomread(words, dwords)
        assert err.value.errorcode == "0xC054"
        return
    memory.write_words("D", 32, [i + 1 for i in range(word_count)] if word_count else [0])
    if dword_count:
        memory.write_words("D", 1024, [0x5678, 0x1234] * dword_count)
    res_w, res_dw = client.randomread(words, dwords)
    assert res_w == [i + 1 for i in range(word_count)]
    assert res_dw == [0x12345678] * dword_count


@pytest.mark.parametrize("count", [0, 1, 188, 189, 255])
def test_random_bit_count_boundaries(client, memory, count):
    values = [i % 2 for i in range(count)]
    if count == 0 or count > 188:
        with pytest.raises(pymcprotocol.mcprotocolerror.MCProtocolError) as err:
            client.randomwrite_bitunits([f"M{i}" for i in range(count)], values)
        assert err.value.errorcode == "0xC053"
        return
    client.randomwrite_bitunits([f"M{i}" for i in range(count)], values)
    if count:
        assert client.batchread_bitunits("M0", count) == values
        assert memory.read_bits("M", 0, count) == values


@pytest.mark.parametrize("kind", ["read-words", "read-dwords", "write-words", "write-dwords", "write-bits"])
def test_client_rejects_256_before_send(monkeypatch, kind):
    instance = pymcprotocol.Type3E()
    sent = []
    monkeypatch.setattr(instance, "_send", sent.append)
    devices = ["D0"] * 256
    with pytest.raises(ValueError):
        if kind == "read-words":
            instance.randomread(devices, [])
        elif kind == "read-dwords":
            instance.randomread([], devices)
        elif kind == "write-words":
            instance.randomwrite(devices, [0] * 256, [], [])
        elif kind == "write-dwords":
            instance.randomwrite([], [], devices, [0] * 256)
        else:
            instance.randomwrite_bitunits(["M0"] * 256, [0] * 256)
    assert sent == []


@pytest.mark.parametrize("word,dword", [(32767, 2147483647), (-32768, -2147483648), (-1, -1)])
def test_signed_values_and_low_word_first(client, memory, word, dword):
    client.randomwrite(["D0"], [word], ["R10"], [dword])
    assert client.randomread(["D0"], ["R10"]) == ([word], [dword])
    assert memory.read_words("R", 10, 2) == [dword & 0xFFFF, (dword >> 16) & 0xFFFF]


def test_duplicates_and_overlaps_apply_in_wire_order(client, memory):
    client.randomwrite(["D0", "D0", "D1"], [1, 2, 3],
                       ["D0", "D1", "D0"], [0x11112222, 0x33334444, 0x55556666])
    assert memory.read_words("D", 0, 3) == [0x6666, 0x5555, 0x3333]
    assert client.randomread(["D0", "D0", "D1"], ["D0", "D1"]) == (
        [0x6666, 0x6666, 0x5555], [0x55556666, 0x33335555]
    )
    client.randomwrite_bitunits(["M1", "M1", "M2", "M1"], [0, 1, 1, 0])
    assert client.batchread_bitunits("M1", 2) == [0, 1]


@pytest.mark.parametrize("kind,value", [("word", -32769), ("word", 32768),
    ("dword", -2147483649), ("dword", 2147483648), ("bit", 2)])
def test_client_rejects_out_of_range_values_before_send(monkeypatch, kind, value):
    instance = pymcprotocol.Type3E()
    sent = []
    monkeypatch.setattr(instance, "_send", sent.append)
    with pytest.raises(ValueError):
        if kind == "bit":
            instance.randomwrite_bitunits(["M0"], [value])
        else:
            instance.randomwrite(["D0"] if kind == "word" else [], [value] if kind == "word" else [],
                                 ["D2"] if kind == "dword" else [], [value] if kind == "dword" else [])
    assert sent == []
