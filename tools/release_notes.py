"""Print the curated release notes for one version from docs/HANDOFF.md.

Each release has a section headed ``## <date> release X.Y.Z — release-note source``.
The release workflow publishes its body (above the auto-generated PR list) and fails
closed before building or publishing to PyPI when the section is missing.

    python tools/release_notes.py 0.9.0 [docs/HANDOFF.md] > notes.md
"""

import posixpath
import re
import sys
from pathlib import Path

REPO_BLOB = "https://github.com/greatgc-flow/VirtualPLC/blob/v{version}/"

HEADING = r"^## [^\n]*\brelease {version} \S+ release-note source[ \t]*\r?$"
FENCE = re.compile(r"^\s*(```|~~~)")


def extract(version, handoff_text):
    """Return the section body for ``version``; raise LookupError if absent or empty."""
    pattern = re.compile(HEADING.format(version=re.escape(version)), re.M)
    match = pattern.search(handoff_text)
    if match is None:
        raise LookupError("no 'release %s — release-note source' section in HANDOFF" % version)
    body_lines, in_fence = [], False
    for line in handoff_text[match.end():].splitlines()[1:]:
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and line.startswith("## "):
            break  # next section; a '## ' inside a code fence is content
        body_lines.append(line)
    if in_fence:
        raise LookupError("release %s note section has an unterminated code fence" % version)
    body = "\n".join(body_lines).strip()
    if not body:
        raise LookupError("release %s note section is empty" % version)
    return _absolute_links(body, REPO_BLOB.format(version=version)) + "\n"


def _absolute_links(text, base):
    """HANDOFF lives in docs/: make its relative links work on the release page.

    Links are pinned to the release tag so anchors keep working after docs move.
    """
    def fix(match):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:", "#")):
            return match.group(0)
        if target.startswith("/"):  # repository-root path
            path = posixpath.normpath(target.lstrip("/"))
        else:
            path = posixpath.normpath(posixpath.join("docs", target))
        return "](" + base + path + ")"
    return re.sub(r"\]\(([^)\s]+)\)", fix, text)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not 1 <= len(argv) <= 2:
        print("usage: release_notes.py VERSION [HANDOFF.md]", file=sys.stderr)
        return 2
    path = Path(argv[1]) if len(argv) == 2 else Path(__file__).resolve().parents[1] / "docs" / "HANDOFF.md"
    try:
        sys.stdout.write(extract(argv[0], path.read_text(encoding="utf-8")))
    except (LookupError, OSError) as error:
        print("release notes: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
