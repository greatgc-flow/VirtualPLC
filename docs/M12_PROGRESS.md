# M12 — regression hardening, evidence provenance and explicit external gates

Date: 2026-10-20. Work branch `feat/m1-3e-binary-tdd`; GitHub `greatgc-flow/VirtualPLC` is **PUBLIC**. The default branch, physical equipment, automatic CI and the release designation must not be modified.

## Checked before changes
- M11 handoff ZIP: `ZipFile.testzip() == None`, **235/235 files** match its `FILE_SHA256_MANIFEST.json`, no untracked ZIP files; historic package retained unmodified.
- GitHub Draft PR #1 HEAD: `062e43d5f76ee8b5c9d9aae5a5a000e741668046` at initial M12 checkout. Repo visibility Public; no new Actions run at initial check.
- PyPI: `pymcprotocol==0.3.0` wheel `pymcprotocol-0.3.0-py3-none-any.whl`, SHA-256 `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6` (published 2021-04-26). The container has no package installed and cannot download due to DNS failure. This is **NOT RUN**, not a failed interoperability test and not a PASS.

## New independent tests
- `tests/test_m12_fault_matrix.py`: **51 passing cases** against real local server or `Memory/process`. Ten D-word boundary/endian cases, 16 M-bit packing parity cases, 17 invalid decoded commands with atomic failure, four truncated commands, one concurrent atomic snapshot, three TCP connectivity/fragmentation scenarios. All connections loopback only. Deliberately no new P0 CASE-ID mapping: these are supplementary regression cases.
- `tests/test_m12_audit.py`: **10 passing mutation/negative tests**: zero/incorrect/duplicate/failed/errored/skipped JUnit results are rejected; overwrite refused; stdout evidence exactly equals both stored copies, release remains HOLD.
- Standalone M12 suite: **61/61 PASS**, JUnit `m12_new.xml`.
- Combined focused rerun with prior M1/M10/M11: **153/153 PASS**, JUnit `m12_regression_combined.xml`.
- Audit script `python -m scripts.m12_audit --junit ... --out ...`: PASS for *local regression only* and emits JSON/console.txt identical bytes. Refuses to overwrite. It records baseline **183 P0 local observed / 16 open / 0 independently attested**.

The previous global **183/199** is a carried-forward, locally observed historical value. No claim of a fresh 199-case run, Windows validation, vendor error-code certification, wheel integration, or final approval is made in M12.

## External release gates (unchanged)
- **G0-E**: 6 model/firmware-specific Mitsubishi end-code scenarios; CPU series and firmware are unspecified. The currently returned `0xC059` is a simulator fallback and not a verified across-model mapping.
- **G0-C**: 6 real `pymcprotocol` v0.3.0 wheel interoperability scenarios. Official SHA is known, **wheel not obtained/installed, tests not run**.
- **G3**: 2 actual Windows runs with captured platform and source identity, NOT RUN.
- **G4**: 2 independent evidence and release attestations, UNATTESTED.

### How to proceed without prematurely marking PASS
1. Obtain the wheel from [official PyPI](https://pypi.org/project/pymcprotocol/), verify SHA256 before install in an isolated Python environment, run the six existing `tests/compat` cases against **127.0.0.1 only**, capture raw network frames and JUnit.
2. Choose exact Mitsubishi CPU series / Ethernet module / firmware and locate the normative vendor end-code table for that profile. Distinguish unsupported command, invalid device, route, point count and CPU-specific errors in response policy.
3. Run Windows independently with source commit identity, interpreter/OS versions, complete logs and JUnit. Do not accept file labels or screenshots as sole proof.
4. Review all 199 P0 outcomes and artifacts independently, sign off G4, then consider nonproduction release candidate. Keep a release HOLD until then.

## Sources
- PyPI source and wheel SHA: https://pypi.org/project/pymcprotocol/
- pymcprotocol repository: https://github.com/senrust/pymcprotocol
- Mitsubishi SLMP Reference Manual SH-080956ENG: https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080956eng/sh080956engm.pdf

**Production, remote-network and physical PLC use remain prohibited for this experimental artifact.**