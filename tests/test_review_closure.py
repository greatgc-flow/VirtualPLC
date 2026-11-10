"""Regression tests for the 2026-11-10 MECE closure review (docs/code/tests cross-checks)."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Workflow files are repository-only (not shipped in the sdist).
repo_only = pytest.mark.skipif(not (ROOT / ".github").is_dir(), reason="repository-only check")


def _slug(heading):
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def _anchors(path):
    return {_slug(m.group(1)) for m in re.finditer(r"^#{1,6}\s+(.+?)\s*$",
                                                   path.read_text(encoding="utf-8"), re.M)}


def _links(path):
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"```.*?```|~~~.*?~~~", "", text, flags=re.S)
    return re.findall(r"\]\(([^)\s]+)\)", text)


def test_readme_has_no_relative_links_because_it_is_the_pypi_description():
    bad = [t for t in _links(ROOT / "README.md") if not t.startswith(("http://", "https://", "#"))]
    assert not bad, "relative links break on PyPI: %s" % bad


def test_readme_in_page_anchors_resolve():
    readme = ROOT / "README.md"
    anchors = _anchors(readme)
    for target in _links(readme):
        if target.startswith("#"):
            assert target[1:] in anchors, target


@pytest.mark.parametrize("module", ["virtual_plc.oracle"])
def test_oracle_cli_rejects_abbreviated_options(module, tmp_path):
    observations = tmp_path / "o.json"
    observations.write_text("{}", encoding="utf-8")
    result = subprocess.run([sys.executable, "-I", "-m", module, "compare", str(observations),
                             "--rep", str(tmp_path / "r.json")], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


def test_manual_evidence_tool_rejects_abbreviated_options():
    result = subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "manual_revision_evidence.py"),
                             "--over"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


def test_guide_ethernet_units_are_spaced():
    from virtual_plc.__main__ import build_parser
    from virtual_plc import guide

    text = guide.render(build_parser(), "ethernet")
    assert "alive_retries=3 count" in text and "3count" not in text


def test_rncpu_reference_depends_on_the_owning_module():
    source = (ROOT / "virtual_plc" / "rncpu_reference.py").read_text(encoding="utf-8")
    assert "from .ethernet_reference import" in source
    assert "from .ethernet import" not in source


def test_manual_urls_use_the_canonical_download_host():
    for path in [ROOT / "virtual_plc" / "ethernet.py", ROOT / "docs" / "ETHERNET_MODEL_SETTINGS.md"]:
        assert "www.mitsubishielectric.com/dl/" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("encoding,prefix", [("utf-8-sig", b""), ("utf-16", b"")])
def test_oracle_compare_reads_bom_and_utf16_observation_files(tmp_path, encoding, prefix):
    """Windows PowerShell 5.1 `>` writes UTF-16 with BOM; `Set-Content utf8` writes a UTF-8 BOM."""
    template = subprocess.run([sys.executable, "-I", "-m", "virtual_plc.oracle", "template"],
                              cwd=ROOT, capture_output=True, text=True, check=True).stdout
    path = tmp_path / "observations.json"
    path.write_bytes(prefix + template.encode(encoding))
    result = subprocess.run([sys.executable, "-I", "-m", "virtual_plc.oracle", "compare", str(path)],
                            cwd=ROOT, capture_output=True, text=True)
    assert "codec can't decode" not in result.stderr and "BOM" not in result.stderr, result.stderr


def _github_links(text):
    # main and tag-pinned (vX.Y.Z) URLs are checked against the current tree: shallow CI
    # checkouts have no tags, and released sections must keep resolving anyway.
    base = "https://github.com/greatgc-flow/VirtualPLC/"
    for match in re.finditer(re.escape(base) + r"(?:blob|tree)/(?:main|v\d+\.\d+\.\d+)/([^)\s#]+)(?:#([^)\s]+))?", text):
        yield match.group(1), match.group(2)


@pytest.mark.parametrize("doc", sorted(p for p in ROOT.rglob("*.md")
                                       if not any(part.startswith(".") for part in p.relative_to(ROOT).parts))
                         + [ROOT / "llms.txt"], ids=lambda p: str(p.relative_to(ROOT)))
def test_every_markdown_link_and_repo_url_resolves_locally(doc):
    text = doc.read_text(encoding="utf-8")
    for target in _links(doc):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path_part, _, fragment = target.partition("#")
        resolved = (doc.parent / path_part).resolve()
        assert resolved.exists(), "%s -> %s" % (doc, target)
        if fragment and resolved.suffix == ".md":
            assert fragment in _anchors(resolved), "%s -> %s" % (doc, target)
    for path_part, fragment in _github_links(text):
        resolved = ROOT / path_part
        assert resolved.exists(), "%s -> %s" % (doc, path_part)
        if fragment and resolved.suffix == ".md":
            assert fragment in _anchors(resolved), "%s -> %s#%s" % (doc, path_part, fragment)


@repo_only
def test_ci_runs_sdist_tests_against_the_installed_package():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert 'sdist-venv/bin/python" -I -m pytest' in text


@repo_only
def test_release_tooling_is_pinned_and_shared_by_ci_and_release_workflows():
    pins = (ROOT / "requirements-release.txt").read_text(encoding="utf-8").split()
    assert {p.split("==")[0] for p in pins} == {"build", "twine"}
    assert all(re.fullmatch(r"[a-z]+==[0-9][0-9.]*", p) for p in pins)
    for workflow in ("ci.yml", "release.yml"):
        text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
        assert "-r requirements-release.txt" in text
        for line in text.splitlines():
            if "pip install" in line:
                assert not re.search(r"(build|twine)", line.replace("requirements-release.txt", "")), line
    assert "requirements-release.txt" in (ROOT / "MANIFEST.in").read_text(encoding="utf-8")


def test_sh081257_error_table_is_cited_at_its_printed_page():
    """C050H-C05DH sit on printed p.453 of SH-081257 (PDF page 455); p.452 ends at C040H."""
    for path in list((ROOT / "virtual_plc").glob("*.py")) + list((ROOT / "docs").rglob("*.md")):
        assert "p.452" not in path.read_text(encoding="utf-8"), path
