# M13 — external evidence intake, wheel-unavailable closure discipline

2026-10-20 · repository `greatgc-flow/VirtualPLC` (PUBLIC) · Draft PR #1 · `feat/m1-3e-binary-tdd`

## Inputs and provenance

- The M12 ZIP is preserved without changes in the M13 release package and was checked with ZIP CRC and SHA-256 **241/241**. This is integrity, not independent origin/authenticity.
- GitHub PR #1 was Draft and not merged at M13 start; observed head `c935144ba533a28a13741908f89f836e8efc5d59`.
- Official PyPI `pymcprotocol==0.3.0` wheel SHA-256 is `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6` (PyPI project `https://pypi.org/project/pymcprotocol/`). A network/DNS-blocked download attempt in the M13 Linux environment did **not** obtain the file. Therefore the six real-client tests remain **NOT_RUN**. A fabricated lookalike client must not be used to close these cases.
- The exact Mitsubishi model and firmware are **unspecified**. Do not infer the correct vendor end code for the generic simulator's provisional `0xC059` reply.

## Deliverables

- `scripts/m13_evidence_gate.py`: pure standard-library, fail-closed, local evidence intake; validates catalogue hash, exactly 16 remaining CASE-IDs, optional historic ZIP CRC + SHA-256/entry-list exactness, pinned wheel SHA, and six unique successful CASE-ID test outcomes in JUnit. A parsed JUnit file **does not prove** a real external run. The tool always emits `decision=HOLD` and returns exit code 2 pending independent approval.
- `tests/test_m13_evidence_gate.py`: parametrized tamper tests including fake wheel, missing/skipped/failed/duplicate client cases, forged source claim, unlisted/missing/duplicate archive entries, no-overwrite, stdout-byte equality. These are **additional validation tests**, not new P0 completions.
- `RUN_M13_CLIENT_WINDOWS.cmd`: opt-in command file for an actual Windows PC; downloads public official wheel if available and delegates SHA pin enforcement, localhost tests and console/file evidence to the existing M10 runner. No PowerShell and no PLC network access. Does **not** constitute a Windows CI result unless actually run and independently reviewed.
- `M13_GATES.json`: machine-readable, explicit unchanged external P0 status.

## Launch commands

```bash
# These commands only work in a folder containing the project source.
python -m pytest tests/test_m13_evidence_gate.py -q
python -m scripts.m13_evidence_gate --m12-zip /path/to/VirtualPLC_M12_TDD_183of199_20261020.zip --out-dir ./m13_audit_unique
# Expected process exit: 2 because release remains HOLD; result.json and console.txt still written.
```

Windows client test (runs **only on the user's Windows PC**, never against production PLC):

```bat
RUN_M13_CLIENT_WINDOWS.cmd C:\VirtualPLC_M13_CLIENT_EVIDENCE
```

Do not commit wheel binaries, `_pinned_package`, customer data or local evidence to this PUBLIC repository. Share only non-sensitive hash and JUnit metadata after review.

## Release status

P0 catalogue: 199 required; **183 locally observed in historical M10 evidence (not independently attested)**; exactly **16 external P0 cases** remain open: G0-E 6 manufacturer errors, G0-C 6 official real-client interactions, G3 2 independently observed Windows/OS, G4 2 independent provenance/release approvals. M13 itself promotes **0** cases. Overall release remains **HOLD**.

These gates are independently necessary and not mutually substitutable. Verification feed-back closes only after real evidence -> byte integrity -> matching source profile -> independent review -> signed decision. New failure outcomes must reopen the corresponding gate and create a targeted regression test.
