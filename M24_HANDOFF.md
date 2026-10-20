# VirtualPLC M24 continuation

1. Verify GitHub latest `main`, Draft PR #1, workflow state and M23 ZIP CRC + file-by-file `FILE_SHA256_MANIFEST.json` before use. Latest main always authoritative over earlier claimed SHA.
2. M23 adds opt-in `scripts/m23_recovery_soak.py`, `tests/test_m23_recovery_soak.py`, `RUN_M23_LOCAL_RECOVERY.cmd`; M23 summary `docs/M23_PROGRESS.md` and `M23_GATES.json`. No default server semantics changed.
3. M23 locally measured a single PID duration soak of 4 loopback clients for 2 seconds and synthetic pre-mutation disconnect/reconnect. Metrics are observations, **not leak-free or vendor certification**.
4. M23 rerun has 797 pytest PASS + 5 unittest subtests, 45/45 TCP, 183/199 local P0. External 16 remain in backlog and release HOLD; do not reopen without new evidence.
5. Next: opt-in scenario taxonomy and cross-run comparisons with source/OS fingerprints and fail-closed evidence. Keep simpler than prior tool spread: reusable functions, bounded options, no external PLC connection, private runtime logs, explicit gates.
6. Do not merge the Draft PR, re-enable CI, or claim official pymcprotocol wheel/Windows/CPU hardware tests or independent approval.
