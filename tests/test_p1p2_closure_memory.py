"""P1/P2 review closure: direct Memory API validation and atomic dword staging."""

import pytest

from virtual_plc.memory import Memory


# F8: heads must be exact ints (no floats/bools) for every access path.
@pytest.mark.parametrize("head", [0.5, 1.0, True, False, "1", None])
@pytest.mark.parametrize("call", [
    lambda m, h: m.write_words("LTN", h, [7]),
    lambda m, h: m.write_words("D", h, [7]),
    lambda m, h: m.read_words("D", h, 1),
    lambda m, h: m.read_bits("M", h, 1),
    lambda m, h: m.write_bits("M", h, [1]),
    lambda m, h: m.write_atomic([("D", h, "word", [1])]),
])
def test_non_int_heads_are_rejected_without_mutation(head, call):
    memory = Memory("iQ-R")
    with pytest.raises(ValueError):
        call(memory, head)
    assert memory.dump() == {}


@pytest.mark.parametrize("count", [1.5, True])
def test_non_int_counts_are_rejected(count):
    with pytest.raises(ValueError):
        Memory("Q").read_words("D", 0, count)


# F10: write_atomic dword staging and validation branches.
def test_write_atomic_stages_native_dword_halves():
    memory = Memory("iQ-R")
    memory.write_words("LTN", 4, [0x1111, 0x2222])
    memory.write_atomic([("LTN", 4, "word", [0xAAAA]), ("LTN", 5, "word", [0x3333, 0x4444]),
                         ("LTN", 4, "word", [0xBBBB, 0xCCCC]), ("D", 0, "word", [5])])
    assert memory.read_words("LTN", 4, 4) == [0xBBBB, 0xCCCC, 0x3333, 0x4444]
    assert memory.read_words("D", 0, 1) == [5]


@pytest.mark.parametrize("operations, message", [
    ([("D", 0, "dword", [1])], "bit or word unit"),
    ([("D", 0, "word", [1.0])], "must be integers"),
    ([("D", 0, "word", [True])], "must be integers"),
    ([("D", 0, "word", [0x10000])], "out of range"),
    ([("M", 0, "bit", [2])], "out of range"),
    ([("D", 0, "word", [-1])], "out of range"),
])
def test_write_atomic_rejects_bad_operations_atomically(operations, message):
    memory = Memory("iQ-R")
    memory.write_words("LTN", 0, [1, 2])
    before = memory.dump()
    with pytest.raises(ValueError, match=message):
        memory.write_atomic([("LTN", 0, "word", [9, 9])] + operations)
    assert memory.dump() == before


@pytest.mark.parametrize("runs", [{0: [1]}, {"0": []}, {"0": 1}])
def test_load_rejects_bad_run_shapes(runs):
    memory = Memory("Q")
    with pytest.raises(ValueError, match="nonempty lists"):
        memory.load({"D": runs})
    assert memory.dump() == {}
