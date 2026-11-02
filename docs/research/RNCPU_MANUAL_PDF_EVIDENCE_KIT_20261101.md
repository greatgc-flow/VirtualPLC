# Offline R04CPU manufacturer PDF revision evidence kit

As-of 2026-11-01; [tracking issue #14](https://github.com/greatgc-flow/VirtualPLC/issues/14).
**The actual AD↔AG and E↔I manual clauses are NOT_VERIFIED.**
The script below prepares an auditable review package when authentic
manufacturer PDF originals are available *locally*. No PDFs or verbatim
manual text are committed; this is a developer-only utility, not part of
the installed VirtualPLC wheel and not part of a plant-side workflow.

## Official revision identity and current blocker

| Document family | Compared editions | Current vendor listed revision | Previously sourced pages |
| --- | --- | --- | --- |
| SH-081257ENG, Ethernet Application | AD ↔ AG | AG, 2026-10 | AD printed 324–326, 329–330, 396–397, Appendix 10 554 |
| SH-082488ENG, CPU Module | E ↔ I | I, 2026-08 | E printed 3, 684–685 |

Manufacturer's [official R04CPU manual download listing](https://www.mitsubishielectric.com/fa/products/faspec/download.page?category=ex&formNm=RnCPU_R04CPU_3322&id=spec&kisyu=%2Fplcr&lang=2)
explicitly lists AG (19.23 MB) and I (18.39 MB).
It **does not** prove the relevant text is unchanged from AD/E.
Attempting to fetch the official binary PDFs from the current execution
environment hit an inaccessible AG URL and source size/DNS restrictions;
the actual PDF pages and their SHA-256 remain **NOT_OBTAINED** here.
Never use filename or a published-revision listing alone as document
authenticity or vendor-clause equivalence.

## Run on a PC holding authentic originals

1. From the **official manufacturer site**, obtain the four exact PDF
   editions: Ethernet AD + AG, CPU E + I. Preserve their original files,
   note the source URL/date locally and do not upload them to this repo.
   The filenames below are *local examples*, not verified download URLs.
2. Have a trusted local Poppler/Xpdf `pdftotext` executable installed
   (or on `PATH`). **No network access is performed by the script**.
3. From the cloned VirtualPLC repository, run in CMD or PowerShell.
   This single-line example works without modern PowerShell syntax:

```cmd
py -3.11 tools\manual_revision_evidence.py --ethernet-ad "C:\Manuals\SH-081257ENG-AD.pdf" --ethernet-ag "C:\Manuals\SH-081257ENG-AG.pdf" --cpu-e "C:\Manuals\SH-082488ENG-E.pdf" --cpu-i "C:\Manuals\SH-082488ENG-I.pdf" --output "C:\Manuals\R04CPU_evidence.json"
```

If `pdftotext.exe` is not on PATH, specify its local absolute path with
`--pdftotext "C:\Portable\poppler\Library\bin\pdftotext.exe"`.
Only one complete pair may be supplied (omit both flags for the other
family). `--max-hits 12` (default) controls bounded page candidates;
`--overwrite` must be explicit before replacing an existing report.
The JSON written to `--output` is exactly the JSON printed to stdout.

**Whole-pack input preflight (PR #46):** Before calling `pdftotext`,
the tool validates both edition roles for every supplied family, screens
headers and file sizes, and rejects duplicate PDF SHA-256 even across
families. If a later source is missing, malformed or byte-identical, no
extractor runs at all. This avoids unnecessary processing of known-bad
evidence packs. The previously documented post-extraction and final
source rechecks remain; this is not protection from every filesystem race
or proof of an official manual.

**Output file integrity (PR #44):** The CLI stages JSON in the output
directory, flushes/fsyncs it, then atomically publishes a complete report.
Existing output is replaced only with `--overwrite`, preserving the old
report if publication fails. Without `--overwrite`, exclusive hard-link
creation refuses a concurrent writer's destination. On filesystems
without hard-link support, publication fails safely; it does not fall
back to a partial write. Temporary staging files are cleaned on errors.
This is atomic visibility on supported filesystems, not power-loss
durability (parent directory not fsynced), proof of manufacturer PDF
authenticity or evidence that AD/AG and E/I clauses are equal.

The script refuses to overwrite any supplied source PDF.

Example on POSIX/Linux:

```sh
python tools/manual_revision_evidence.py --cpu-e /manuals/sh082488enge.pdf --cpu-i /manuals/sh082488engi.pdf --output /manuals/cpu_review.json
```

## What the JSON means (and cannot mean)

- Each supplied PDF is screened for the `%PDF-` file signature,
  file length (max 100 MiB), and **SHA-256 over its original bytes**.
  The header is not a cryptographic certificate or confirmation that
  the manufacturer supplied the PDF.
- Source-integrity gate ([PR #43](https://github.com/greatgc-flow/VirtualPLC/pull/43)):
  the same PDF **bytes** cannot fill multiple edition roles, even under
  different filenames. Each input is SHA-256 fingerprinted again
  immediately after local text extraction; if content or length changes,
  the entire report fails closed. Keep manufacturer originals stable
  (copy to a read-only workspace before running). This detects common
  duplicate/mid-extraction source drift, **not** cryptographic publisher
  authentication or all concurrent filesystem races.
- Full-pack source-integrity gate ([PR #45](https://github.com/greatgc-flow/VirtualPLC/pull/45)):
  after all supplied PDF editions and manual families are processed,
  each original is SHA-256/size checked again. A later extraction
  changing a previously scanned source invalidates the entire report.
  This supplements immediate post-extraction checks; it cannot
  establish genuine publisher identity, prevent all rapid replace-and-
  restore races, or guarantee that originals remain unchanged after
  final verification.
- `front_matter_edition_candidate` searches the first eight extracted
  PDF pages for the expected document/edition label. It is a **weak
  candidate**, not authentication (edition history may include older
  identifiers; extracted text can be incomplete).
- `topics` reports the first bounded matching **PDF page indices**
  (1-based, not printed page labels), total term occurrences and short
  snippets (up to 180 characters each). A match might come from a
  TOC, duplicated heading, appendix or irrelevant model: inspect
  the actual text/table/screenshots for the **R04CPU CPU built-in
  Ethernet scope**.
- `MATCH_COUNT_CHANGED` only means a keyword occurrence count
  changed; `CANDIDATE_PAGES_ONLY` **does not** mean texts are equal.
- `status=SOURCE_CLAUSE_REVIEW_REQUIRED` and
  `manual_revision_equivalence=NOT_VERIFIED` are always emitted.
  No modification or automation changes `ethernet_reference.py`
  manufacturer's version gates; that requires a human-audited diff.

**Human review checklist:** AD/AG relevant External Device Configuration
user-slot range, PLC own-port allowed vs system reserved, A038H units,
default time/count values and cross-field inequalities, manufacturer
revision notes and exact model scope; E/I A031H Opening Method and
remote STOP→RUN behavior. Record **both PDF SHA-256 values**, printed
pages and screenshots/text of the actual changed clause, if any.
If numbers or model scope changed, update source SSOT only with
independently checked manufacturer evidence and focused TDD tests.
Do not treat a new edition as certified without that review.

The tool reads local files, calls local `pdftotext` with a subprocess
argument array (no shell), writes JSON only if requested, and does not
connect to the PLC, external network or manufacturer. Inputs, full PDF
content and source PDFs are not included in CI or committed. Tests use
synthetic PDF byte headers and mocked local extraction.

[PR #42](https://github.com/greatgc-flow/VirtualPLC/pull/42)
is the implementation and test evidence. Physical PLC certification
is a separate, unperformed acceptance gate under issue #2.
