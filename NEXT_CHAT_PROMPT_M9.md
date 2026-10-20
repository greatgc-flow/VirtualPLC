# VirtualPLC M9 handoff

Open latest GitHub public `greatgc-flow/VirtualPLC`, Draft PR #1; compare current PR HEAD with M8 commit recorded in `docs/M8_PROGRESS.md` (prefer real latest HEAD). Verify M8 ZIP CRC and per-file SHA, read `README.md`, `M8_REMAINING_P0.json`, `docs/M8_PROGRESS.md`, `evidence/m8_verified/gate.json`, canonical `suite/catalog/test_cases.jsonl`. Do not enable automatic Actions or merge main.

M8 local evidence: source+suite integrity PASS, **178/199 P0 observed local PASS**, 21 NOT_RUN, 0 attested; full suite 208 cases unchanged. New opt-in route CASE-0121, hash-chain local evidence CASE-0146. Existing M7 CASE-0068 mock updated to include allowed_routes.

Next: 1) obtain exact PyPI pymcprotocol==0.3.0 wheel, verify pinned SHA `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6`, run binary Type3E D/M against local server, compare raw packets and signed int behavior; 2) determine actual PLC model/firmware and official end codes without invention, 3) reproduce Windows/Linux with independent CI evidence (keep workflow disabled until explicit approval), 4) sign gate evidence externally and inspect license/security/throughput; 5) update test-case exact IDs only from JUnit verified evidence. Production/physical PLC use remains prohibited.

Deliver a single integrated ZIP with source + full 208-case catalogue + JUnit and manifests + GitHub readback; fail closed on missing evidence.
