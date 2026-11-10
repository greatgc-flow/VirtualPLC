"""Print the curated release notes for one version from docs/HANDOFF.md.

Each release has a section headed ``## <date> release X.Y.Z — release-note source``.
Its body (up to the next ATX ``## `` heading) is published unchanged at the top
of the GitHub release notes. The format is deliberately restricted so nothing
needs translating:

* plain Markdown text, bullets and inline code; no code fences;
* links only as inline ``[text](https://...)``; reference-style links,
  ``<...>`` autolinks/HTML and non-https targets are rejected.

Anything else fails closed (exit 1) so the release stops before building.

    python tools/release_notes.py 0.9.1 [docs/HANDOFF.md] > notes.md
"""

import re
import sys
from pathlib import Path

HEADING = r"^## [^\n]*\brelease {version} \S+ release-note source[ \t]*$"
FENCE = re.compile(r"^\s*(```|~~~)", re.M)
NON_HTTPS_LINK = re.compile(r"\]\((?!https://)")
OTHER_LINK = re.compile(r"^ {0,3}\[[^\]]+\]:|\]\[|<[A-Za-z/!]", re.M)


def extract(version, handoff_text):
    """Return the validated section body for ``version``; raise LookupError otherwise."""
    text = handoff_text.replace("\r\n", "\n")
    match = re.search(HEADING.format(version=re.escape(version)), text, re.M)
    if match is None:
        raise LookupError("no 'release %s — release-note source' section in HANDOFF" % version)
    rest = text[match.end():]
    following = re.search(r"^## ", rest, re.M)
    body = (rest[:following.start()] if following else rest).strip()
    if not body:
        raise LookupError("release %s note section is empty" % version)
    if FENCE.search(body):
        raise LookupError("release %s notes must not contain code fences" % version)
    if NON_HTTPS_LINK.search(body) or OTHER_LINK.search(body):
        raise LookupError("release %s notes may only use inline [text](https://...) links" % version)
    return body + "\n"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not 1 <= len(argv) <= 2:
        print("usage: release_notes.py VERSION [HANDOFF.md]", file=sys.stderr)
        return 2
    path = Path(argv[1]) if len(argv) == 2 else Path(__file__).resolve().parents[1] / "docs" / "HANDOFF.md"
    try:
        notes = extract(argv[0], path.read_text(encoding="utf-8"))
    except (LookupError, OSError, UnicodeDecodeError) as error:
        print("release notes: %s" % error, file=sys.stderr)
        return 1
    sys.stdout.buffer.write(notes.encode("utf-8"))  # UTF-8 whatever the console code page
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
