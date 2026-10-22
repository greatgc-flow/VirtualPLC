# M27 — M26 run evidence comparison / anomaly triage (2026-10-22)

## Scope and safety
- Standalone **offline read-only** comparator for one bounded M26 output folder (requested 3–30 M23 loopback runs). Does not access a PLC or establish sockets.
- Rechecks the complete M26 SHA-256 manifest and inventory, bounded file trees, no symlinks, parent and child source fingerprints, M26 JUnit and console, then calls the **existing M25 verifier for each VERIFIED M23 run** and its M25 multi-run analysis.
- Reports per-run p50/p95/p99, server-only RSS initial/final/slope, within-run RSS delta, requests and reconnect/readback status. Min/median/max/MAD are **descriptive observations**, not inferential confidence, safety proof, vendor SLA or memory leak certification.
- Distinguishes (a) invalid/corrupted input => HOLD_INVALID_INPUT, (b) incomplete/failed/timeout run => HOLD_INCOMPLETE_RUNS, (c) source/environment/workload incompatibility => INCOMPARABLE, (d) explicit user-threshold exceedance => OPTIONAL_THRESHOLD_EXCEEDED, (e) comparable description => COMPARABLE_DESCRIPTIVE. **Every outcome keeps release HOLD.**
- Default: **no thresholds**. Explicit optional JSON keys: `p95_growth_percent`, `p99_growth_percent`, `rss_growth_kib`; compares later runs against run 1 and only after complete comparable validation. An exceedance is not approval or an SLA violation.
- Refuses existing/output-inside-input/repository paths. Emits `analysis.json`, console byte-identical `console.log`, pass/fail JUnit and SHA-256 manifest to a fresh external folder. Integrity hashes do not prove execution origin.

## CLI / Windows
```cmd
RUN_M27_LOCAL_COMPARE.cmd "D:\VPLC_M26_EXISTING" "D:\VPLC_M27_NEW"
RUN_M27_LOCAL_COMPARE.cmd "D:\VPLC_M26_EXISTING" "D:\VPLC_M27_NEW_2" "D:\limits.json"
```
```json
{"p95_growth_percent": 20, "rss_growth_kib": 512}
```
Or `python -m scripts.m27_compare --input /tmp/m26 --out /tmp/m27-new [--thresholds-json /tmp/limits.json]`. Requires Python 3.11+. Non-comparable or blocked outcomes exit nonzero and produce a failing JUnit marker.

## Verification and evidence boundary
M27 code and synthetic/mock negative tests were added to Draft PR #1. The full repository cannot be checked out in the current isolated runner, and the original M26 ZIP/11 JUnit originals were **not** supplied. Thus the previous M26 figure of **1,015 historical pytest PASS + 5 subtests + 45/45 TCP and 183/199 P0** is historical, NOT a fresh M27 regression or new independently verified evidence. Run `python -m pytest tests/test_m27_compare.py tests/test_m26_multi_run.py tests/test_m25_replicates.py tests/test_m24_compare.py -q --junitxml=...` from an actual clean checkout, then perform `RUN_M26_LOCAL_REPEATS.cmd` on an isolated Windows localhost machine to exercise real evidentiary paths privately.

## Release and future
**RELEASE HOLD**. External 16 P0 remain unchanged in `backlog/M20_BACKLOG.json`: G0-C 6 real client, G0-E 6 vendor profile, G3 2 Windows and G4 2 independent approval. No auto-CI, Draft PR promotion, main merge, real PLC I/O or public upload of operator artifacts.
Next M28: independent private Windows runner replay and optional cross-bundle provenance/equivalence review; do not claim attested host identity from SHA or platform labels.
