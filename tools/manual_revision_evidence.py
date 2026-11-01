"""Source-scoped offline evidence candidates for Mitsubishi manual revisions.

Run only with locally obtained official original PDFs. Needs an optional
local Poppler/Xpdf pdftotext executable; the VirtualPLC runtime remains
stdlib-only, and this utility never accesses any network or PLC.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


PAIRS = {
    "ethernet": {
        "manual": "081257ENG",
        "older": "AD", "newer": "AG",
        "topics": {
            "r04cpu": r"\bR04CPU\b",
            "external_device_configuration": r"External\s+Device\s+Configuration",
            "connection_number": r"Connection\s+(?:No\.?|Number)",
            "plc_port": r"(?:PLC|Own)\s+Port\s+(?:No\.?|Number)",
            "data_communication_timer": r"(?:Data\s+Communication\s+Timer|Change/Set\s+Timer\s+Value|\bA038H\b)",
            "system_port": r"System\s+Port",
        },
    },
    "cpu": {
        "manual": "082488ENG",
        "older": "E", "newer": "I",
        "topics": {
            "r04cpu": r"\bR04CPU\b",
            "opening_method": r"Opening\s+Method",
            "a031h": r"\bA031H\b",
            "remote_stop": r"Remote\s+STOP",
            "remote_run": r"Remote\s+RUN",
        },
    },
}


def fingerprint_pdf(path, max_bytes=100 * 1024 * 1024):
    """Hash local bytes, reject directories/empty/non-PDF and excessive size.

    Header check is only file-format screening, not publisher authentication.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError("PDF path must be an existing regular file: {}".format(path))
    size = path.stat().st_size
    if size < 5 or size > max_bytes:
        raise ValueError("PDF size must be within 5..{} bytes: {}".format(max_bytes, path))
    digest = hashlib.sha256()
    with path.open("rb") as source:
        if source.read(5) != b"%PDF-":
            raise ValueError("PDF signature/header not found: {}".format(path))
        source.seek(0)
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return {"file": str(path), "bytes": size, "sha256": digest.hexdigest()}


def extract_pdf_text(path, executable="pdftotext"):
    """Extract local UTF-8 text with page formfeeds; never use shell/network."""
    args = [executable, "-layout", "-enc", "UTF-8", str(path), "-"]
    try:
        result = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=180, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("pdftotext unavailable or timed out: {}".format(exc)) from exc
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace")[:240]
        raise ValueError("pdftotext exited {}: {}".format(result.returncode, message))
    try:
        text = result.stdout.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("pdftotext did not return UTF-8") from exc
    if not text.strip():
        raise ValueError("pdftotext output is empty; manual clause review blocked")
    return text


def split_pages(text):
    """Keep empty PDF pages; 1-based page indices are PDF indices, not print."""
    pages = text.split("\f")
    if len(pages) > 1 and not pages[-1].strip():
        pages.pop()
    return pages


def find_topics(pages, kind, max_hits=12):
    """Generate bounded candidates; TOC hits may be false positives."""
    if kind not in PAIRS or type(max_hits) is not int or max_hits < 1:
        raise ValueError("unsupported manual family or max_hits")
    result = {}
    for name, pattern in PAIRS[kind]["topics"].items():
        expr = re.compile(pattern, flags=re.IGNORECASE)
        number = 0
        found_pages = []
        examples = []
        for index, page in enumerate(pages, 1):
            for match in expr.finditer(page):
                number += 1
                if index not in found_pages and len(found_pages) < max_hits:
                    found_pages.append(index)
                if len(examples) < max_hits:
                    region = page[max(0, match.start() - 50):match.end() + 100]
                    examples.append(re.sub(r"\s+", " ", region).strip()[:180])
        result[name] = {
            "pages": found_pages,
            "occurrences": number,
            "examples": examples,
        }
    return result


def _edition_candidate(pages, manual, edition):
    """Weak front-matter hint only; history/cover content needs human review."""
    pattern = r"SH(?:\(NA\))?[\s-]*{}[\s-]*{}\b".format(
        re.escape(manual), re.escape(edition),
    )
    return re.search(pattern, "\n".join(pages[:8]), re.IGNORECASE) is not None


def generate_report(pairs, extract=None, max_hits=12, executable="pdftotext"):
    """Inspect provided source pairs; NEVER infer clause/physical equivalence."""
    if type(pairs) is not dict or not pairs or set(pairs) - set(PAIRS):
        raise ValueError("provide at least one known complete edition pair")
    if type(max_hits) is not int or not 1 <= max_hits <= 30:
        raise ValueError("max_hits must be integer 1..30")
    if extract is None:
        def extract(path):
            return extract_pdf_text(path, executable=executable)

    pair_reports = {}
    # A source hash must identify exactly one edition role across the report.
    # Different filenames are not independent sources when their bytes match.
    seen_sources = {}
    source_fingerprints = []
    for kind in sorted(pairs):
        paths = pairs[kind]
        if type(paths) is not tuple or len(paths) != 2 or any(p is None for p in paths):
            raise ValueError("{} requires (older PDF, newer PDF)".format(kind))
        spec = PAIRS[kind]
        sources, scanned = {}, {}
        for label, raw_path in zip(("older", "newer"), paths):
            path = Path(raw_path)
            metadata = fingerprint_pdf(path)
            digest = metadata["sha256"]
            role = "{}/{}".format(kind, label)
            if digest in seen_sources:
                raise ValueError(
                    "duplicate PDF bytes for {} and {}; each revision needs "
                    "independent source evidence".format(seen_sources[digest], role)
                )
            seen_sources[digest] = role

            text = extract(path)
            # The digest in the report must identify the bytes from which
            # text was extracted. Local PDFs may be replaced during review.
            verified = fingerprint_pdf(path)
            if (metadata["sha256"] != verified["sha256"] or
                    metadata["bytes"] != verified["bytes"]):
                raise ValueError(
                    "PDF changed during extraction: {}; rerun on stable "
                    "originals".format(path)
                )
            if type(text) is not str or not text.strip():
                raise ValueError("extracted manual text is absent: {}".format(path))
            pages = split_pages(text)
            revision = spec[label]
            metadata.update({
                "declared_manual": "SH-" + spec["manual"],
                "declared_edition": revision,
                "pdf_page_count": len(pages),
                "front_matter_edition_candidate": _edition_candidate(
                    pages, spec["manual"], revision),
                "identity_authentication": "NOT_VERIFIED",
            })
            sources[label] = metadata
            scanned[label] = find_topics(pages, kind, max_hits=max_hits)
            source_fingerprints.append((path, metadata))

        topics = {}
        for name in spec["topics"]:
            older = scanned["older"][name]
            newer = scanned["newer"][name]
            topics[name] = {
                "older_pages": older["pages"],
                "newer_pages": newer["pages"],
                "older_occurrences": older["occurrences"],
                "newer_occurrences": newer["occurrences"],
                "older_examples": older["examples"],
                "newer_examples": newer["examples"],
                "hint": ("MATCH_COUNT_CHANGED" if older["occurrences"] !=
                         newer["occurrences"] else "CANDIDATE_PAGES_ONLY"),
            }
        pair_reports[kind] = {
            "manual_revision_equivalence": "NOT_VERIFIED",
            "older": sources["older"], "newer": sources["newer"],
            "topics": topics,
            "review_warning": (
                "PDF-page and bounded text hints include TOC/duplicate hits; "
                "printed page numbers and clause equivalence require human review."
            ),
        }

    # Later extractions can replace sources scanned earlier. Check every
    # original once more after the entire multi-edition scan completes.
    for path, baseline in source_fingerprints:
        latest = fingerprint_pdf(path)
        if (latest["sha256"] != baseline["sha256"] or
                latest["bytes"] != baseline["bytes"]):
            raise ValueError(
                "PDF changed before final report: {}; rerun on stable "
                "originals".format(path)
            )

    return {
        "status": "SOURCE_CLAUSE_REVIEW_REQUIRED",
        "manual_revision_equivalence": "NOT_VERIFIED",
        "physical_hardware_certified": False,
        "simulator_network_affected": False,
        "pdf_bytes_embedded": False,
        "pairs": pair_reports,
        "next_action": (
            "Verify manufacturer identity and each specific AD/AG or E/I "
            "clause/page manually; no automatic promotion of vendor SSOT."
        ),
    }


def write_report_atomic(output, payload, overwrite=False):
    """Publish complete JSON or leave the previous report untouched.

    Staging is in the destination directory. With --overwrite, os.replace
    atomically replaces the destination. Without it, os.link atomically
    claims an absent name and refuses races with another writer.
    Unsupported hard-link filesystems fail closed; no partial JSON is
    published. fsync flushes staging data, not the parent directory.
    """
    output = Path(output)
    if output.exists() and not overwrite:
        raise ValueError("output already exists; pass --overwrite explicitly")
    staging = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n",
                prefix="." + output.name + ".", suffix=".tmp",
                dir=str(output.parent), delete=False) as stream:
            staging = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(staging, output)
        else:
            try:
                os.link(staging, output)
            except FileExistsError as exc:
                raise ValueError(
                    "output already exists; pass --overwrite explicitly"
                ) from exc
    finally:
        if staging is not None and os.path.exists(staging):
            os.unlink(staging)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline Mitsubishi manual PDF evidence; always NOT_VERIFIED."
    )
    for option in ("ethernet-ad", "ethernet-ag", "cpu-e", "cpu-i"):
        parser.add_argument("--" + option, metavar="PDF")
    parser.add_argument("--pdftotext", default="pdftotext",
                        help="local Poppler/Xpdf executable (no downloading)")
    parser.add_argument("--max-hits", type=int, default=12)
    parser.add_argument("--output", help="write same JSON printed to stdout")
    parser.add_argument("--overwrite", action="store_true",
                        help="explicitly replace an existing local JSON report")
    args = parser.parse_args(argv)

    pairs = {}
    for kind, a, b in (("ethernet", args.ethernet_ad, args.ethernet_ag),
                       ("cpu", args.cpu_e, args.cpu_i)):
        if bool(a) != bool(b):
            parser.error("{} requires BOTH older and newer PDF".format(kind))
        if a and b:
            pairs[kind] = (Path(a), Path(b))
    if not pairs:
        parser.error("supply at least one complete manual PDF edition pair")
    try:
        report = generate_report(pairs, max_hits=args.max_hits,
                                 executable=args.pdftotext)
        payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.output:
            output = Path(args.output)
            if any(output.resolve() == p.resolve() for pair in pairs.values() for p in pair):
                raise ValueError("output must not overwrite a source PDF")
            write_report_atomic(output, payload, overwrite=args.overwrite)
        sys.stdout.write(payload)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
