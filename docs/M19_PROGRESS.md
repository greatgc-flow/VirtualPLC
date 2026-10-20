# VirtualPLC M19 — cross-platform evidence ZIP namespace alias hardening

**Status: RELEASE HOLD** — October 20, 2026. Draft PR #1; main not merged and CI Actions unchanged.

## Motivation and change

M18 refused Windows reserved DOS names and path traversal, but an intake ZIP could still contain different paths that collide on the same Windows filesystem. M19 improves the **independent incoming-evidence verifier**, not the simulated PLC protocol or its production capability.

- `scripts/m16_provenance_gate.py`: rejects `COM¹`/`COM²`/`COM³`, `LPT¹`/`LPT²`/`LPT³` Windows device-name variants; NFD/decomposed Unicode, bidi format controls, surrogate and private-use characters.
- Detects case-insensitive path aliases (including folder spelling differences) and file/directory prefix collisions **before extracting any member**. `casefold()` intentionally errs on the side of rejection.
- Retains M18 ZIP CRC, all-member SHA-256, exact manifest coverage, compression bomb limits, type checks and private result location checks.
- `tests/test_m19_portable_name_aliases.py`: 23 new synthetic regression cases (and 26 M18 security cases reexecuted). **These do not constitute Windows execution or client interoperability.**

## Actual fresh Linux runs (source of truth = six JUnit files)

| Group | Passed | JUnit |
|---|---:|---|
| Core A | 122 | `M19_CORE_A.xml` |
| Core B | 81 plus 5 unittest subtests | `M19_CORE_B.xml` |
| Evidence M12–M19 | 267 | `M19_EVIDENCE.xml` |
| TCP live loopback, in three independent groups | 16 + 16 + 13 | `M19_TCP_0/1/2.xml` |
| **Total distinct completed pytest** | **515** | `M19_RUN_SUMMARY.json` |

No duplicate test node IDs, skipped, failed or errored cases among these six groups. They are local Linux tests only; no real PLC connection.

## Pending independent gates

The **historical local P0** is 183/199; the remaining 16 are **not verified or approved** (6 actual pymcprotocol wheel-client, 6 model-specific Mitsubishi end codes, 2 Windows, 2 independent release and provenance decisions).

An official `pymcprotocol==0.3.0` wheel was not downloadable in this environment. PyPI SHA256 expected `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6`; the upstream source tag is not a substitute for running the wheel. User-supplied real Windows evidence must remain private; this repository is public.

## Human-operated next step

On a CLEAN Windows checkout at the latest exact feature PR HEAD, with Python >=3.11 and pytest 8 or 9, run:

```
RUN_M17_WINDOWS_ONE_SHOT.cmd "AUTO" "D:\VPLC_M19_RUN_NEW" "<FULL_40_CHAR_FEATURE_PR_HEAD>"
```

Transfer `M14_CLIENT_RUN.zip` and `D:\VPLC_M19_RUN_NEW.preflight.json` **privately**, not to public GitHub. Independently check original archive bytes through `python -m scripts.m16_provenance_gate --zip <zip> --result <PRIVATE_NEW_RESULT_PATH>`; then have an independent reviewer attest machine, origin, source, wheel, licensing and failback. Exact Mitsubishi CPU/Ethernet module/firmware/manual are separately required for end code certification.

### References

- https://pypi.org/project/pymcprotocol/0.3.0/ (distribution + pinned SHA)
- https://github.com/senrust/pymcprotocol/tree/0.3.0 (upstream source, not executed artifact)
- https://www.mitsubishielectric.com/dl/fa/document/manual/plc/sh080956eng/sh080956engl.pdf (generic SLMP format; device-specific approvals still withheld)
