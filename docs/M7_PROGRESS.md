# VirtualPLC M7 — traced P0 development and interoperability gate

**Date:** 2026-10-20. **Status:** RELEASE HOLD. Source branch only; do not merge without approval.

## What was physically checked

- M6 handoff ZIP CRC PASS; its 125 manifest-listed files have matching SHA-256. GitHub source was previously verified at M6 HEAD `85b31bc6f5f3200a14fdbfcbb94dab4ce5637c9a` before M7 changes.
- M7 local Linux Python 3.13.5: 161 baseline tests (plus 5 unittest subtests), 35 M5 tests, 20 M6 tests, 43 ordinary TCP tests, 2 isolated TCP fuzz tests and 3 M7 tests = **264 pytest successes**. NOTE: the 43+2 TCP tests were run separately to avoid a long all-in-one execution; all JUnit files are in the evidence directory.
- Exact P0 **176/199 observed local PASS, 23 NOT_RUN, 0 FAIL, 0 SKIP**; original 208-case catalogue SHA256 unchanged: `31415a1c0813aa28364883a24e006c5d8d4ff5ad8db171409ec4551a02f2fa7f`.
- Three new P0 cases: CASE-0054 replay metadata without PLC value logging, CASE-0068 deterministic send failure with resource release, CASE-0126 real TCP slow receiver and competing client service. All named cases have JUnit `case_id` properties. Other tests are excluded from P0 counting if they have no exact CASE-ID.
- 50 iterations each of 100 word reads and aggregate 1000 word reads measured on one Linux loopback host. Output includes p50/p95/p99 and RSS. **These are measurements, not a service guarantee and not multi-OS evidence.**
- `pyproject.toml` Python lower bound checked as >=3.11, consistent with `tomllib` (no change needed).

## Open blockers

- The official `pymcprotocol==0.3.0` wheel remains **NOT INSTALLED**. The sandbox's `pip download` could not resolve its configured Python package host; secondary download was unavailable. Official wheel SHA256 advertised by PyPI: `614217d43fbf8d9e409c1928993cbb4339d17828c1002c1766ce900aaee12dd6`. No actual client→server PASS has been claimed.
- Vendor-specific model/firmware end-code values are **UNVERIFIED**. Simulator code `0xC059` is a placeholder and may differ from Mitsubishi hardware. G0-E remains open; do not promote eight associated cases.
- No Windows execution, GitHub Actions remote run or independent release signoff. CI workflow intentionally remains a non-active template; main is unchanged.
- CASE-0121 nondefault supported route remains an opt-in design decision and NOT_RUN. Routes not configured are rejected.
- M7 follows existing protocol max 960 points **per request**; 1000 logical words in benchmark are explicitly split 960+40. This does NOT support a single request of 1000 points. CASE-0132 remains a manual/open gate until independent platform measurement and accepted interpretation.
- CASE-0047, CASE-0129 and all other manual requirements remain NOT_RUN as complete release or cross-platform oracles, even though local measurements exist.

## M7 residual P0, exact IDs

From M6 list, remove only `CASE-0054`, `CASE-0068`, `CASE-0126`, leaving **23** cases across G0-E, G0-C, G3, G4 and G1. M7 JUnit audit rejects duplicates. Release gates remain HOLD.

## Test reproducibility

```sh
# Python 3.11+ and pytest installed; no private network use.
MC_SIM_ADAPTER_MODULE=virtual_plc.test_adapter python -m pytest tests/test_m7_runtime.py -q
PYTHONPATH=. python scripts/benchmark_m7.py --iterations 50 --out evidence/m7_benchmark.json
PYTHONPATH=. python scripts/run_m7.py --output evidence/m7_rerun
python scripts/gate_report.py --junit evidence/m7_rerun/combined.xml --out evidence/m7_rerun/gate.json
```

The optional all-in-one runner duplicates console output byte-for-byte to `evidence/m7_rerun/console.txt` and prints it. It deliberately fails if any test suite fails, exact CASE-ID count changes or JUnit identity integrity fails. It never approves a production release.

## Improvement / feedback loop

Failed test -> isolated reproduction / SHA-256 evidence -> validated requirement+risk+CASE-ID -> minimal fix -> domain / wire / fault -> platform + vendor client -> independent gate review. Do not bypass any step or turn NOT_RUN into PASS by reclassifying a case.

## Public repository safety

Only synthetic data, loopback network, no real PLC links, no production addresses, no customer traces, no private keys or workstation paths, no manufacturer certification claims. Changes belong in Draft PR #1 until reviewed.
