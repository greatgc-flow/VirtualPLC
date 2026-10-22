# M28 continuation — VirtualPLC
1. Fetch latest main/feat/m1-3e-binary-tdd and Draft PR #1. Never use cached HEAD instead of remote. Preserve HOLD, private operator evidence and inactive CI.
2. Read docs/M27_PROGRESS.md, M27_GATES.json, scripts/m27_compare.py, tests/test_m27_compare.py, docs/M26_PROGRESS.md, M26_GATES.json, docs/handoff/2026-10-22_M26_COMPLETE_CHAT_HANDOFF.md and backlog/M20_BACKLOG.json.
3. On a complete clean checkout, execute the M27 synthetic TDD and grouped full regression with independent JUnit and console byte/hashes. Do not count aborted or unrun groups.
4. Then use private isolated localhost-only Windows M26 outputs to exercise M27, verify original ZIP CRC/member SHA, source/env/run comparability and error paths. Never publish machine evidence to PUBLIC GitHub.
5. M28 proposal: optional comparison of multiple independently captured M26 bundles, with strict workload/source/host metadata checks. User-chosen thresholds only; all success descriptive rather than attestation.
6. G0-C 6, G0-E 6, G3 2, G4 2 => P0 16 external HOLD. Do not merge main, undraft PR, turn on Actions or declare release without explicit approval.
