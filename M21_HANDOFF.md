# VirtualPLC M21 — Continuation

1. Verify GitHub Draft PR #1 latest full HEAD/main/Actions and the M20 ZIP top-level CRC/SHA exact file set. **Do not merge**, activate Actions or release.
2. The user's decision is definitive: **all external hardware/Windows/client/independent-review dependencies stay in backlog**, do not repeatedly demand them before continuing internal implementation. Refer to `backlog/M20_BACKLOG.json` and `docs/M20_BACKLOG.md`; revisit only when authentic evidence appears.
3. M20 internal BL-INT-001 implemented optional loopback-only deterministic `FaultPlan` (`virtual_plc/faults.py`), integrated with `server.py` and `telemetry.py`. No new network controls, no vendor end-code claims; default disabled.
4. M20 complete 10 JUnit files: **546 unique pytest PASS, 5 unittest subtests, 45 live loopback cases**, no duplicate node IDs. Current JUnit has 160 P0 cases, historic P0 observed unapproved 183/199, 16 external HOLD.
5. Next implement **BL-INT-002**: one-command local smoke and evidence runner, fail-closed/no overwrite, console/file match, atomic artifact manifest, test subprocess timeout/cancel and null/empty options. Then BL-INT-003 bounded load/soak with resource telemetry, BL-INT-004 scenario/runbook.
6. Preserve historic JUnit and ZIP, maintain honest PASS/FAIL/SKIP counts. New unit tests for optional features do NOT count as existing external P0s. Keep M21 package and Draft PR in sync; no operator-private evidence on public GitHub.
