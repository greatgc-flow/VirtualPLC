"""M2 client-compat: mixed random access, byte-count boundaries, request order."""

from itertools import product

import pymcprotocol
import pytest


@pytest.mark.parametrize("word_count,dword_count", list(product((0, 1, 255), repeat=2)))
def test_mixed_random_count_boundaries(client, memory, word_count, dword_count):
    words = [f"D{32 + i}" for i in range(word_count)]
    dwords = [f"D{1024 + 2 * i}" for i in range(dword_count)]
    word_values = ([0, -1, 32767, -32768] * 64)[:word_count]
    dword_values = ([0x12345678, -1, 2147483647, -2147483648] * 64)[:dword_count]
    client.randomwrite(words, word_values, dwords, dword_values)
    assert client.randomread(words, dwords) == (word_values, dword_values)
    if word_count:
        assert memory.read_words("D", 32, word_count) == [value & 0xFFFF for value in word_values]
    if dword_count:
        assert memory.read_words("D", 1024, 2 * dword_count) == [
            part for value in dword_values for part in (value & 0xFFFF, (value >> 16) & 0xFFFF)
        ]


@pytest.mark.parametrize("count", [0, 1, 255])
def test_random_bit_count_boundaries(client, memory, count):
    values = [i % 2 for i in range(count)]
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
