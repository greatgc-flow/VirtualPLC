# Manual cross-check (issue #2)

Source: MELSEC Communication Protocol Reference Manual, SH-080008, revision AB (RJ71C24 edition; also covers QJ71C24N/LJ71C24).
URL: https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080008/sh080008ab.pdf (fetched 2026-10-30)
SHA-256: b5b601f8d6b0eaa4e63d8ba7244301d009d671e406ea4ad62b1d06178d84ae02
Extraction: `markitdown-gc[pdf]` (manual.md) and `pdftotext -layout` (m.txt). The PDF and transcripts are Mitsubishi Electric copyright; they are kept locally in `.manual/` (git-ignored) and not redistributed. Re-fetch from the URL and verify the hash.

## Findings (page = printed page in the PDF)
| Item | Manual says | Status |
|---|---|---|
| Remote STOP 1002 mode | Fixed value `0001H` (p.174) | verified; current `(1,)` correct |
| Loopback 0619 data | Numerals 0-9 and characters A-F, 1-960 bytes (p.184) | applied: restricted to 0-9, A-F, a-f (case unverified) |
| Device number notation | Decimal or hexadecimal by device type; X, Y, B, W (and others) are hexadecimal (p.68 device code list, device number field) | implemented as opt-in |
| Batch read/write points | Word 1-960 (iQ-R) / 480 (Q/L via C24) per request, bit up to 7168 points, depending on target module | module-dependent; the 4096 default `max_points` is not a manual value |
| Error code table | Not in SH-080008. See SH-081257 below. | see below |
| Zero-point random ops, bad_end_code frame shape | Not located yet | unverified |

## Second source: MELSEC iQ-R Ethernet User's Manual (Application), SH-081257ENG rev AD
URL: https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf (fetched 2026-10-30)
SHA-256: 21039bce5832a420a138da52ffab1c8b7e5f19ee7d67e9c1033f3b0fbc6a7dbc
Section: 3.5 List of Error Codes (p.458+). Extraction: `pdftotext -layout` (columns interleave; read rows carefully).

| Code | Manual meaning | Simulator today |
|---|---|---|
| C050H | ASCII data that cannot be converted to binary | not used |
| C051H | word read/write points out of range | POINTS_OUT_OF_RANGE (ok) |
| C052H / C053H / C054H | bit points / random bit points / random word-dword points out of range | all mapped to C051 or C05C |
| C056H | read/write exceeds largest address | ADDRESS_OUT_OF_RANGE (ok) |
| C057H | request data length does not match number of data in text | applied: DATA_LENGTH_MISMATCH (0xC057) |
| C058H | request data length after ASCII/binary conversion mismatch | not used |
| C059H | command/subcommand incorrect or unsupported | UNSUPPORTED_COMMAND (ok) |
| C05AH / C05BH | cannot read/write the specified device | not used |
| C05CH | request data incorrect | REQUEST_DATA_ERROR (ok) |
| C061H | request message with no-response command sent to another network | applied: remapped data-length mismatch to C057 |
| C202H | remote password could not be unlocked on another station | simulator uses C202 as INVALID_STATE (not supported by manual SH-081257 3.5; remap tracked in issue #5) |
| C203H | error checking the remote password | documented remote-password error code; simulator uses C200/C201 (remap tracked in issue #5) |
| C204H | lock request from a different device than the unlock requester | documented remote-password lock code (remap tracked in issue #5) |
| C200H / C201H | listed with SLMPSND dedicated-instruction failure (layout ambiguous) | simulator: LOCKED / WRONG_PASSWORD (not supported by manual SH-081257 3.5; C203/C204 are the documented remote-password codes; remap tracked in issue #5) |
