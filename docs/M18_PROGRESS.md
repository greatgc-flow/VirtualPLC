# VirtualPLC M18 — portable external-evidence intake hardening

Date: 2026-10-20. Work branch `feat/m1-3e-binary-tdd`, Draft PR #1. **Release HOLD**.

## Purpose and concrete security change

M17 already fail-closed on Windows preflight (Python/pytest/Git/wheel paths). M18 protects the **incoming Windows evidence ZIP** when inspected on Linux, macOS, or Windows: a ZIP path is not assumed safe merely because its POSIX normalization is safe.

`m16_provenance_gate` now refuses ZIP member names with Windows drive-relative prefixes (`C:foo`), NTFS ADS (`data:stream`), reserved device names (`CON`, `NUL`, `AUX`, `COM1..9`, `LPT1..9`, etc.), trailing space or dot, empty or dot components, control characters, and path traversal. Directories remain recognized, but file type, CRC, size, compression ratio, precise manifest coverage and SHA-256 still undergo the previous checks. All rejected members remain unextracted.

The CLI also refuses to place a potentially identifying/private Windows evidence review result inside the public Git repository, overwrite the input evidence ZIP, or use an existing symlink as the report path. All failures remain HOLD.

## Reproducible actual execution on Linux (M18)

| Group | Recorded execution | JUnit |
|---|---:|---|
| Existing core A | 122 PASS | `M18_CORE_A.xml` |
| Existing core B | 81 PASS + 5 subtest PASS | `M18_CORE_B.xml` |
| M12..M17 evidence plus M18 portable tests | 244 PASS | `M18_EVIDENCE.xml` |
| Live TCP, split 16 + 16 + 13 | 45 PASS | `M18_TCP_0/1/2.xml` |
| **Unique executed pytest** | **492 PASS** | Six disjoint group files |

The M18-specific 26 tests are included in the 244 evidence tests. No duplicate pytest executions are added to the total. The 16 external P0 case IDs remain **NOT RUN / UNVERIFIED / NOT APPROVED**. Historic **183/199 locally observed, independently unattested** persists unchanged.

## Source paths

- `scripts/m16_provenance_gate.py`: portable path validation + safe result destination; existing archive validation retained.
- `tests/test_m18_portable_archive_security.py`: deterministic 26-case tests; synthetic fixtures, **not real Windows attestation**.
- `M18_GATES.json`: fail-closed gate ledger.
- `M19_HANDOFF.md`: handoff and next steps.

## Human-operated steps

1. On a clean, isolated Windows test PC with no plant routing, run the latest exact PR HEAD using `RUN_M17_WINDOWS_ONE_SHOT.cmd "AUTO" "D:\\VPLC_M18_FRESH" "<LATEST_40_HEX_HEAD>"` or SHA-verified offline wheel.
2. Privately share `M14_CLIENT_RUN.zip` + `D:\\VPLC_M18_FRESH.preflight.json` and any relevant operator attestation. Do **not** publish in GitHub (repository is public).
3. Verify with `python -m scripts.m16_provenance_gate --zip "...\\M14_CLIENT_RUN.zip" --result "D:\\VPLC_M18_REVIEW.json"` **outside source checkout**. Inspect file hashes and exact six CASE-IDs, then independently attest the machine, source HEAD and operator.
4. G0-E requires a real CPU/model, Ethernet module, firmware and cited official Mitsubishi manual revision/page. G4 requires an independent release/licensing/failback review.

## Limits / prohibited promotion

- PyPI official pinned 0.3.0 SHA-256 was checked independently, but **the pinned wheel was not downloadable or executed in this environment**. Source-tag API inspection is not distribution execution.
- No actual Windows client execution and no vendor hardware were observed during M18; therefore no G0-C, G0-E, G3, or G4 gate closes.
- Cross-platform archive validation does not certify authentic data, identity, manufacturer compatibility, or release approval.
- Do not merge `main` or change GitHub Actions state without user instruction.

## References

- PyPI `pymcprotocol` official artifact: https://pypi.org/project/pymcprotocol/0.3.0/
- Upstream source release tag `0.3.0`: https://github.com/senrust/pymcprotocol/tree/0.3.0
- Mitsubishi QnUCPU built-in Ethernet manual (model-specific reference only, not an assertion of user hardware): https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080811eng/sh080811engy.pdf
