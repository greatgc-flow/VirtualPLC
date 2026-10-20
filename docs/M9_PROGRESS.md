# VirtualPLC M9 — 2026-10-20

## Provenance first

- Source of truth: `greatgc-flow/VirtualPLC`, public Draft PR #1, pre-M9 HEAD `ca5e08602e0b8389a65f63f5994867797850693d`.
- Previous M8 ZIP CRC **PASS**, but **original M8 SHA256_MANIFEST.json FAILS 7/125 files**. Do not repeat the earlier unrestricted `CRC/SHA PASS` claim.
- Seven mismatches (README.md, `virtual_plc/{__init__,__main__,config,memory,server,telemetry}.py`) **exactly match pinned GitHub Git Blob SHA-1** at that head. Other 118 listed entries match their old SHA-256. Full ZIP entry digest inventory is regenerated independently; not a digital signature.
- `scripts/m9_audit_m8_zip.py` and `docs/provenance/M9_PINNED_GITHUB_BLOBS.json` preserve the original fail and document a reconciled state. The legacy manifest is NEVER overwritten or concealed.

## M9 test changes

- `CASE-0129`: real Linux runtime (`Python >=3.11`) with JSON environment fingerprint and loopback smoke. Does **not** count Windows.
- `CASE-0047`: measured p50/p95/p99, peak RSS (Linux KiB) and release-neutral environment fingerprint; no SLA invented.
- `CASE-0132`: deterministically generated 100/1000-word logical reads, 1000 split as 960+40 due to the 960 point/frame implementation limit, 40 repetitions per size in the CLI report (test fixture also runs 12 rounds). Read values checked on every iteration. Not a full client emulation.
- Additional percentile boundary, invalid input, and manifest policy regression tests. Canonical 208-case catalogue **unchanged**.
- `scripts/merge_m9_evidence.py` checks exact CASE-ID properties in independent JUnit inputs, SHA-256 of each original JUnit, duplicate/error/skip detection, and **181/199 observed P0 / 18 NOT_RUN / 0 attested**. If any phase is missing, reject the gate.

## Independent verification still OPEN

- No official `pymcprotocol==0.3.0` wheel could be fetched in this runtime: PyPI wheel SHA256 is publicly known `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6`, but **the actual wheel bytes were not present/installed**. **G0-C** remains OPEN.
- No selected Mitsubishi PLC model and firmware to bind an authoritative `endcode` profile. Simulator `0xC059` is provisional. **G0-E** remains OPEN.
- Windows runner and user-approved independent CI evidence absent. **G3** remains partially OPEN. Linux metrics alone are not comparable Windows data.
- No externally signed release evidence, no independent approver, 18 missing P0. **G4** HOLD. Never treat source SHA or a local manifest as an external attestation.
- Public repository only; no company data, manufacturing topology or real PLC endpoints; localhost only.

## Reproduction (Python >=3.11)

```shell
python -m pytest tests/test_virtual_plc.py tests/test_m4_p0_case_ids_v2.py suite/tests/domain suite/tests/static tests/test_m5_p0_case_ids.py tests/test_m5_governance.py tests/test_m6_runtime.py tests/test_m6_governance.py tests/test_m7_runtime.py tests/test_m8_route.py tests/test_m8_evidence.py tests/test_m8_merge.py -q --junitxml=artifacts/base.xml
python -m pytest suite/tests/live/test_wire_cases.py -k 'not fuzz' --server-cmd 'python -m virtual_plc --host {host} --port {port}' -q --junitxml=artifacts/tcp43.xml
python -m pytest suite/tests/live/test_wire_cases.py -k fuzz --server-cmd 'python -m virtual_plc --host {host} --port {port}' -q --junitxml=artifacts/fuzz.xml
python -m pytest tests/test_m9_platform_perf.py -q --junitxml=artifacts/m9.xml
python -m pytest tests/test_m9_archive_audit.py -q --junitxml=artifacts/archive.xml
python -m scripts.m9_benchmark --rounds 40 --out artifacts/performance.json
python -m scripts.merge_m9_evidence --evidence-dir artifacts --out artifacts/merge_m9
```

Use `MC_SIM_ADAPTER_MODULE=virtual_plc.test_adapter` with the domain fixtures (PowerShell: `$env:MC_SIM_ADAPTER_MODULE='virtual_plc.test_adapter'`). Capture terminal output in the specific `artifacts/*.log` as well as JUnit. The M9 scripts themselves print their exact JSON file contents.

## Next stage M10

1. User-approved isolated wheel transfer or compatible runner, install **only** digest-verified wheel and run raw Type3E D/M tests, including signed/unsigned word behavior and negative end-code behavior.
2. Select actual model and firmware, cite manufacturer manuals and verify error codes, device head limits, station/route and read limits.
3. Windows independent suite, resource/leak/fuzz stress, policy/risk crosscheck.
4. Capture full 199 P0 unique CASE-IDs and independent release signatures; keep Draft PR, main and CI unchanged until signoff.
