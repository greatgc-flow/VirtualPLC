# VirtualPLC M8 — TDD route allowlist, evidence integrity and exact CASE-ID gate

Date: **2026-10-20**. Base: M7 ZIP 171 entries / 170 individually SHA-256-verified files, public GitHub Draft PR #1 HEAD `b7c6d6cfdd1d72d2bce1fc9a81935b460c09a54e` on entry. **RELEASE HOLD**.

## Actual changes

1. **CASE-0121**: explicit opt-in 5-byte nondefault MC 3E route allowlist. Default route remains `00 FF FF 03 00`. Example extra synthetic route is `02 FF FF 03 00`; the server only echoes the route, never forwards packets to external PLCs. Unconfigured routes, duplicate routes, malformed hex, all-FF wildcard, oversized allowlist and non-loopback bind are denied. Config: `[server] routes=["00FFFF0300","02FFFF0300"]`. The allowed table is bounded to 16 entries. This is a simulator-only route contract; external PLC multi-hop behavior is **not** claimed.
2. **CASE-0146**: SHA-256 source+catalog report with digest sidecar; verification recomputes source hashes and catalogue counts; creation uses exclusive file creation with no overwrite. This provides local integrity checking, **not digital signatures or tamperproof storage**. Full independent release attestation remains open.
3. Updated M7 CASE-0068 fake Handler fixture to match new Server interface. This regression had initially **FAILED**, then passed after a minimal test-double-only fix. The first failure is recorded in M8 work history.
4. Added verifier mutation tests rejecting missing phase, failed test and duplicate CASE-ID. No new legacy catalogue entries or re-numbering.

## Observed verification

- M7 archive ZIP CRC PASS, file-by-file SHA-256: **170/170 PASS** (manifest itself excluded from its listing).
- Complete baseline test phase: **216 PASS + 5 unittest subtests PASS**.
- TCP general: **43 PASS** (2 fuzz deselected); fuzz: **2 PASS** (43 other cases deselected).
- M7 + M8 tests: **25 PASS** (3 M7 + 22 M8 including CASE-0121/0146).
- M8 verifier mutation tests: **3 PASS** in a separate run, not included in the 286 CASE-ID merge.
- Total independently completed pytest testcases **289 PASS** (286 JUnit phase tests plus 3 verifier mutation tests), with 5 additional unittest subtests; subgroup counts are not unique catalogue IDs.
- Four JUnit phase inputs total: **286 passed**, no failures/skips. Exact P0 JUnit identity: **178/199 observed PASS; 21 NOT_RUN; 0 FAIL; 0 SKIP; 0 independently attested**. No duplicate/unknown CASE-ID. Source 208-case catalogue SHA unchanged: `31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f`.
- Static checks: suite 208-case traceability and baseline v1.1 design cross-links **PASS**.

See `evidence/m8_run`, `evidence/m8_verified`, `evidence/m8_integrity`, `M8_REMAINING_P0.json`. All P0 counts are **local observed**, not release approval.

## Fail-closed gates

- **G0-C**: real PyPI wheel `pymcprotocol==0.3.0` not downloaded/installed, despite PyPI SHA-256 being publicly confirmed as `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6`. Do not pass `CASE-0027/0028/0029/0109/0110/0111`, nor CASE-0055/0147 requiring real client/version evidence.
- **G0-E**: official Mitsubishi Q/L/iQ etc. end codes and behavior are model/firmware-specific. Simulator `0xC059` is **provisional**; eight related CASE-IDs remain open.
- **G3**: no Windows runtime / CI evidence; Linux loopback measurements are not independent performance certification.
- **G4**: local hash report is not independent cryptographic signature; release approver has not signed.
- **CI**: active workflow remained disabled; prior 3 push-time failures were zero-job/validation records. Do not activate workflows, merge `main`, or change repository visibility without authorization.

## Quick reproduction

```sh
python -m pytest tests/test_m8_route.py tests/test_m8_evidence.py tests/test_m8_merge.py -q
MC_SIM_ADAPTER_MODULE=virtual_plc.test_adapter python -m pytest tests/test_m7_runtime.py -q
python scripts/evidence_m8.py --out evidence/NEW_M8_INTEGRITY
python scripts/merge_m8_evidence.py --junit-dir evidence/m8_run --out evidence/NEW_M8_VERIFIED
```

Run full tests in isolated phase groups documented in `scripts/run_m7.py`; the previous 43 TCP and 2 fuzz tests are intentionally isolated. No external network endpoints are used.

## Sources

- Official SLMP specification (frames and end-code behavior): https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080956eng/sh080956engl.pdf
- Official PyPI pinned client release/hash: https://pypi.org/project/pymcprotocol/0.3.0/
- GitHub PR: https://github.com/greatgc-flow/VirtualPLC/pull/1

## M9 handoff

See `NEXT_CHAT_PROMPT_M9.md`. Continue only with verified GitHub HEAD, validate package SHA and file identities, and never reclassify NOT_RUN as PASS.
