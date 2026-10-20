# M27 continuation — VirtualPLC

1. Verify Draft PR #1, GitHub branch latest HEAD, `main`, inactive CI; do **not** merge, publish real machine evidence, or re-enable workflows without explicit user instruction.
2. Validate M26 ZIP CRC and `FILE_SHA256_MANIFEST.json` for all members, excluding self. Read `docs/M26_PROGRESS.md`, `M26_GATES.json`, `scripts/m26_multi_run.py`, `tests/test_m26_multi_run.py`, `backlog/M20_BACKLOG.json`, and the 11 JUnit originals.
3. M26 locally verified: 1,015 unique pytest PASS (+5 subtests), 45 loopback TCP PASS, P0 183/199, remaining 16 external HOLD; local 3-run p95 [613,521,521] us. Distinguish measured vs certified.
4. New tool: `python -m scripts.m26_multi_run --out <NEW_OUT> --runs 3 --clients 2 --duration 0.5`. `RUN_M26_LOCAL_REPEATS.cmd` convenience. Outputs unique child folders, stdout, `report.json`, JUnit and SHA-256 manifest. Existing destinations rejected. Fail/interrupt => HOLD; never auto-retry uncertain writes.
5. External 16 P0 are intentionally queued in M20 backlog (G0-C 6, G0-E 6, G3 2, G4 2). User asked to keep developing without blocking on those items.
6. Suggested M27: comparative evidence-diff/anomaly report for 3..30 M26 observations, deterministic and MECE, opt-in conditions. Avoid false SLA or memory leak claims. Retain tests, source links, and handoff in one ZIP; push only portable sources/docs to Draft PR.
