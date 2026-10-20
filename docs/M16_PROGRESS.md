# VirtualPLC M16 — External evidence collection and independent integrity intake

Date: 2026-10-20 · Source branch `feat/m1-3e-binary-tdd`, Draft PR #1. **Release HOLD.**

## Rationale and scope

This stage deliberately does **not** increase the historical `183/199` P0 observed count. M15 supplied six real-client test definitions and raw-request hooks, but this execution environment still cannot download the SHA-pinned PyPI 0.3.0 wheel or execute a genuine Windows client run. Source-version static review and mock captures are **not** interchangeable with actual wheel execution or independent attestation.

M16 focuses on the remaining blockers, not feature inflation:

1. `RUN_M16_WINDOWS_ONE_SHOT.cmd` and `scripts/m16_windows_one_shot.py`: Explicit `AUTO` or offline wheel path. `AUTO` fetches only `pymcprotocol==0.3.0` from the official HTTPS PyPI index. **Every** path verifies expected SHA-256 `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6` before invoking M14/M15 integration. Requires Windows, Python >=3.11, pytest, Git, clean PR checkout. Output must be new and outside the public repo. The M14 subprocess is restricted to localhost. The new script never self-approves external P0.
2. `scripts/m16_provenance_gate.py`: Independently examines the resulting `M14_CLIENT_RUN.zip` without opening network endpoints or modifying inputs. Checks path traversal, symlink/non-file records, duplicate names, capacity limits, ZIP CRC, all-file SHA-256/size, required six client CASE-IDs, raw request binary frames and self-reported Windows metadata. Returns `LOCAL_WINDOWS_EVIDENCE_INTACT_NOT_INDEPENDENTLY_ATTESTED` — never `RELEASE_APPROVED`.
3. `tests/test_m16_external_intake.py`: Synthetic adversarial scenarios, **none** accepted as real execution evidence. Includes honest synthetic success, SHA corruption, manifest additions/deletions, forged approval/OS, duplicate file, ZIP slip, malicious symlink, existing output, Windows preflight, optional pip failure and SHA mismatch. The synthetic test fixture claims Windows intentionally; the validator still labels it **UNATTESTED** to demonstrate its limits.

## Verified commands and local evidence

Run separately to avoid TCP test timeout; full one-shot TCP runs do not count if interrupted.

- Core: `MC_SIM_ADAPTER_MODULE=virtual_plc.test_adapter python -m pytest tests/test_virtual_plc.py tests/test_m4_p0_case_ids_v2.py tests/test_m5_p0_case_ids.py tests/test_m6_runtime.py tests/test_m7_runtime.py suite/tests/domain suite/tests/static -q --junitxml=M16_CORE.xml` -> **203 passed + 5 pytest subtests passed**.
- Intake and fault matrix: `python -m pytest tests/test_m16_external_intake.py tests/test_m15_wire_evidence.py tests/test_m14_windows_evidence.py tests/test_m14_vendor_profile.py tests/test_m13_evidence_gate.py tests/test_m12_fault_matrix.py tests/test_m12_audit.py -q --junitxml=M16_EVIDENCE.xml` -> **191 passed**.
- TCP live suite: `suite/tests/live/test_wire_cases.py` in separate 16/16/13 test chunks using local-only `--server-cmd 'python -m virtual_plc --host {host} --port {port}'` -> **45 passed**.

All logs and JUnit raw XML have been preserved in this ZIP. These are *separate verified execution groups*, not a single monolithic invocation; total 439 passing pytest test cases (203+191+45) and five pytest subtest successes, with no claim that this count is the unique P0 count. No actual Windows run is present.

## Source/spec cross-check

- Official PyPI release and wheel SHA-256: https://pypi.org/project/pymcprotocol/0.3.0/
- `pymcprotocol` upstream **tag `0.3.0`**, `src/pymcprotocol/type3e.py`: `_send`, `batchwrite_wordunits`, `batchread_wordunits`, `batchwrite_bitunits`, `batchread_bitunits` exist. Upstream repository: https://github.com/senrust/pymcprotocol/tree/0.3.0
- Mitsubishi reference: https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080008/sh080008ab.pdf (reference only; does not certify unknown production CPU, module or firmware).

## Windows development-PC run — operator handoff

1. Prepare a disposable, clean **Windows** checkout at the exact Draft PR HEAD and confirm it with `git rev-parse HEAD` and `git status --porcelain`. Install Python 3.11+ and pytest. Network access should be restricted to the PyPI index (AUTO case) and 127.0.0.1 for tests. No real PLC/plant network access.
2. Offline: `RUN_M16_WINDOWS_ONE_SHOT.cmd "C:\\wheel\\pymcprotocol-0.3.0-py3-none-any.whl" "D:\\VPLC_M16_NEW" "<FULL_PR_HEAD_SHA>"`.
3. Online **opt-in**: `RUN_M16_WINDOWS_ONE_SHOT.cmd "AUTO" "D:\\VPLC_M16_NEW" "<FULL_PR_HEAD_SHA>"`.
4. Preserve all generated evidence privately, especially `M14_CLIENT_RUN.zip` and `M16_CONSOLE.bin`. The latter has the exact ordered bytes emitted from wheel download (if applicable), real client runner and closing status line. Never upload raw machine identifiers, logs or wheel to PUBLIC GitHub.
5. Validate independently: `python -m scripts.m16_provenance_gate --zip "D:\\VPLC_M16_NEW\\M14_CLIENT_RUN.zip" --result "D:\\M16_AUDIT_NEW.json"`. Output is the exact JSON bytes saved. Even a successful inspection **does not grant independent attestation**: reviewer must compare original wheel, machine/OS evidence, test output and Git commit separately.

## Open release gates and MECE traceability

- `G0-C`: six client CASE-IDs — actual SHA-pinned distribution on isolated localhost required.
- `G0-E`: six vendor-model-specific endcode/behavior CASE-IDs — identify model, firmware, applicable Mitsubishi manual revision/page.
- `G3`: two Windows execution CASE-IDs — independent Windows host provenance and results.
- `G4`: two external acceptance/independent approval CASE-IDs — qualified human review and approved release decision; tools **must never** self-approve.

**No exceptions or inferred passes.** Every failure or new model/revision must reopen the affected gate, update tests and restore immutable evidence in a new run folder.
