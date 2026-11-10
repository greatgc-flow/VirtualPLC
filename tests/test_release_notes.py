"""tools/release_notes.py: the HANDOFF release-note contract and the release workflow gate.

Contract (fail closed, exit 1): a `## <date> release X.Y.Z — release-note source`
section exists and is non-empty, has no code fences, and links only absolute
https:// URLs. Output is the body, UTF-8, LF line endings.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = (ROOT / "docs" / "HANDOFF.md").read_text(encoding="utf-8")
HEAD = "## 2026-01-01 release 1.0.0 — release-note source\n"


def _tool():
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import release_notes
    finally:
        sys.path.pop(0)
    return release_notes


def _run(*args):
    return subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "release_notes.py"), *args],
                          capture_output=True)


def _released_versions():
    return re.findall(r"^## \S+ release (\d+\.\d+\.\d+) \S+ release-note source", HANDOFF, re.M)


def test_handoff_has_a_valid_section_for_every_release_since_0_7_0_and_the_current_version():
    versions = _released_versions()
    current = re.search(r'^version = "([^"]+)"',
                        (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
    assert {"0.7.0", "0.8.0", "0.9.0", current} <= set(versions)
    for version in versions:  # every section satisfies the contract
        assert _tool().extract(version, HANDOFF).strip()


def test_body_runs_to_the_next_level_two_heading_and_normalises_crlf():
    text = (HEAD + "a\n### sub stays\n##x stays\n- b `c`\n## next\nold\n").replace("\n", "\r\n")
    assert _tool().extract("1.0.0", text) == "a\n### sub stays\n##x stays\n- b `c`\n"


@pytest.mark.parametrize("text", [
    "## d release 1.0.0\nb\n",                                   # heading without the suffix
    "## d release 1x0x0 — release-note source\nb\n",          # version is matched literally
    "## d release 1.0.0.1 — release-note source\nb\n",        # no prefix match
    HEAD + "\n\n## next\nold\n",                                  # empty section
    HEAD + "a\n```\ncode\n```\n",                                 # backtick fence
    HEAD + "a\n  ~~~\ncode\n  ~~~\n",                             # tilde fence, indented
    HEAD + "see [B](BEHAVIOR.md#x)\n",                            # relative link
    HEAD + "see [H](http://example.com)\n",                       # non-https link
    HEAD + "see [R](/README.md)\n",                               # root-relative link
    HEAD + "see [B][b]\n\n[b]: BEHAVIOR.md\n",                    # reference-style link
    HEAD + "see <http://example.com>\n",                          # non-https autolink
    HEAD + 'see <a href="BEHAVIOR.md">B</a>\n',                   # raw HTML link
    HEAD + "see <https://example.com>\n",                         # https autolink is <...> too
    HEAD + "see [b]\n\n[b]: rel.md\n",                            # reference definition alone
    HEAD + "see [B][b]\n",                                        # full reference alone
    HEAD + "x ``` [l](rel.md) `\n",                               # unequal backtick runs
])
def test_contract_violations_fail_closed(text):
    with pytest.raises(LookupError):
        _tool().extract("1.0.0", text)


def test_https_links_pass_through_unchanged():
    link = "[B](https://github.com/greatgc-flow/VirtualPLC/blob/v1.0.0/docs/BEHAVIOR.md#x)"
    assert _tool().extract("1.0.0", HEAD + "see " + link + "\n") == "see " + link + "\n"


def test_cli_writes_utf8_bytes_whatever_the_console_code_page(tmp_path):
    handoff = tmp_path / "HANDOFF.md"
    handoff.write_text(HEAD + "dash — arrow →\n", encoding="utf-8")
    result = _run("1.0.0", str(handoff))
    assert result.returncode == 0, result.stderr
    assert result.stdout == "dash — arrow →\n".encode("utf-8")


def test_cli_exit_codes_and_clean_errors(tmp_path):
    assert _run(_released_versions()[0]).returncode == 0  # default path: docs/HANDOFF.md
    undecodable = tmp_path / "bad.md"
    undecodable.write_bytes(b"\xff\xfe\x00broken")
    for args in (("99.99.99",), ("1.0.0", str(tmp_path / "missing.md")), ("1.0.0", str(undecodable))):
        result = _run(*args)
        assert result.returncode == 1 and result.stdout == b"" and b"Traceback" not in result.stderr
    assert _run().returncode == 2 and _run("1", "2", "3").returncode == 2


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


@pytest.mark.skipif(not (ROOT / ".github").is_dir(), reason="repository-only check")
def test_release_workflow_exact_extract_step_and_job_wiring():
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n")
    assert ("          mkdir -p release-notes\n"
            '          python tools/release_notes.py "${RELEASE_TAG#v}" docs/HANDOFF.md'
            " > release-notes/notes.md\n") in text
    assert "continue-on-error" not in text
    assert "needs: [build, publish]" in text
    step = text[text.index("- name: Extract curated release notes"):text.index("python tools/release_notes.py")]
    assert "if:" not in step  # the gate cannot be switched off
    github_release = text[text.index("  github-release:"):]
    assert "name: release-notes\n          path: release-notes\n" in github_release
