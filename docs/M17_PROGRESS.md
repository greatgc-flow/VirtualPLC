# VirtualPLC M17 — Windows External Evidence Preflight, Honest Release HOLD

Date: 2026-10-20. Branch `feat/m1-3e-binary-tdd`, **Draft PR #1**. `main` stays unchanged, automatic CI stays disabled, release **HOLD**.

## Goal & objective boundary

M16 introduced `RUN_M16_WINDOWS_ONE_SHOT.cmd` and a fail-closed archive intake. M17 adds a **lightweight prerequisite preflight** for the Windows operator so missing Python, pytest, Git identity and Git clean checkout do not waste a new evidence run or lead to a false attestation.

M17 deliberately **does not claim** a new actual wheel-based execution or independent Windows attestation in this Linux environment. The PyPI `pymcprotocol` 0.3.0 wheel was still unavailable at build time. A successful synthetic Windows preflight must never count toward P0 test approval.

## Changes

- `scripts/m17_preflight.py`: standard-library-only preflight. Requires Windows, Python >=3.11, pytest 8.x/9.x, a *clean* checkout of the **exact user-specified 40-character HEAD**, and Git `origin` pointing to `greatgc-flow/VirtualPLC`. Both requested evidence output and JSON preflight report must be new and outside source checkout. Offline wheel path is SHA-256-verified against the pinned PyPI artifact. `AUTO` defers actual wheel download and verification to the existing M16 script. Failures are fail-closed and report `HOLD`.
- `RUN_M17_WINDOWS_ONE_SHOT.cmd`: one entry point, invoking preflight before the unchanged M16 real-client capture. Preflight JSON saved as `<new-output>.preflight.json` so the M16 new-output refusal rule remains intact. `VPLC_PYTHON=py -3.11` optional, otherwise `python`. Console output of the preflight equals report file bytes verbatim; M16 captures its own download/runner/stdout.
- `tests/test_m17_preflight.py`: 26 deterministic synthetic tests for Windows, supported Python/pytest, Git origin/HEAD/cleanliness, output/report locations, forged wheel, existing report, and console/file equality on failure. These are **not actual Windows tests**.
- Existing M16 source and runtime remain otherwise unchanged. No private Windows logs, OS identifiers, wheel blobs or PLC IPs are added to the public GitHub repository.

## Actually executed locally (Linux)

All are newly executed in this M17 workspace; no M16 JUnit status was silently reclassified:

| Group | Result | Evidence |
| --- | ---: | --- |
| M17 preflight | 26 PASS | `M17_PREFLIGHT.xml` |
| M16/M15 and earlier evidence/exception tests plus M17 | 218 PASS | `M17_EVIDENCE.xml`; includes same M17 tests, do not double count |
| Core A | 122 PASS | `M17_CORE_A.xml` |
| Core B | 81 PASS + 5 pytest subtests | `M17_CORE_B.xml` |
| Live TCP split A/B/C | 16 + 16 + 13 = 45 PASS | `M17_TCP_0/1/2.xml` |

Unique tests from the three non-overlapping core/evidence/TCP groups: **122 + 81 + 218 + 45 = 466 pytest cases PASS** and five subtest successes. M17 standalone 26 tests are already included in the evidence group and are **not counted twice**. The first monolithic core attempt exceeded execution time; it was **not** counted, and completed chunks replace it.

P0 CASE-ID status remains **183/199 local observed historic baseline, 16 external uncompleted**. No verified wheel run, independent Windows run, vendor-specific hardware proof, or independent G4 release approval. The test count of 466 is not a distinct P0 count. All gates HOLD.

## Windows operator steps (offline or explicit AUTO)

1. In a disposable **Windows** development environment with no plant/PLC routes, clone `greatgc-flow/VirtualPLC` and checkout the exact latest **Draft PR #1 HEAD**. Confirm `git status --porcelain` is empty, no generated evidence in repository.
2. Install Python >=3.11, pytest >=8,<10, Git, pip. Use `VPLC_PYTHON=py -3.11` only if desired and available.
3. From root of checkout, invoke:
   - `RUN_M17_WINDOWS_ONE_SHOT.cmd "AUTO" "D:\\VPLC_M17_NEW" "<FULL_40_HEX_PR_HEAD>"` or
   - `RUN_M17_WINDOWS_ONE_SHOT.cmd "D:\\wheel\\pymcprotocol-0.3.0-py3-none-any.whl" "D:\\VPLC_M17_NEW" "<FULL_40_HEX_PR_HEAD>"`.
4. Store `D:\\VPLC_M17_NEW.preflight.json`, `D:\\VPLC_M17_NEW\\M14_CLIENT_RUN.zip`, and console evidence securely. Do not put them in a public issue or PR.
5. Independently run `python -m scripts.m16_provenance_gate --zip "D:\\VPLC_M17_NEW\\M14_CLIENT_RUN.zip" --result "D:\\M17_INTAKE_NEW.json"`. This checks **file integrity**, not actor identity or actual host authenticity. A qualified reviewer must separately validate origin, OS and expected HEAD. For G0-E, also collect concrete CPU/model, module, firmware and vendor manual page/revision.

## Gate matrix

- `G0-C` (6): pinned distribution actual local communication, raw frames and JUnit — **NOT_RUN**.
- `G0-E` (6): manufacturer-specific error mapping and CPU/module/firmware — **UNVERIFIED**.
- `G3` (2): independent Windows host and environment validation — **NOT_RUN**.
- `G4` (2): third-party sign-off, license and release/failback decision — **NOT_APPROVED**.

**Do not merge main or enable Actions without explicit direction.**

## Authoritative references

- PyPI release + pinned wheel digest: https://pypi.org/project/pymcprotocol/0.3.0/
- Upstream source tag `0.3.0` (source inspection, not wheel execution): https://github.com/senrust/pymcprotocol/tree/0.3.0
- Existing source: `docs/M16_PROGRESS.md`, `M16_GATES.json`, `scripts/m16_windows_one_shot.py`, `scripts/m16_provenance_gate.py`.
