"""v0.11.2 audit recommendations closed in 0.11.4: ValueError for bad Memory inputs."""

from pathlib import Path
import re

import pytest

from virtual_plc import Memory


@pytest.mark.parametrize("bad_values", [5, None])
def test_write_words_non_iterable_raises_value_error(bad_values):
    mem = Memory()
    mem.write_words("D", 0, [1234])
    with pytest.raises(ValueError, match="values must be an iterable of integers"):
        mem.write_words("D", 0, bad_values)
    assert mem.read_words("D", 0, 1) == [1234]


@pytest.mark.parametrize("bad_values", [5, None])
def test_write_bits_non_iterable_raises_value_error(bad_values):
    mem = Memory()
    mem.write_bits("M", 0, [1])
    with pytest.raises(ValueError, match="values must be an iterable of integers"):
        mem.write_bits("M", 0, bad_values)
    assert mem.read_bits("M", 0, 1) == [1]


@pytest.mark.parametrize("bad_unit", ["dword", None])
def test_check_unknown_unit_raises_value_error(bad_unit):
    mem = Memory()
    with pytest.raises(ValueError, match='unit must be "bit" or "word"'):
        mem.check("D", 0, 1, bad_unit)


def test_check_valid_unit_returns_spec():
    mem = Memory()
    spec = mem.check("D", 0, 1, "word")
    assert spec is mem.profile.devices["D"]


def test_clear_unknown_mode_raises_value_error_and_preserves_state():
    mem = Memory()
    mem.write_words("D", 0, [42])
    with pytest.raises(ValueError, match='mode must be "latch", "non_latch" or "all"'):
        mem.clear({}, "bogus")
    assert mem.read_words("D", 0, 1) == [42]


def test_clear_all_empties_d0():
    mem = Memory()
    mem.write_words("D", 0, [42])
    mem.clear({}, "all")
    assert mem.read_words("D", 0, 1) == [0]
    assert mem.dump() == {}


def test_generator_values_still_accepted():
    mem = Memory()
    mem.write_words("D", 0, (value for value in [7, 8]))
    assert mem.read_words("D", 0, 2) == [7, 8]


@pytest.mark.parametrize("bad_unit", ["Word", True])
def test_check_unit_is_an_exact_match(bad_unit):
    with pytest.raises(ValueError, match='unit must be "bit" or "word"'):
        Memory().check("D", 0, 1, bad_unit)


@pytest.mark.parametrize("bad_values", [5, None])
def test_write_atomic_non_iterable_raises_value_error(bad_values):
    mem = Memory()
    mem.write_words("D", 0, [9])
    with pytest.raises(ValueError, match="iterable of integers"):
        mem.write_atomic([("D", 0, "word", bad_values)])
    assert mem.read_words("D", 0, 1) == [9]


ROOT = Path(__file__).resolve().parents[1]


def test_behavior_names_the_accepted_check_units_and_clear_modes():
    text = (ROOT / "docs" / "BEHAVIOR.md").read_text(encoding="utf-8")
    assert '`unit` is `"bit"` or `"word"`' in text
    assert "(`latch`, `non_latch`, `all`)" in text


def test_session_record_pr_list_covers_every_release_row():
    """Every release in section 5.1 has its PR in section 5.2 (missed twice by hand)."""
    text = (ROOT / "docs" / "handoff" / "SESSION_20261110_MECE_REVIEW_AND_RELEASES.md").read_text(
        encoding="utf-8")
    releases = re.findall(r"^\| (\d+\.\d+\.\d+) \| \d{4}-\d{2}-\d{2} \|", text, re.M)
    section = text.split("### 5.2 Pull requests", 1)[1].split("###", 1)[0]
    assert len(releases) >= 8
    assert [version for version in releases if version + ")" not in section] == []
