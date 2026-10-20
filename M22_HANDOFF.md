# VirtualPLC M22 handoff — loopback bounded load & soak

1. Validate the M21 top-level ZIP exact file inventory, CRC, SHA and GitHub Draft PR #1 HEAD. Preserve `main`, no merge, no automated Actions, no release.
2. M21 BL-INT-002: `scripts/m21_local_evidence.py` + `RUN_M21_LOCAL.cmd`, two profiles, timeout, exact stdout capture, no-clobber atomic manifest, negative tests. Tests and exact reports under `evidence_m21/` in ZIP.
3. M20 external 16 P0 remain `BLOCKED` in `backlog/M20_BACKLOG.json`; M21 changes recorded non-destructively in `backlog/M21_DELTA.json`. No need to request Windows, wheel, manufacturer details to proceed with independent work.
4. M22 BL-INT-003: implement bounded loopback-only concurrent/soak runner with explicit iterations/duration/session limits, per-request latency distribution and real RSS sampling, avoid flaky hard performance budgets, generate console/log/JUnit/manifest, ensure clean server/thread lifecycle even on interrupt/failure, protect sensitive data.
5. M23 BL-INT-004: deterministic scenario sequencing and operator runbook. Keep all additions modular, optional, null/empty tolerant; never connect to production PLCs.
6. Historical P0 183/199 locally observed, 160 directly observable in M20 10 JUnit files, 16 external BLOCKED; M21 does not redo full 199-case tally and does not make new P0 claims. Release stays HOLD.
