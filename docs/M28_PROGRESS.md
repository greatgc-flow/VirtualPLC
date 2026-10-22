# M28 — Offline cross-bundle provenance and descriptive comparison (2026-10-22)

## Goal and state
**Source, 28 synthetic unit tests, Windows wrapper and documentation implemented; full-checkout/Windows evidence replay remains NOT_RUN; RELEASE HOLD.**

M28 compares **2..12 existing M26 evidence folders**, each containing 3..30 bounded M23 loopback observations. It **never contacts a PLC, opens a socket or changes input files**. The default baseline is the first specified bundle. Every input is validated by the unchanged M27 analyzer (which calls M26 SHA inventory checks and M25/M23 original JUnit, manifest, source, recovery, and metrics verification) before any comparison is performed. All original evidence stays privately on the machine.

## Recursive MECE status / integrity
1. **Invalid/altered input**: reject tampering, missing/unregistered files, symlinks, unsafe size, forged status, JUnit contradictions, duplicate/overlapping input folders, duplicate parent M26 report digests, or reused M23 child reports; CLI records HOLD_INVALID_INPUT.
2. **Incomplete or internally incomparable input**: reject selecting only successful repeats when any M26 run failed or timed out. Report HOLD_INPUT_NOT_COMPARABLE, no cross-bundle metrics.
3. **Environment/source/workload mismatches**: source digest, platform/Python, concurrent clients, duration, cycle budget, fault delay, timeout, and (by default) repetition count; INCOMPARABLE, no threshold interpretation. Optional --allow-unequal-runs relaxes **only** the repetition count and records each affected bundle.
4. **Missing measurements**: if a required descriptive statistic is unavailable, mark INCOMPARABLE. Metrics are run-level p50/p95/p99, *server-only* RSS initial/final/slope, within-run RSS delta, and requests.
5. **Eligible comparable inputs**: compute **differences between the per-run medians of each M26 bundle**, not pooled socket samples. Results are DESCRIPTIVE_CROSS_BUNDLE with release **HOLD**, no confidence/causality/SLA/leak proof.
6. **Explicit-only anomaly thresholds**: opt-in JSON accepts M24-compatible keys p95_growth_percent, p99_growth_percent, rss_growth_kib. Comparisons are against the **first bundle median** and never automatic certification. Exceedance => OPTIONAL_THRESHOLD_EXCEEDED, release **HOLD**.

SHA-256 here is integrity, **not trusted identity, signing or independent run provenance**. Comparing OS and Python labels cannot establish same Windows host, CPU/NUMA, OS patches, measurement conditions, vendor fidelity or statistical significance. Duplicate-content detection rejects obvious copied evidence but does not prove independence otherwise.

## Windows CMD (Python >= 3.11)
All input folders must be **existing original M26 outputs** and destination must not exist:

    RUN_M28_COMPARE.cmd "D:\VPLC_M28_NEW" "D:\VPLC_M26_A" "D:\VPLC_M26_B"

Advanced CLI (call from repository root):

    py -3.11 -m scripts.m28_cross_bundle --inputs "D:\VPLC_M26_A" "D:\VPLC_M26_B" --out "D:\VPLC_M28_NEW_2" --thresholds-json "D:\VPLC_LIMITS.json"

Optional --allow-unequal-runs is **off** by default. Example user-owned, non-SLA policy:

    {"p95_growth_percent":20,"p99_growth_percent":25,"rss_growth_kib":512}

M28 always writes a new analysis.json, exact-byte stdout mirror console.log, pass/fail junit.xml, and MANIFEST_SHA256.json; it checks the complete output inventory/hash as well as agreement among JSON, console and JUnit. Comparable descriptive results exit 0; all other statuses exit nonzero and have a JUnit failure marker.

## TDD and provenance of observations
- **Current-turn isolated synthetic harness**: 28/28 test cases completed PASS, 0 errors/failures/skips, captured JUnit SHA-256 f8224f83ff9daeaab56716ec7b38b46226b9f2cf3b8b73442afca51086a7564d. This run tested **M28 code with deliberately stubbed M24/M26/M27 dependency functions**, not the full GitHub worktree or authentic M26 artifacts. It cannot validate upstream verifier behavior or Windows compatibility.
- GitHub tests/test_m28_cross_bundle.py exercises the same synthetic test logic with targeted upstream monkeypatches. The newly uploaded remote file and full connected-project suite have **not been directly executed**.
- M26's historical 1,015 pytest, 5 subtests, TCP 45/45 and unique P0 183/199 are carried forward as **previously recorded observations**, not new M28 verification. Original M26 operator ZIP and 11 source JUnit originals were not available; therefore no claim of checking their CRC or provenance now.

## HOLD and next milestone
External P0: **G0-C 6, G0-E 6, G3 2, G4 2 = 16 unresolved**. Baseline test catalog remains 208 unique CASE IDs (199 P0), **no new P0 ownership or approval credited**. Public GitHub holds code, synthetic tests and docs only; no private Windows/operator output is committed. Draft PR #1 remains unmerged, workflow automation disabled.

**M29 next:** reproduce M27/M28 against at least two *independently executed original private Windows M26 bundles*, run and hash source/JUnit/CRC with a clean exact-HEAD checkout, report source/environment/workload drift, and run grouped regression without counting timeouts as PASS. Continue internal analysis without waiving external approvals.
