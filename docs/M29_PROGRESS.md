# VirtualPLC M29 — Opt-in grouped local regression, CASE-ID and evidence gate

Date: 2026-10-22. **Source committed; release HOLD, no main merge.**

## Purpose
M29 provides an independent, explicitly invoked Python 3.11+ regression gate that runs each local pytest file once, split into bounded groups. This is a development/engineering smoke and evidence runner, not an official Mitsubishi/Windows/client certification. It never installs dependencies, enables GitHub Actions, opens PLC endpoints, or retries uncertain writes.

Usage from a clean checkout on a non-PLC-network Windows development PC:

    RUN_M29_LOCAL_GATE.cmd "D:\VPLC_M29_NEW" 6 240

or:

    py -3.11 -m scripts.m29_local_gate --root . --out "D:\VPLC_M29_NEW" --groups 6 --timeout 240

The destination must not already exist and must be external to the repository. Existing or symlink paths fail closed.

## Verification model (recursive MECE)
1. **Inventory/preflight:** only tests/test_*.py, suite/tests/static/test_*.py and suite/tests/domain/test_*.py. Explicitly excludes external wheel and compatibility tests under tests/compat; no real PLC. All Python source, the catalog, backlog and pyproject are snapshotted with SHA-256 before execution. Dynamic group count 1..12, per-group timeout 20..900 seconds.
2. **Execution:** independent pytest subprocess per group, kill whole local process group on timeout or output overflow. Max captured log 2 MB per group. No automatic retry; TIMEOUT, nonzero exit and missing JUnit never become PASS.
3. **JUnit:** verify well-formed XML, forbid DTD/entities, validate declared suite counts and actual nodes, detect duplicate classname/name test nodes, canonical duplicate CASE-ID owners, skip, error and failure. A skipped test is **not** a PASS.
4. **P0 source catalog:** validate catalog ID uniqueness and membership, canonical JUnit owners and backlog cases, calculate P0 passed vs remaining backlog. Missing CASE-IDs other than external backlog mark HOLD, never falsely certify. Baseline recorded P0 183/199 and external 16 remain historical, not new test evidence.
5. **Source drift:** reread source fingerprint before each group, after execution and before final output. Unexpected source changes stop progression.
6. **Evidence:** separate per-group original JUnit and merged stdout logs, parent byte-identical console.log, report.json, final pass/fail JUnit and full SHA-256 manifest; verify inventory and hashes before returning. Local regression may succeed without becoming a release gate pass: every report carries release HOLD and no independent approval.

## Local development observation
In the restricted workspace, a separate prototype of this M29 runner was exercised using 21 pytest cases, including a genuine nested pytest subprocess, output flooding, process-group timeout, skip, falsified/missing/contradictory JUnit, canonical CASE-ID duplication, source changes and artifact tamper. Observed: **21/21 PASS**, JUnit SHA-256 **08be3d8050cb8065a5755de685043687f9cd23cabaf7010b9f4cda1a5cf61637**. That workspace is a **minimal simulated repository**, not the complete VirtualPLC GitHub checkout, and does not establish that the subsequently committed M29 remote source passed those exact tests. The remote tests/test_m29_local_gate.py and full existing suite remain to be executed from a clean complete checkout.

## Outstanding certification and M30
- Original historical M26 private ZIP and 11 JUnit originals not supplied in this turn; cannot independently revalidate CRC/SHA or prior pass counts.
- Official SHA-verified pymcprotocol, target Mitsubishi device/error manual, independent Windows environment and external independent release approval remain HOLD: **G0-C 6, G0-E 6, G3 2, G4 2**.
- Next M30: execute M29 on the clean full checkout in Windows/Linux isolated loopback, inspect exact original artifacts and SHA, then run two separate M26 bundles through M27/M28, validate private M26 ZIP CRC and original manifests before proposing gate upgrades.
- No changes to main, automatic workflows, license signoff or public upload of machine evidence are authorized.
