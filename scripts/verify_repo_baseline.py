"""Fail-closed verification of the byte-exact M3 source baseline.

Run from repository root:
    python scripts/verify_repo_baseline.py
This does not claim runtime compatibility or release certification.
"""
from __future__ import annotations
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/provenance/M3_SOURCE_MANIFEST.json"

def verify():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = manifest["sha256"]
    git_blobs = manifest["git_blobs"]
    issues = []
    if len(expected) != 74 or set(expected) != set(git_blobs):
        issues.append("source manifest inventory mismatch (expected 74)")
    for path, digest in expected.items():
        item = pathlib.PurePosixPath(path)
        if item.is_absolute() or ".." in item.parts:
            issues.append(f"unsafe path {path}")
            continue
        actual = ROOT.joinpath(*item.parts)
        if not actual.is_file() or actual.is_symlink():
            issues.append(f"missing or symlink source {path}")
            continue
        content = actual.read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()
        gitsha = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\x00" + content).hexdigest()
        if sha256 != digest or gitsha != git_blobs[path]:
            issues.append(f"content mismatch {path}")
    catalog = ROOT / "suite/catalog/test_cases.jsonl"
    if catalog.is_file():
        try:
            cases = [json.loads(s) for s in catalog.read_text(encoding="utf-8").splitlines() if s.strip()]
            if len(cases) != 208 or sum(c["phase"] == "P0" for c in cases) != 199:
                issues.append("208/199 catalogue cardinality mismatch")
            if len({c["id"] for c in cases}) != len(cases):
                issues.append("duplicate CASE-ID")
        except (ValueError, KeyError) as e:
            issues.append(f"catalog parse error: {e}")
    print(json.dumps({"source_files": len(expected), "case_total": 208, "P0": 199,
        "status": "PASS" if not issues else "FAIL", "issues": issues}, ensure_ascii=False))
    return 0 if not issues else 1

if __name__ == "__main__":
    sys.exit(verify())
