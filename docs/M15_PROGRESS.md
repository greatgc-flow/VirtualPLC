# VirtualPLC M15 — Real-client wire-evidence hardening

**Date:** 2026-10-20 (Asia/Seoul)  
**Repository:** `greatgc-flow/VirtualPLC` (PUBLIC), work in Draft PR #1; no main merge or Actions reactivation.  
**Release status: HOLD** — this is a local-only non-production 3E Binary TCP prototype.

## Baseline provenance

- Opened the actual `VirtualPLC_M14_TDD_ExternalEvidence_HOLD_20261020.zip`.
- ZIP CRC: PASS. Top-level manifest contains 276 entries, all byte count and SHA-256 checks: PASS. The manifest itself is excluded from its inventory.
- GitHub PR #1 HEAD before M15: `b1c48033add72f1f37d6d482125318e1c25c8fc7`, Draft/unmerged; three historical zero-job push-trigger failure records and no automatic workflow in the branch.
- Previous **183/199 P0** is a historical *local-observed, not independently attested* baseline. All sixteen external cases remain OPEN.

## M15 finding and change (TDD)

**Finding:** The earlier `m10_wheel_gate.py`/`m14_windows_evidence.py` persisted a JUnit file and console output, but six exact **raw requests** sent by the pinned Python client were not archived. The compatibility tests inspected their internally captured packet bytes only in memory. Consequently a post-run reviewer could not replay the client wire-format assertions.

**Fix:**

1. `scripts/m15_wire_evidence.py` decodes and independently validates only the **known localhost dummy** 3E Binary D100/M10 two-frame write/read sequence. It checks frame length, route, command/subcommand, address, count, and D/M payload. It writes 6 CASE-ID-scoped JSON files once, refusing overwrite; each stores request bytes, decoded fields, and SHA-256. It cannot claim release approval.
2. `tests/compat/test_pymcprotocol_030.py` emits these raw capture files **only when the genuine pinned client test is opted in** by the M10 runner. Capture directory is explicitly passed via `VIRTUALPLC_WIRE_EVIDENCE_DIR`.
3. `scripts/m10_wheel_gate.py` now refuses to classify an otherwise zero-exit test suite as a successful client run if any of six raw captures is missing or invalid. Its `result.json` contains the independent capture digests.
4. `scripts/m14_windows_evidence.py` independently re-reads the six request files, checks them against JUnit CASE-IDs and the runner report, and includes the request hashes in its local evidence manifest.
5. Updated M14 offline synthetic fixtures and added M15 mutation tests (header, route, payload, address, command order, duplicates, overwrite, skipped/missing real-client capture).

All test fixtures here use **synthetic local data**; their PASS does **not** certify the real PyPI wheel, Windows, vendor CPU, or external test provenance.

## Local execution results (recorded JUnit/log)

- `tests/test_m15_wire_evidence.py` + `tests/test_m14_windows_evidence.py`: **67 passed**.
- `tests/test_virtual_plc.py` + `tests/test_m12_audit.py` + `tests/test_m13_evidence_gate.py` + `tests/test_m14_vendor_profile.py`: **101 passed** (one benign duplicate-ZIP fixture warning).
- Static unittest: **20 tests passed**.
- Memory-domain pytest with configured adapter: **19 passed**.
- No complete re-run of all historic P0 CASE-ID fixtures in this M15 step. Do not aggregate these test counts into new unique P0s.
- The M15 external client run was **NOT_RUN**: a request to install/download the official `pymcprotocol-0.3.0-py3-none-any.whl` could not produce an authenticated file in this environment. Published PyPI wheel SHA-256: `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6`.

## Open release gates

| Gate | CASE-IDs | State |
|---|---|---|
| G0-C | 0027,0028,0029,0109,0110,0111 | NOT_RUN — official wheel+wire evidence missing |
| G0-E | 0018,0019,0020,0064,0088,0090 | OPEN — exact CPU, Ethernet module, firmware, revision and manual page needed |
| G3 | 0044,0128 | NOT_RUN — independent native Windows tests |
| G4 | 0055,0147 | OPEN — independent review/signoff |

## Windows evidence run

Use a fresh clean checkout at this exact PR head on an isolated Windows dev PC (no physical PLC interfaces); download the official wheel and verify its SHA with `certutil -hashfile ... SHA256`. Execute `RUN_M14_ON_WINDOWS.cmd "C:\...\pymcprotocol-0.3.0-py3-none-any.whl" "D:\VirtualPLC_M15_EVIDENCE_NEW" "<full checked-out HEAD SHA>"`.

The generated output must contain `client_run/raw_capture/CASE-XXXX.json` for **all six** CASE-IDs, complete JUnit, runner log, wheel metadata, console and whole-file SHA-256 manifest. If any proof is missing or altered, the script fails closed. No real PLC network is used; all traffic is localhost. **Keep evidence private**; do not commit wheel, raw environment fingerprints, or local machine information to the PUBLIC repository.

## Research references

- Official wheel hash and release date: https://pypi.org/project/pymcprotocol/0.3.0/
- SLMP 3E Binary reply layout: https://www.mitsubishielectric.com/dl/fa/document/manual/plc/sh080956eng/sh080956engl.pdf
- Note that project `pymcprotocol` describes 3E as tested on Q PLC; 4E is implemented but not tested. Do not infer universal PLC compatibility from local simulation.

## Feedback loop

`Requirement/CASE-ID -> failing test -> minimal code change -> targeted regression -> immutable wire/JUnit/source hashes -> independently reviewed evidence -> gate decision -> new deficiency report`. Reopen a gate if source, client version, route, profile or test definition changes; never substitute test-catalog presence for executed proof.
