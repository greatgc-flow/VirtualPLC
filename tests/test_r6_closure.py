"""0.9.1 closure regressions: SD203 vs max_cells, overlay staging in Memory.write_atomic."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from virtual_plc import Memory, Server
from virtual_plc.memory import CellCapExceeded

ROOT = Path(__file__).resolve().parents[1]


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "virtual_plc", *args], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=30)


def test_server_explains_that_the_sd203_mirror_needs_one_cell():
    memory = Memory(max_cells=1)
    memory.write_words("D", 0, [5])
    with pytest.raises(CellCapExceeded, match="SD203"):
        Server(memory=memory, port=0)


def test_init_snapshot_boundary_counts_sd203(tmp_path):
    snapshot = tmp_path / "i3.json"
    snapshot.write_text(json.dumps({"D": {"0": [1, 2, 3]}}), encoding="utf-8")
    common = ["--init", str(snapshot), "--ethernet-model", "qj71e71", "--show-effective-ethernet"]
    full = _cli(*common, "--max-cells", "3")
    assert full.returncode == 2 and "SD203" in full.stderr, full.stderr
    assert _cli(*common, "--max-cells", "4").returncode == 0


def test_write_atomic_stages_an_overlay_instead_of_copying_the_family():
    """F1: a 1-point random write must not copy (or replace) a large device family."""
    memory = Memory()
    memory.write_words("D", 0, list(range(1, 50001)))
    before = memory._cells["D"]
    memory.write_atomic([("D", 7, "word", [99]), ("D", 60000, "word", [5])])
    assert memory._cells["D"] is before  # updated in place, never copied
    assert memory.read_words("D", 7, 1) == [99] and memory.read_words("D", 60000, 1) == [5]
    assert memory.stored_cells == 50001


def test_write_atomic_overlay_keeps_cap_atomicity_and_dword_halves():
    memory = Memory("iQ-R", max_cells=3)
    memory.write_words("D", 0, [1, 2])
    with pytest.raises(CellCapExceeded):
        memory.write_atomic([("D", 0, "word", [7]), ("D", 5, "word", [1]), ("D", 6, "word", [1])])
    assert memory.read_words("D", 0, 2) == [1, 2] and memory.stored_cells == 2
    memory.write_atomic([("D", 1, "word", [9]), ("D", 5, "word", [3])])  # 1 overwrite + 1 new = 3
    assert memory.read_words("D", 0, 2) == [1, 9] and memory.stored_cells == 3
    big = Memory("iQ-R")
    big.write_words("LTN", 4, [0x5678, 0x1234])
    big.write_atomic([("LTN", 4, "word", [0xBEEF])])  # low half only: high half read through
    assert big.read_words("LTN", 4, 2) == [0xBEEF, 0x1234]


def test_preseeded_sd203_needs_no_extra_cell():
    """BEHAVIOR: one free cell is needed for SD203 'unless it already contains SD203'."""
    memory = Memory(max_cells=2)
    memory.write_words("D", 0, [5])
    memory.write_words("SD", 203, [0])
    Server(memory=memory, port=0)  # RUN overwrites SD203 in place
    assert memory.read_words("SD", 203, 1) == [1] and memory.stored_cells == 2


def test_init_snapshot_with_sd203_fits_exactly_at_the_cap(tmp_path):
    snapshot = tmp_path / "with_sd203.json"
    snapshot.write_text(json.dumps({"D": {"0": [1, 2]}, "SD": {"203": [0]}}), encoding="utf-8")
    result = _cli("--init", str(snapshot), "--max-cells", "3",
                  "--ethernet-model", "qj71e71", "--show-effective-ethernet")
    assert result.returncode == 0, result.stderr


def test_write_atomic_never_scans_or_copies_the_family():
    """F1 (0.9.1): a small random write must not iterate or copy a large device family."""
    class NoScan(dict):
        def _scan(self, *args):
            pytest.fail("write_atomic scanned or copied the whole device family")
        copy = __iter__ = keys = items = values = _scan

    for cap in (None, 60000):
        memory = Memory(max_cells=cap)
        memory.write_words("D", 0, list(range(1, 50001)))
        memory._cells["D"] = NoScan(dict.items(memory._cells["D"]))
        memory.write_atomic([("D", 7, "word", [99]), ("D", 60000, "word", [5])])
        assert dict.get(memory._cells["D"], 7) == 99 and dict.get(memory._cells["D"], 60000) == 5
