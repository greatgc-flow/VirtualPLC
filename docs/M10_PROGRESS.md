# VirtualPLC M10 — 2026-10-20

## Status — local-only, unapproved

- Repo: `greatgc-flow/VirtualPLC` (PUBLIC); Draft PR #1; no main merge or CI activation.
- M9 before M10: 181/199 unique P0 CASE-ID locally observed PASS, 18 NOT_RUN.
- M10 added **CASE-0089** (D9999 final legal point) and **CASE-0092** (D0/M0 address zero). P0 local observed: **183/199**, **16 NOT_RUN**. No independent attestation. HOLD.
- Full M10 observed groups: `base` 244, `tcp_a` 20, `tcp_b` 20, `tcp_c` 5, `m9_additional` 16, `m10` 13 = **318 pytest PASS**. Additional M10 evidence-mutator tests: 6 PASS (separate, not part of 318); existing 5 `unittest` subtests are reported separately and not counted as new CASE-IDs.
- G0-E manufacturer end-code and model/firmware profile: **OPEN**. A simulated error does not prove a vendor end-code. Both new CASE-IDs are bounded-memory success behaviors, not manufacturer-profile certification.
- G0-C actual PyPI wheel: **NOT_RUN**. The download attempt could not resolve the package index; scripts enforce pinned SHA-256 `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6` on supplied `pymcprotocol-0.3.0-py3-none-any.whl`. Six tagged real-client tests remain SKIPPED until real wheel is installed with explicit opt-in, and none were counted as passes. See https://pypi.org/project/pymcprotocol/.
- G3 Windows independent testing: **NOT_RUN**. User can execute `RUN_M10_CLIENT.cmd` after obtaining the exact wheel. The run must still be externally reviewed, not promoted automatically.
- G4 release: **HOLD**, P0 observed not signed; no additional CASE-ID registered without JUnit evidence.

## M9 package forensic note

M9 ZIP CRC passes; 232 entries referenced in the top-level SHA-256 manifest match, but an additional actual ZIP file (`project/FILE_SHA256_MANIFEST.json`) is **not listed** by that top-level manifest. The M9 original remains unchanged. M10 final package regenerates a complete manifest for every emitted payload, including nested copies; no claim that original M9 manifest was exhaustive.

## Sources and known constraints

- Official protocol: Mitsubishi SLMP Reference Manual SH-080956ENG, model support to be verified.
- Official client source: https://github.com/senrust/pymcprotocol and PyPI wheel (MIT).
- Signed word behavior: 16-bit wire patterns, client-side interpretation may be signed; 0xFFFF wire is not automatically the integer +65535 to signed readers.
- Raw-packet case oracle: derived `VEC001`/`VEC002`/`VEC003` from `suite/fixtures/wire_vectors_baseline.json`, **not** previously observed real client packets. Real-client tests compare them only when the verified wheel is present.
- Windows quick command: `RUN_M10_CLIENT.cmd "C:\path\pymcprotocol-0.3.0-py3-none-any.whl"` from checkout root, with `python` on PATH; optional `VIRTUALPLC_PYTHON` environment override. Outputs `m10_client_evidence/` (no overwrite). Run only against 127.0.0.1.
- M10 local evidence ZIP `evidence_m10/merged` contains exact CASE-ID reconciliation, JUnit hashes, and console/file match. The default TDD test runner does not manufacture external compatibility evidence.

## Next M11 priorities

1. User-supplied or verified-download wheel: run 6 real Type3E tests and capture raw bytes; archive wheel SHA and Python/OS fingerprint. If mismatch, investigate before marking any G0-C IDs.
2. Select Mitsubishi family/model/firmware and manufacturer-supported error codes; change provisional `SIMULATED_ERROR` only after independent references.
3. Independent Windows >=3.11 execution, deliberate fault injection/performance characterization, review privacy and threat model.
4. Re-run all suites, compare retained evidence; then consider independent signoff / opt-in CI / PR review. **Do not merge main or enable automatic workflows yet.**
