# VirtualPLC M25 continuation

1. Verify `greatgc-flow/VirtualPLC` latest `main` and Draft PR #1 HEAD, Actions status, and M24 archive CRC + the top-level full-file SHA-256 manifest; newer GitHub head takes precedence.
2. Read `docs/M24_PROGRESS.md`, `M24_GATES.json`, `scripts/m24_scenarios.py`, `scripts/m24_compare.py`, `scripts/m24_junit_audit.py`; review 2026-10-20 M24 JUnit and local measurement reports from the package.
3. M24 added 3 closed loopback-only deterministic scenarios, descriptive metric comparison with optional caller-owned thresholds, strict one-owner CASE-ID JUnit audit; legacy 62 M4 duplicate labels now `legacy_case_id` without removing any functional test.
4. 922 pytest PASS, 5 subtests PASS, 45 TCP PASS, 183/199 local P0 and 16 external P0 HOLD. Local measurements are not vendor hardware, Windows, official wheel, performance SLA, or memory-leak certification.
5. Continue with independent report verifier, opt-in repeated comparison uncertainty, and bounded fault recovery harness. Preserve short, testable functions and opt-in options.
6. `backlog/M20_BACKLOG.json` is source for 16 externally blocked tests; do not infer approvals, merge Draft PR, or activate CI without user approval. Publish source and only sanitized summary, keep raw runtime logs private in ZIP.
