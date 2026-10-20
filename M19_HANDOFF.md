# VirtualPLC M19 handoff — authoritative M18 state

1. GitHub repo `greatgc-flow/VirtualPLC`; `feat/m1-3e-binary-tdd`, Draft PR #1. Check HEAD, `main`, Action runs; do not merge main or enable CI absent authorization.
2. Verify M18 ZIP CRC, top-level `FILE_SHA256_MANIFEST.json` entries **and exact file-set match**. The included prior M17 ZIP is immutable; project/FILE_SHA256_MANIFEST.json is historical, not current package authority.
3. M18 changed scripts/m16_provenance_gate.py and added tests/test_m18_portable_archive_security.py (26 synthetic assertions), docs/M18_PROGRESS.md, M18_GATES.json. Review their actual source and evidence.
4. Fresh Linux test runs M18: core A 122, core B 81+5 subtests, evidence 244 (incl M18 26), TCP 45 = 492 unique pytest PASS. Preserve raw JUnit and logs.
5. P0: historical local observed 183/199; 16 external **HOLD**. In this environment verified wheel download and real Windows tests not available. Never claim these as PASS.
6. Human Windows operator (private): clean exact PR commit checkout, Python >=3.11, pytest 8/9, run `RUN_M17_WINDOWS_ONE_SHOT.cmd "AUTO" "D:\\VPLC_M19_NEW" "<LATEST_PR_HEAD>"`. Evidence stays off public GitHub. Use `python -m scripts.m16_provenance_gate --zip ... --result ...`, then independent human attestation.
7. G0-E manufacturer end-code verification needs exact CPU/model, Ethernet module, firmware, and vendor-manual version/page. G4 is separate risk, licensing, failback and independent release approval.
8. Consider expanding portable ZIP guards only where demonstrated by failing tests. No test-count inflation or default changes to production routing.
