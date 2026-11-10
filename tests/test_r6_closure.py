"""Round-6 (0.9.0) closure review regressions: SD203 vs max_cells, curated release notes."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from virtual_plc import Memory, Server
from virtual_plc.memory import CellCapExceeded

ROOT = Path(__file__).resolve().parents[1]


def _release_notes():
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import release_notes
    finally:
        sys.path.pop(0)
    return release_notes


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


def test_every_release_version_has_a_curated_release_note_section():
    release_notes = _release_notes()
    version = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
                        re.M).group(1)
    notes = release_notes.extract(version, (ROOT / "docs" / "HANDOFF.md").read_text(encoding="utf-8"))
    assert notes.strip() and "release-note source" not in notes
    with pytest.raises(LookupError):
        release_notes.extract("99.99.99", (ROOT / "docs" / "HANDOFF.md").read_text(encoding="utf-8"))


@pytest.mark.skipif(not (ROOT / ".github").is_dir(), reason="repository-only check")
def test_release_workflow_publishes_the_curated_notes():
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "tools/release_notes.py" in text and "--notes-file" in text
    # Extraction fails closed in the build job, before anything is built or published.
    assert (text.index("tools/release_notes.py") < text.index("python -m build")
            < text.index("upload-artifact") < text.index("pypa/gh-action-pypi-publish"))
    publish = text[text.index("  publish:"):text.index("  github-release:")]
    assert "needs: build" in publish and "release-notes" not in publish
    # A release created beforehand (e.g. by hand) still gets the curated notes if empty.
    assert publish.count("name: release-distributions") == 1  # never pulls the notes into dist/
    assert text.count("name: release-notes") == 2  # uploaded once (build), downloaded once
    assert "path: release-notes/notes.md" in text[:text.index("  publish:")]
    attach = text[text.index("Attach distributions to release"):]
    empty_check = 'if [ -z "$(gh release view "$RELEASE_TAG" --json body --jq .body)" ]; then'
    assert empty_check in attach and attach.index(empty_check) < attach.index("gh release edit")
    assert attach.count("--notes-file release-notes/notes.md") == 2
    assert "--notes-file release-notes/notes.md --generate-notes" in attach


def test_release_notes_rewrite_relative_links_to_absolute_repo_urls():
    release_notes = _release_notes()
    text = ("## 2026-01-01 release 1.2.3 — release-note source\n\n"
            "See [B](BEHAVIOR.md#x), [R](../README.md), [abs](https://e.x/y) and [a](#top).\n\n## next\n")
    notes = release_notes.extract("1.2.3", text)
    base = "https://github.com/greatgc-flow/VirtualPLC/blob/v1.2.3/"  # pinned to the tag
    assert "[B](%sdocs/BEHAVIOR.md#x)" % base in notes
    assert "[R](%sREADME.md)" % base in notes
    assert "[abs](https://e.x/y)" in notes and "[a](#top)" in notes


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


def test_release_notes_ignore_headings_inside_code_fences_and_fix_root_links():
    rn = _release_notes()
    text = "\n".join([
        "## d release 2.0.0 — release-note source", "", "Intro [root](/README.md)", "",
        "```text", "## not a heading", "```", "", "after fence", "",
        "## 2026 release 1.0.0 — release-note source", "old", ""])
    notes = rn.extract("2.0.0", text)
    assert "after fence" in notes and "old" not in notes
    assert "[root](https://github.com/greatgc-flow/VirtualPLC/blob/v2.0.0/README.md)" in notes


HEAD = "## d release 1.0.0 \u2014 release-note source\r\n"


@pytest.mark.parametrize("body", ["a\n```\n## x\n", "a\n~~~\nb\n", "\n\n## next\n", ""])
def test_release_notes_fail_closed_on_unterminated_fence_or_empty_section(body):
    with pytest.raises(LookupError):
        _release_notes().extract("1.0.0", HEAD + body)


def test_release_notes_crlf_and_indented_tilde_fences():
    text = HEAD + "a\r\n  ~~~\r\n## x\r\n  ~~~\r\nb\r\n## next\r\nold\r\n"
    assert _release_notes().extract("1.0.0", text) == "a\n  ~~~\n## x\n  ~~~\nb\n"


def test_release_notes_fence_closes_only_on_same_char_and_length():
    text = HEAD + "a\n````\n```\n## x\n````\nb\n## next\n"
    assert _release_notes().extract("1.0.0", text) == "a\n````\n```\n## x\n````\nb\n"


def test_release_notes_leave_code_untouched_and_keep_link_titles():
    text = HEAD + 'see `f[i](x)` and [t](x.md "T")\n```\n[c](y.md)\n```\n## next\n'
    notes = _release_notes().extract("1.0.0", text)
    assert "`f[i](x)`" in notes and "[c](y.md)" in notes
    assert '[t](https://github.com/greatgc-flow/VirtualPLC/blob/v1.0.0/docs/x.md "T")' in notes


def test_release_notes_cli_exit_codes(tmp_path):
    def run(*args):
        return subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "release_notes.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"',
                        (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
    ok = run(version)  # default path: docs/HANDOFF.md next to tools/
    assert ok.returncode == 0 and ok.stdout.strip()
    missing = run("99.99.99")
    assert missing.returncode == 1 and missing.stdout == ""
    assert run().returncode == 2
    bad = tmp_path / "h.md"
    bad.write_bytes(b"\xff\xfe\x00broken")
    undecodable = run(version, str(bad))
    assert undecodable.returncode == 1 and "Traceback" not in undecodable.stderr
