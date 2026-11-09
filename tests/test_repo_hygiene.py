"""Packaging/CI hygiene guards (improvement ballot B2: I3, I4, I5, I13, I14, M1, F12).

Text-level checks only: no network, no build, stdlib only.
"""

import ast
import fnmatch
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
# Workflow files are repository-only (not shipped in the sdist); the sdist CI run skips these.
repo_only = pytest.mark.skipif(not (ROOT / ".github").is_dir(), reason="repository-only check")


def _pyproject_version():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version = "([^"]+)"', text, re.M).group(1)


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
@repo_only
def test_third_party_actions_are_pinned_to_commit_shas(workflow):
    """I4: every `uses:` is owner/repo@<40-hex SHA> with a version comment."""
    refs = re.findall(r"uses:\s*(\S+)(.*)", workflow.read_text(encoding="utf-8"))
    assert refs
    for ref, rest in refs:
        assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", ref), ref
        assert re.search(r"#\s*v\d", rest), f"{ref} needs a '# vX' comment"


@repo_only
def test_ci_matrix_matches_python_classifiers():
    """I5: CI tests exactly the Python versions the package classifies."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    matrix = set(re.findall(r"'(3\.\d+)'", re.search(r"python: \[([^\]]*)\]", ci).group(1)))
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    classified = set(re.findall(r"Programming Language :: Python :: (3\.\d+)", pyproject))
    assert matrix == classified
    assert "3.14" in matrix
    minimum = re.search(r'requires-python = ">=(3\.\d+)"', pyproject).group(1)
    assert min(matrix, key=lambda v: int(v.split(".")[1])) == minimum


@repo_only
def test_ci_does_not_cancel_main_runs():
    """I13: only pull-request runs cancel; main runs get one group per SHA."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "group: ci-${{ github.event_name == 'pull_request' && github.ref || github.sha }}" in ci
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in ci


@repo_only
def test_ci_has_one_macos_job():
    """F12: a single macOS job (not required until green on main)."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "macos-latest" in ci


@repo_only
def test_release_requires_green_main_ci_for_tagged_sha():
    """M1: release fails closed unless ci.yml push run on main succeeded for the tag SHA."""
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "actions: read" in release
    for needle in ("ci.yml", "event=push", "branch=main", "head_sha", "success"):
        assert needle in release, needle


def test_version_fallback_literal_matches_pyproject():
    """I14: the source-tree fallback __version__ is bumped with pyproject."""
    tree = ast.parse((ROOT / "virtual_plc" / "__init__.py").read_text(encoding="utf-8"))
    fallbacks = [node.body[0].value.value for node in ast.walk(tree)
                 if isinstance(node, ast.ExceptHandler)
                 and isinstance(node.body[0], ast.Assign)
                 and node.body[0].targets[0].id == "__version__"]
    assert fallbacks == [_pyproject_version()]


def _manifest_rules():
    rules = []
    for line in (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts:
            rules.append((parts[0], parts[1:]))
    return rules


def _shipped(path):
    """Approximate setuptools MANIFEST.in semantics for include/graft/global-exclude."""
    rel = path.as_posix()
    shipped = rel.startswith("virtual_plc/") or rel in ("pyproject.toml", "setup.cfg", "setup.py")
    for command, args in _manifest_rules():
        if command == "include" and any(fnmatch.fnmatch(rel, pattern) for pattern in args):
            shipped = True
        elif command == "graft" and any(rel.startswith(directory.rstrip("/") + "/") for directory in args):
            shipped = True
        elif command == "global-exclude" and any(fnmatch.fnmatch(Path(rel).name, pattern) or pattern in rel.split("/")
                                                 for pattern in args):
            shipped = False
    return shipped


def test_sdist_ships_every_repo_file_the_tests_reference():
    """I3: bundled tests must run from an extracted sdist (examples/, tools/, ...)."""
    referenced = set()
    for test in (ROOT / "tests").glob("*.py"):
        text = test.read_text(encoding="utf-8")
        for match in re.findall(r'["\']((?:examples|tools|docs|\.github)/[\w./-]+\.\w+)["\']', text):
            referenced.add(match)
        for directory, name in re.findall(r'ROOT\s*/\s*"(examples|tools)"\s*/\s*"([\w.-]+)"', text):
            referenced.add(f"{directory}/{name}")
    for top in ("examples", "tools"):
        for path in (ROOT / top).rglob("*.py"):
            referenced.add(path.relative_to(ROOT).as_posix())
    missing = sorted(rel for rel in referenced if (ROOT / rel).exists() and not _shipped(Path(rel)))
    assert not missing, f"MANIFEST.in does not ship: {missing}"
