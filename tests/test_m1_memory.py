"""M1 sparse unsigned storage, family isolation, packing, and atomic writes."""

import pytest


@pytest.mark.parametrize("device", ["D", "W", "R", "ZR", "SD"])
def test_word_storage_unsigned_and_sparse(memory, device):
    assert memory.read_words(device, 100, 3) == [0, 0, 0]
    memory.write_words(device, 100, [0, 32768, 65535])
    assert memory.read_words(device, 99, 5) == [0, 0, 32768, 65535, 0]


@pytest.mark.parametrize("device", ["M", "X", "Y", "B", "SM"])
def test_bit_storage_and_odd_count(memory, device):
    memory.write_bits(device, 10, [1, 0, 1, 0, 1])
    assert memory.read_bits(device, 9, 7) == [0, 1, 0, 1, 0, 1, 0]


def test_families_and_instances_are_independent(memory, memory_factory):
    memory.write_words("D", 0, [42])
    assert memory.read_words("R", 0, 1) == [0]
    assert memory_factory().read_words("D", 0, 1) == [0]
    memory.write_bits("M", 0, [1])
    assert memory.read_bits("X", 0, 1) == [0]


def test_t3_t18_word_view_uses_point_address_and_lsb_first(memory):
    memory.write_bits("M", 16, [1] + [0] * 14 + [1] + [1] + [0] * 15)
    memory.write_bits("M", 256, [0] * 16)
    assert memory.read_words("M", 16, 2) == [0x8001, 1]
    memory.write_words("M", 16, [0x0002])
    assert memory.read_bits("M", 16, 16) == [0, 1] + [0] * 14


@pytest.mark.parametrize("values", [[1, -1], [1, 65536]])
def test_invalid_word_tail_is_atomic(memory, values):
    memory.write_words("D", 0, [7, 8])
    with pytest.raises(ValueError):
        memory.write_words("D", 0, values)
    assert memory.read_words("D", 0, 2) == [7, 8]


def test_invalid_bit_tail_is_atomic(memory):
    memory.write_bits("M", 0, [0, 1])
    with pytest.raises(ValueError):
        memory.write_bits("M", 0, [1, 2])
    assert memory.read_bits("M", 0, 2) == [0, 1]


@pytest.mark.parametrize("device, write, read", [("D", "write_words", "read_words"), ("M", "write_bits", "read_bits")])
def test_t12_range_crossing_is_atomic(memory_factory, device, write, read):
    memory = memory_factory(limits={device: (0, 31)})
    getattr(memory, write)(device, 31, [1])
    with pytest.raises(ValueError):
        getattr(memory, write)(device, 31, [0, 1])
    assert getattr(memory, read)(device, 31, 1) == [1]


@pytest.mark.parametrize("method, args", [
    ("read_words", ("D", -1, 1)), ("read_words", ("D", 0, 0)),
    ("write_words", ("D", 0, [])), ("read_bits", ("D", 0, 1)),
    ("write_bits", ("D", 0, [1])), ("read_words", ("UNKNOWN", 0, 1)),
])
def test_invalid_access(memory, method, args):
    with pytest.raises(ValueError):
        getattr(memory, method)(*args)


@pytest.mark.unverified
def test_unaligned_bit_word_head_rejected(memory):
    with pytest.raises(ValueError):
        memory.read_words("M", 1, 1)
