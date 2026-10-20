# VirtualPLC M24 — Synthetic fault taxonomy and cross-run metric comparison

## Scope and safety

M24 implements **opt-in** deterministic, loopback-only synthetic fault scenarios and a separate **descriptive** M23 performance report comparator. No simulator default protocol behavior changed. No outbound PLC traffic, vendor end-code certification, official pymcprotocol wheel execution, Windows execution or independent release approval is asserted.

### Scenario catalog (closed, fixed; never accepts network targets)

- `disconnect_before_write` — before-mutation drop, reconnection and verified readback. Does **not** infer safe retry after uncertain commit.
- `delay_then_read` — deterministic 40–200ms delayed read, nonmutation and fault telemetry.
- `read_timeout_then_reconnect` — read-only timeout followed by a new TCP socket and unchanged D-memory check. Avoids automatic retransmission of ambiguous writes.

Seed `0..2^32-1` selects deterministic order. `repeats=1..3`, max 9 scenarios. No arbitrary packet payload, server host, production trace or fault mode is provided. Default server is unaffected. New output directory must be outside source checkout. Captures `console.log`, `report.json`, `junit.xml`, and `MANIFEST_SHA256.json`; all remain noncertifying HOLD evidence. Hashes detect edits, not origin forgery.

```sh
python -m scripts.m24_scenarios --out /tmp/vplc-m24-matrix-fresh --seed 24 --repeats 2 --delay-ms 65
```

### Performance comparison

`m24_compare` accepts only *successful-but-not-certified* M23 JSON, requires `release=HOLD`, no external P0 approvals, unchanged source during each run, and validated p50/p95/p99 plus non-null core measurements. It records original report SHA-256, delta for p50/p95/p99, observed change in **final server RSS**, source equality and environment metadata. Different platform/Python, concurrency, requested duration or cycle budget are INCOMPARABLE; source drift also blocks comparison by default (option `--allow-source-drift` records its explicit use). Exact equality of reports is refused; no claim of independent run identity from SHA alone.

Optional thresholds use an explicit JSON object with nonnegative finite `p95_growth_percent`, `p99_growth_percent`, `rss_growth_kib`; omitted thresholds yield description only. Even with thresholds, an exceedance is *not* a release decision or vendor SLA. A comparable result does not establish environment equivalence beyond available metadata (CPU/thermal/noise conditions are **not** controlled); no memory leak diagnosis is possible.

```sh
python -m scripts.m24_compare --baseline /tmp/m23-base/report.json --candidate /tmp/m23-candidate/report.json --out /tmp/vplc-m24-comparison-fresh
# Optional explicit caller-owned thresholds (descriptive only):
# --thresholds-json /path/to/thresholds.json
```

### MECE JUnit/CASE-ID lineage repair

Existing `tests/test_m4_p0_case_ids.py` and `tests/test_m4_p0_case_ids_v2.py` both attached the same 62 `case_id` properties. M24 preserves **all actual tests** but labels the legacy suite `legacy_case_id`, leaving the maintained v2 suite as **the one canonical P0 CASE-ID owner**. No P0 status was promoted; external P0 backlog remains 16 IDs in `backlog/M20_BACKLOG.json`. `scripts.m24_junit_audit` fails on duplicate test node IDs, duplicate canonical CASE-IDs, failed/skipped results, or mismatch between missing P0 and approved external backlog. No release approval is encoded or inferred.

### Execution evidence (2026-10-20, local Linux)

- Independent local scenario matrix: seed=24, repeats=2, delay_ms=65 => **6/6 observed noncertifying**, source unchanged, console bytes equal to `console.log`.
- Two fresh M23 same-process 4-client, 0.5-second, 20-cycle local soak reports => **COMPARABLE_DESCRIPTIVE**, no thresholds. Original JSON + provenance SHA retained in package.
- Distinct pytest JUnit test nodes: **922 PASS**, additional unittest subtests **5 PASS**; TCP live loopback **45/45**; P0 canonical CASE-IDs **183/199**, missing external backlog **16**, duplicates **0**. All actual test failures in accepted JUnit **0**.
- A batch command exceeding execution time limit was not counted. Subsequent complete, partitioned JUnit runs were audited; canonical CASE-ID ownership was repaired and impacted M4 test group rerun.
- M23 ZIP CRC, manifest SHA-256: 442/442 PASS, no omissions.

### External backlog and acceptance

Keep `backlog/M20_BACKLOG.json` untouched: official `pymcprotocol` 0.3.0 wheel/real client six IDs, exact Mitsubishi CPU/firmware/manual end-code six, Windows validation two, independent approval two. **Release HOLD**; Draft PR only, do not merge `main` or enable Actions.

### Next M25 candidate

- Report schema consistency and byte-exact console evidence verification independent of creator.
- Improved timing isolation and optional repeat-count statistical uncertainty bounds, keeping unsupported hardware conclusions explicitly blocked.
- Address JUnit owner at its source when new tests appear (single owner, cross-check witnesses optional).
