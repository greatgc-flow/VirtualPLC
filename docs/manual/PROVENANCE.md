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
| Batch read/write points | SH-080008 p.87/91/96 (Ethernet E71 column): `Q`, `L`, `iQ-L`, `iQ-R` word `1..960`, bit binary `1..7168`, bit ASCII `1..3584`; `QnA` word `1..480`, bit binary `1..3584`, bit ASCII `1..1792`. Zero or over-limit rejected: `C051` (word points out of range), `C052` (bit points out of range) per SH-081257 3.5 | applied: stored per profile as `(profile, wire, unit)` in `profiles.py` (`QnA` shares Q-class wire with lower caps); `--max-points` defaults to `None` (optional additional cap `min(manual_cap, max_points)`); direct `Memory` calls uncapped (manual-derived; C051/C052 code assignment unverified, real-PLC verification still open in #2) |
| Error code table | Not in SH-080008. See SH-081257 below. | see below |
| Error information in abnormal response and bad_end_code frame shape | Abnormal response carries access route, command, subcommand after end code with response data dropped and length updated (5.2 p.92, 5.3 p.102) | applied (manual-derived; other-station routing and real-PLC no-error-info unverified) |
| Random-access point limits (zero and upper bounds) | Read 0403: `words + dwords <= 192` (Q-class 0000) / `96` (iQ-R 0002) (p.98). Word/dword write 1402: `words*12 + dwords*14 <= 1920` (Q-class 0000) / `960` (iQ-R 0002) (p.105). Bit write 1402: `points <= 188` (Q-class 0001) / `94` (iQ-R 0003) (p.108). Zero or over-limit rejected: C053 (random bit points out of range), C054 (random word/dword points out of range) per SH-081257 3.5 | applied: keyed on request wire class (`Wire` in `profiles.py`), independent of `--max-points`; check order: zero total -> over-limit -> length/format (manual-derived; C053/C054 assignment unverified, not verified PLC behavior) |

## Second source: MELSEC iQ-R Ethernet User's Manual (Application), SH-081257ENG rev AD
URL: https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf (fetched 2026-10-30)
SHA-256: 21039bce5832a420a138da52ffab1c8b7e5f19ee7d67e9c1033f3b0fbc6a7dbc
Section: 3.5 List of Error Codes (p.458+). Extraction: `pdftotext -layout` (columns interleave; read rows carefully).

| Code | Manual meaning | Simulator today |
|---|---|---|
| C050H | ASCII data that cannot be converted to binary | not used |
| C051H | word read/write points out of range | applied: `POINTS_OUT_OF_RANGE` (`0xC051`) for batch word zero/over-limit points (`source: manual`; code assignment unverified, real-PLC verification still open in #2) |
| C052H / C053H / C054H | bit points / random bit points / random word-dword points out of range | applied: `C052` (`BIT_POINTS_OUT_OF_RANGE`) for batch bit zero/over-limit points, `C053` for random bit zero/over-limit points, `C054` for random word/dword zero/over-limit points (`source: manual`; manual-derived, code assignment unverified, not verified PLC behavior, real-PLC verification still open in #2) |
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

Note (review 2026-10-30): batch limits are stored per profile (`Q`, `L`, `iQ-L`, `iQ-R` vs `QnA`) keyed by `(profile, wire, unit)` from SH-080008 p.87/91/96 (Ethernet E71 column); random-access limits are keyed by wire class; L, QnA and iQ-L profiles inherit the Q-class (192/1920/188) or iQ-R (96/960/94) random values and are not individually manual-verified. `source: manual` for C051/C052/C053/C054 means the code list is from SH-081257; the path-to-code assignment is design (unverified, real-PLC verification still open in #2).
