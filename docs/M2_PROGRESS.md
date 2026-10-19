# M2 execution record — 2026-10-19

## GitHub state
Public repository `greatgc-flow/VirtualPLC` · work branch `feat/m1-3e-binary-tdd` · draft PR #1. No auto CI. Source and tests are for **loopback-only nonproduction** use; do not connect physical PLCs.

## Verified locally
- Previous M1: 19 domain / 45 TCP / 48 independent smoke / 20 static tests passed, with overlap. 45 P0 CASE-IDs observed but not release attestation.
- Now: full 208-case catalogue and 73 source/design/suite files extracted byte-for-byte from prior M1 handoff ZIP *in a disposable local directory*, with ZIP CRC, per-file SHA-256, 208 total and 199 P0 assertions passing. Hash of catalogue: `31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f`.
- Real external `pymcprotocol` v0.3.0 is not installed in the analysis runtime. Its two optional tests are **SKIPPED**, not passed. Manual GitHub Actions input `run_pymc=true` installs the exact pinned PyPI wheel and exercises D/M plus raw request capture.
- The 73-file full-suite import is **not yet a Git commit**. This PR contains the importer, runtime tests and manual CI invocation. Do not claim full 208-case suite is published on GitHub until an actual commit contains these files.

## Import full suite locally into this branch
```bash
# Download the prior user-owned M1 handoff ZIP and checkout feat/m1-3e-binary-tdd.
python scripts/import_suite.py /path/to/VirtualPLC_M1_TDD_GitHub_Handoff_20261019.zip
python scripts/import_suite.py /path/to/VirtualPLC_M1_TDD_GitHub_Handoff_20261019.zip --apply
python scripts/validate_suite.py --mutation
python -m unittest discover -s suite/tests/static -p 'test_*.py' -v
MC_SIM_ADAPTER_MODULE=virtual_plc.test_adapter python -m pytest suite/tests/domain -q
python -m pytest suite/tests/live/test_wire_cases.py -q --server-cmd 'python -m virtual_plc --host {host} --port {port}'
git status --short
# Inspect generated files and commit by normal review; DO NOT merge without gates.
```

## Manual CI
Actions -> 'Manual validation' -> Run workflow on PR branch. Leave `run_pymc=false` for quick smoke; set to true to install hash-locked v0.3.0 and run D/M client tests. No dispatch has been initiated by ChatGPT. **G0-C stays OPEN until exact GitHub Actions evidence is reviewed**, including failures and client request bytes.

## Release decision
**HOLD.** G0-E vendor-specific error end-code still OPEN. 208-case design coverage != 208 executable cases. Remaining 154 P0 have not passed. Windows and Linux CI have yet to run.
