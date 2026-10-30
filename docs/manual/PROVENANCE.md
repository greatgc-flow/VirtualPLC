# Manual cross-check (issue #2)

Source: MELSEC Communication Protocol Reference Manual, SH-080008, revision AB (RJ71C24 edition; also covers QJ71C24N/LJ71C24).
URL: https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080008/sh080008ab.pdf (fetched 2026-10-30)
SHA-256: b5b601f8d6b0eaa4e63d8ba7244301d009d671e406ea4ad62b1d06178d84ae02
Extraction: `markitdown-gc[pdf]` (manual.md) and `pdftotext -layout` (m.txt). The PDF and transcripts are Mitsubishi Electric copyright; they are kept locally in `.manual/` (git-ignored) and not redistributed. Re-fetch from the URL and verify the hash.

## Findings (page = printed page in the PDF)
| Item | Manual says | Status |
|---|---|---|
| Remote STOP 1002 mode | Fixed value `0001H` (p.174) | verified; current `(1,)` correct |
| Loopback 0619 data | Numerals 0-9 and characters A-F, 1-960 bytes (p.184) | current alnum check is wider than the manual; narrowing to 0-9/A-F is a candidate (case sensitivity unconfirmed) |
| Device number notation | Decimal or hexadecimal by device type; X, Y, B, W (and others) are hexadecimal (p.68 device code list, device number field) | verified; ASCII `manual` numbering policy for X/Y/B/W remains unimplemented |
| Batch read/write points | Word 1-960 (iQ-R) / 480 (Q/L via C24) per request, bit up to 7168 points, depending on target module | module-dependent; the 4096 default `max_points` is not a manual value |
| Error code table (C200, C201, C05C, C061...) | Not in SH-080008 (only example C051H, p.38 refs); table lives in the module user's manual | still unverified; need the Ethernet/serial module manual |
| Zero-point random ops, bad_end_code frame shape | Not located yet | unverified |
