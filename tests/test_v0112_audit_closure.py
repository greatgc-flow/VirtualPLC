"""Whole-product audit of v0.11.2: three minor findings closed in 0.11.3."""

from pathlib import Path
import re

import pytest

from virtual_plc import Server


ROOT = Path(__file__).resolve().parents[1]
# Active docs only: docs/research/ and docs/handoff/ are dated snapshots, and
# HANDOFF.md release-note sections are history by design.
ACTIVE_DOCS = [ROOT / "README.md", ROOT / "llms.txt", ROOT / "AGENTS.md"] + [
    path for path in sorted((ROOT / "docs").glob("*.md")) if path.name != "HANDOFF.md"]
# Closed issues an active doc may cite only as delivered work ("Resolved: ... #95").
RESOLVED_FEATURES = {79, 95}
# Closed issue cited as implementation history, marked "(closed)" in that file.
HISTORY = {("docs/ETHERNET_MODEL_SETTINGS.md", 14)}
# "#N" that is not a PR, a vendor FAQ number or an HTML entity.
ISSUE_REF = re.compile(r"(?<![&\w])(?<!PR )(?<!FAQ )#(\d+)\b|/issues/(\d+)\b")


def _open_issues():
    line = next(text for text in (ROOT / "docs" / "HANDOFF.md").read_text(
        encoding="utf-8").splitlines() if text.startswith("- Open issues:"))
    return {int(number) for number in re.findall(r"#(\d+)", line)}


# F1: active docs must not name closed issues (#14, #22) as open trackers.
def test_active_docs_cite_only_open_or_resolved_feature_issues():
    allowed = _open_issues() | RESOLVED_FEATURES
    stray = sorted(
        "{}: #{}".format(name, number)
        for path in ACTIVE_DOCS
        for name in [path.relative_to(ROOT).as_posix()]
        for match in ISSUE_REF.finditer(path.read_text(encoding="utf-8"))
        for number in [int(match.group(1) or match.group(2))]
        if number not in allowed and (name, number) not in HISTORY)
    assert stray == []
    for name, number in HISTORY:
        assert "#{}](".format(number) in (ROOT / name).read_text(encoding="utf-8")
        assert "(closed)" in (ROOT / name).read_text(encoding="utf-8")


def test_issue_reference_scanner_catches_a_closed_tracker():
    text = "Tracked follow-ups: #2 and [#14](https://github.com/x/y/issues/14). PR #45, FAQ #39316, &#160;"
    numbers = [int(m.group(1) or m.group(2)) for m in ISSUE_REF.finditer(text)]
    assert numbers == [2, 14, 14]
    assert 14 not in _open_issues() | RESOLVED_FEATURES


# F2: the session record lists the 0.11.2 release PR.
def test_session_record_lists_release_pr_103():
    record = (ROOT / "docs" / "handoff" / "SESSION_20261110_MECE_REVIEW_AND_RELEASES.md")
    assert "#103 (0.11.2)" in record.read_text(encoding="utf-8")


# F3: "bad values raise ValueError before binding" also covers a non-string host.
@pytest.mark.parametrize("host", [5, None, b"127.0.0.1", ("127.0.0.1",)])
@pytest.mark.parametrize("allow_nonlocal", [False, True])
def test_non_string_host_raises_value_error_before_binding(host, allow_nonlocal):
    with pytest.raises(ValueError, match="host must be a string"):
        Server(host=host, allow_nonlocal=allow_nonlocal, idle_timeout=1)
