"""Print the curated release notes for one version from docs/HANDOFF.md.

Each release has a section headed ``## <date> release X.Y.Z — release-note source``.
The release workflow publishes its body (above the auto-generated PR list) and fails
closed before publishing to PyPI when the section is missing.

    python tools/release_notes.py 0.9.0 [docs/HANDOFF.md] > notes.md
"""

import posixpath
import re
import sys
from pathlib import Path

REPO_BLOB = "https://github.com/greatgc-flow/VirtualPLC/blob/main/"

HEADING = r"^## [^\n]*\brelease {version} \S+ release-note source[ \t]*\r?$"


def extract(version, handoff_text):
    """Return the section body for ``version``; raise LookupError if absent or empty."""
    pattern = re.compile(HEADING.format(version=re.escape(version)), re.M)
    match = pattern.search(handoff_text)
    if match is None:
        raise LookupError("no 'release %s — release-note source' section in HANDOFF" % version)
    rest = handoff_text[match.end():]
    following = re.search(r"^## ", rest, re.M)
    body = (rest[:following.start()] if following else rest).strip()
    if not body:
        raise LookupError("release %s note section is empty" % version)
    return _absolute_links(body) + "\n"


def _absolute_links(text):
    """HANDOFF lives in docs/: make its relative Markdown links work on the release page."""
    def fix(match):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:", "#")):
            return match.group(0)
        return "](" + REPO_BLOB + posixpath.normpath(posixpath.join("docs", target)) + ")"
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
