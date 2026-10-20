# VirtualPLC M20 handoff — M19 final state

1. Read current GitHub `greatgc-flow/VirtualPLC` Draft PR #1, compare feature HEAD/main/Actions. Do not merge or activate CI without authorization.
2. Verify M19 full ZIP CRC, top-level SHA-256 manifest and exact file set; preserve the nested M18 ZIP unmodified. `project/FILE_SHA256_MANIFEST.json` is historical only.
3. Read `project/docs/M19_PROGRESS.md`, `project/scripts/m16_provenance_gate.py`, `project/tests/test_m19_portable_name_aliases.py`, `project/M19_GATES.json`, `project/M19_RUN_SUMMARY.json`.
4. Linux M19 separate actual runs: 122 + 81 + 267 + 16 + 16 + 13 = **515 pytest PASS** plus 5 unittest subtests. 23 new synthetic archive security assertions are included in the 267 evidence tests.
5. P0 historical local observed 183/199 independently unattested; 16 external remain HOLD. Official PyPI wheel not installed, Windows environment not executed, exact vendor model unspecified. Never fake these approvals.
6. Windows operator should use `RUN_M17_WINDOWS_ONE_SHOT.cmd "AUTO" "D:\VPLC_M20_RUN_NEW" "<LATEST_PR_SHA>"` on a clean checkout and transfer M14_CLIENT_RUN.zip and preflight report privately. Verify bytes with scripts.m16_provenance_gate before independent human attestation.
7. G0-E requires concrete CPU, Ethernet module, firmware and manual revision/page. G4 requires release/licensing/failback approval. Keep synthetic and authentic evidence separate.
8. Prefer actual external evidence over adding repetitive local TDD tests; if none available, report the gating issue honestly rather than claiming release.
