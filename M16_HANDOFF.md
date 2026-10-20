# VirtualPLC M16 handoff

1. Confirm PUBLIC repository `greatgc-flow/VirtualPLC` latest main/PR #1 HEAD and branch, check active workflow and runs. Draft and unmerged until explicit evidence and independent approval.
2. Read `docs/M15_PROGRESS.md`, `M15_GATES.json`, `scripts/m15_wire_evidence.py` and the original `prior/VirtualPLC_M14_TDD_ExternalEvidence_HOLD_20261020.zip`. Validate CRC and file manifest before relying on local evidence.
3. Test the actual `pymcprotocol-0.3.0-py3-none-any.whl` only if SHA-256 matches official PyPI hash `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6`. The M10 runner now fails if any raw request capture missing, malformed or conflicting with the six-case JUnit.
4. Inspect captures individually and compare to official wire vectors. Verify the repo HEAD/OS/execution provenance independently; don't count synthetic tests or locally supplied files as authenticated Windows evidence.
5. Acquire targeted Mitsubishi CPU family, Ethernet module and firmware details to anchor vendor error-code tests to exact manual edition and page; do not invent representative model.
6. Leave historical local-observed P0 183/199 and 16 external P0 HOLD until real evidence. Implement tests through Red/Green/Refactor, keep controlled local-only and never connect to production PLCs.
7. Carry forward M15 source/JUnit/manifest hashes and update MECE crosswalk and failure feedback loop. Preserve prior ZIP unchanged and package all outputs reproducibly.
