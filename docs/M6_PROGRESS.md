# VirtualPLC M6 — Closed-loop evidence and bounded observability (2026-10-20)

## Exact lineage and branch discipline
- Repository: `greatgc-flow/VirtualPLC` (**PUBLIC**); head on arrival `d77c5200ab0109d5d87517d6a6f814d0a9485ad2`, Draft PR #1. Do not auto-merge or activate GitHub Actions.
- Base 208-case catalogue SHA-256 (unchanged): `31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f`.
- Inherits M1→M5 results. New source files: `virtual_plc/telemetry.py`, `scripts/governance.py`, `scripts/run_m6.py`, `tests/test_m6_runtime.py`, `tests/test_m6_governance.py`; modified `virtual_plc/server.py` and `virtual_plc/__main__.py`.

## What has run locally
- Linux Python 3.13.5, pytest 9.0.2. All 4 distinct pytest phases: M5 baseline 161, M5 new 35, M5 TCP 45, M6 new 20 = **261 PASS** (plus 5 unittest subtests). No failures or skipped items in the combined exact-CASE-ID JUnit.
- Exact catalogue **173/199 P0 observed PASS, 26 NOT_RUN, 0 FAIL; zero independently attested**. The 88 anonymous tests do not increase P0 coverage. New M6 20 CASE-IDs are disjoint from prior 153.
- `scripts/validate_suite.py --mutation` PASS; `baseline_v1.1/scripts/validate_design.py` PASS. No revisions to the 208-case definition.
- M6 tests include 1,000 malformed requests with accurate counters and bounded sample, payload/sentinel-free telemetry, ordinary EOF vs mid-frame EOF, SIGTERM local shutdown, fail-closed change/incident/source/replay policy, and test-failure hash-only record.
- Provenance: `evidence/m6_gate.json`, JUnit, console logs, executable commands and package checksum; **LOCAL ONLY**, not GitHub Actions evidence. Repeat on an independently checked-out GitHub commit.

## Protocol and compatibility blockers (HOLD)
- Official `pymcprotocol==0.3.0` wheel **not installed**; PyPI sha256 `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6` is a published reference, NOT local installation proof. GitHub client source is not a substitute for a hash-pinned official wheel test. The six G0-C cases remain untested.
- Actual Mitsubishi model/firmware-specific error end-codes and other route profiles not verified. `0xC059` remains a simulator placeholder; eight G0-E cases not promoted. Simulator listens only at `127.0.0.1` and must never attach to a physical PLC.
- Windows, multiple OS CI, receiver-side throughput/RSS measurements, release license provenance approval, independent release decision are missing.
- All manual P0 items remain NOT_RUN. CASE-0121 (additional nondefault route) and CASE-0132 (1000-word load vs prototype 960-point cap) require requirements/scope decision before claiming full implementation.

## Fresh P0 count from `M6_REMAINING_P0.json`
Remaining 26 = **18 runtime + 3 static + 5 manual**, grouped: **G0-E 8, G0-C 6, G3 8, G4 3, G1 1**. Preserve each oracle and never treat a synthetic test as a manufacturer-approved end-code test.

## Use and verify
From branch root (Python 3.11+; pytest installed):

```sh
python scripts/validate_suite.py --mutation
python baseline_v1.1/scripts/validate_design.py
python scripts/run_m6.py --fast --output evidence/m6_fast
python scripts/run_m6.py --output evidence/m6_full
python scripts/release_gate.py evidence/m6_gate.json  # expected nonzero/HOLD
```

`run_m6.py` echoes exactly what it writes to per-command logs, emits CASE-ID JUnit and environmental SHA evidence, and **never signs off a release**.

## Feedback loop: failure → evidence → risk/requirements → test → gate
1. Preserve failing CASE-ID + input frame SHA256 (not payload), environment, commit SHA, and test stdout.
2. File a scoped issue with requirement, threat/failure mode and owner; reopen on recurrence.
3. Add an independent regression oracle before implementation; verify on Linux, Windows and representative clients.
4. Update source/protocol/ADR and version-controlled test/evidence mapping; repeat negative validators.
5. Release only with G0-C, G0-E, G3, G4 independent attestation. **M6 release = HOLD**.
