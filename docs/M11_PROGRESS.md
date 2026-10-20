# VirtualPLC M11 — verified run and open-gate disposition (2026-10-20)

## State and non-claims
- Repository: https://github.com/greatgc-flow/VirtualPLC; PUBLIC. Work exclusively in Draft PR #1, do not merge main and do not activate scheduled/push GitHub Actions.
- Prior M10 exact CASE-ID baseline: **183/199 local observed, 16 NOT_RUN, 0 independently attested**. M11 makes no new CASE-ID PASS claims. All external release gates remain open; **RELEASE HOLD**.
- `pymcprotocol` wheel 0.3.0: official PyPI SHA256 `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6`. Direct network package download attempt failed DNS resolution and alternative download failed. **NOT INSTALLED / NOT RUN**. Testing a homemade client or GitHub source is not proof of this wheel.
- Windows 3.11+ official-client/OS proof: **NOT RUN** on Windows.
- Manufacturer family/model/firmware and end-code map: **UNSPECIFIED / NOT VALIDATED**. Provisional `0xC059` must not be represented as vendor error-code accuracy.

## New tests / independent execution
1. `tests/test_m11_model_properties.py`: 24 randomized, deterministic seeds * 120 read/write steps each = 2,880 independent read/write oracle checks, with periodic atomic-failure assertions. 24 PASS. No physical PLC, no release certification.
2. `tests/test_m11_gatekeeper.py`: 12 anti-false-green, bad wheel, external-artifact provenance and evidence overwrite guard tests. 12 PASS.
3. Focused regression: `tests/test_virtual_plc.py` plus M11 tests = **84 PASS** from clean local rerun; JUnit `m11_focused.xml`.
4. Second baseline subset: domain, static, M9 release gate and M10 boundary = **50 PASS plus 5 unittest subtests**, JUnit `regression_subset.xml`.
5. Broad baseline run attempted but **TIMED OUT** at 47% collection/progress; see `evidence_m11/base_m11.log`. It is never counted as full PASS. Original M10 evidence is retained byte-for-byte in prior ZIP.
6. Cross-phase counts overlap. Do not add 84+50 and claim independent CASE IDs. No new `case_id` property is inserted in M11 tests.

## M11 verification gate

Run:

```shell
python -m scripts.m11_gatekeeper --out new_m11_evidence
```

Always returns nonzero (2) while release gate HOLD; writes `result.json` and `console.txt` with **exactly the same bytes** as console stdout. Refuses to overwrite existing evidence. An optional wheel is only considered `WHEEL_HASH_VERIFIED_TEST_NOT_RUN` until the real client tests are executed. User-provided Windows JUnit or model-profile metadata is labeled `UNATTESTED`, not accepted as certification.

To test official 0.3.0 wheel if a verified binary is available, run existing:

```shell
python -m scripts.m10_wheel_gate --wheel /path/to/pymcprotocol-0.3.0-py3-none-any.whl --evidence-dir new_client_evidence
```

On Windows, the existing `RUN_M10_CLIENT.cmd` wrapper is supported. Review all six real-client CASE-ID tests, JUnit failures, wire capture, full wheel hash and relevant Python/OS fingerprints before considering any G0-C advancement. The command MUST NOT contact a production PLC (all tests use loopback).

## Exactly 16 unfinished P0 CASE-IDs
G0-E: 0018 0019 0020 0064 0088 0090 (6; manufacturer error semantics required); G0-C: 0027 0028 0029 0109 0110 0111 (6); G3: 0044 0128 (2); G4: 0055 0147 (2).

**Next runnable actions:** (1) obtain SHA-pinned wheel from official PyPI and run client cases in isolated environment; (2) independently run Windows suite and archive exact logs; (3) select target Mitsubishi PLC CPU model/firmware and obtain normative error code source; (4) review all 199 P0 tests and independent release attestation before merge. Do not downgrade tests merely to increase pass ratio.

## Reference (copyright-safe original links)
- https://pypi.org/project/pymcprotocol/ (version 0.3.0 released April 26 2021; wheel SHA above)
- https://github.com/senrust/pymcprotocol (source, MIT; the wheel is not in this package)
- Mitsubishi Electric SLMP Reference Manual SH-080956ENG: https://www.mitsubishielectric.com/dl/fa/document/manual/plc/sh080956eng/sh080956engl.pdf

## Safety
No IP except 127.0.0.1 is used. No actual equipment or production data; GitHub is PUBLIC. No workflow activation / PR merge / production certification.
