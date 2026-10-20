# VirtualPLC M21 — One-command local verification and evidence

**Date:** 2026-10-20. **Scope:** internal BL-INT-002. **Release: HOLD.** No production PLC network access, no CI activation, no merge.

## New functionality

- `scripts/m21_local_evidence.py`: fixed allow-list `smoke` / `core`; no arbitrary command, no network target option. Works on Python 3.11+ and pytest 8/9.
- `RUN_M21_LOCAL.cmd`: Windows CMD entry point, avoiding PowerShell dependencies. Default mode is `smoke`, 90-second deadline.
- Evidence output **must be a fresh absolute directory outside the source tree**; an existing path is rejected before any child process starts, and evidence records are written with exclusive creation.
- Child stdout+stderr, including initial banner and terminal result, are emitted to stdout **and `console.log` as identical bytes**. Bounded output, timeout/cancellation kill the process group; missing, malformed, skipped, failing or duplicate JUnit tests cannot result in local PASS.
- `result.json` contains runtime mode, exact fixed test list, exit status, JUnit counts, source/test SHA-256, and `release=HOLD`; `manifest.json` (written last with no-clobber atomic link) hashes all generated artifacts. CLI `verify` is read-only and rejects extra/missing/changed files.
- The source SHA-256 recorded here is a local claim, not independently signed machine attestation. A reviewer must still verify Git checkout and source independently. It neither proves Windows execution nor closes the official-client/vendor/release gates.
- The historical M20 ZIP is preserved unchanged; external backlog remains blocked and unchanged in `backlog/M20_BACKLOG.json`. The status delta is in `backlog/M21_DELTA.json`.

## Windows execution

Run in a clean VirtualPLC checkout with Python 3.11+ and pytest installed. Replace the path with a **new** folder each run:

```cmd
RUN_M21_LOCAL.cmd "D:\VPLC_M21_RUN_001" smoke 90
```

For expanded local core tests:

```cmd
RUN_M21_LOCAL.cmd "D:\VPLC_M21_RUN_002" core 120
```

Verify without modifying artifacts:

```cmd
py -3.11 -m scripts.m21_local_evidence verify --output "D:\VPLC_M21_RUN_002"
```

The `run` command itself verifies evidence before returning success. The separate `verify` command emits a NEW standalone read-only verification report to its own console; it is not part of the original captured run output.

## Completed local verification

- `tests/test_m21_local_evidence.py`: 38 passed (including invalid, timeout, missing/modified artifacts, forged approval and real subprocess).
- M21 self-run `smoke`: 31 passed; byte-identical captured console output, JUnit and artifact hashes.
- M21 self-run `core`: 79 passed; byte-identical captured console output, JUnit and artifact hashes.
- Selected legacy runtime/governance group: 95 passed; potentially overlaps the two modes; **do not sum test counts**.
- `tests/test_m21_backlog_delta.py`: additional 2 policy tests.
- Current full M20 historical coverage was NOT rerun as an entire 546-test set for M21; previous evidence is retained as historical. No changes to 199-case catalog, no new external P0 completed.

## Limitations and next actions

- Evidence SHA matching establishes file integrity, not operator identity or approved test origin. The local test runner is a developer diagnostic, not a production PLC qualification tool.
- M22: BL-INT-003, resource-bounded loopback-only concurrency/soak, latency distribution and RSS trend measured without making fabricated performance SLA claims.
- External 16 P0: remain blocked in `backlog/M20_BACKLOG.json`. Do not request external input to continue internal work unless real artifacts appear.
