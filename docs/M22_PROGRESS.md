# VirtualPLC M22 — bounded loopback soak and isolated-server memory metrics

## Scope and trust
- Draft PR only; do not merge into `main` or enable GitHub Actions without explicit direction.
- One fixed endpoint: **127.0.0.1**. No external PLC target or forwarding.
- Opt-in only. No background monitor, scheduler, CI, or implicit load on import.
- `scripts/m22_soak.py` runs a separate local `python -m virtual_plc` server process for each of up to 3 stages, at most 8 concurrent load clients (< server MAX_SESSIONS=16).
- Every client writes then reads disjoint D word/M bit ranges and compares exact bytes; no write races. 4 requests/iteration. No C#/.NET dependency.
- Raw payload is *not* retained in evidence. Source hashes, report, JUnit and exact console transcript are SHA-256 chained in the output manifest. Existing output dir forbidden; source tree output forbidden.
- RSS is collected **for server child PID only**: Linux `/proc/{pid}/status:VmRSS` and Windows `GetProcessMemoryInfo` (not executed on Windows here). No psutil dependency. On unsupported environment, RSS fields are null and status is HOLD.
- p50/p95/p99 use exact **nearest-rank** latency in **microseconds**, measured client-side around sendall+full reply. Not wire-only and not independent PLC timings.
- RSS slope (KiB/minute) is descriptive regression over samples. In very short runs it can be meaningless or high because of process warmup. No leak-free, stability, SLA, production or vendor claim. Each stage is a fresh server process; comparison across stages is **not** a same-process long-duration leak test.

## M22 measurements performed on Linux local runner

| Clients | Requests OK | Failed | p50 μs | p95 μs | p99 μs | Server RSS Δ KiB |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 600 | 0 | 27 | 113 | 224 | +68 |
| 4 | 2,400 | 0 | 115 | 423 | 981 | +128 |
| 8 | 4,800 | 0 | 551 | 1,347 | 1,937 | +168 |

These are **local observational values**, not performance targets; consult `evidence_m22/soak_150/report.json` for aggregate latency measurements, peak RSS, throughput and source fingerprints. Memory changes depend on Linux scheduling and process initialization.

## TDD / regression outcome
- M22 isolated new tests: **59 PASS** (included in core regression).
- Whole regression: **755 distinct pytest PASS + 5 unittest subtest PASS**, including **45 loopback TCP** cases.
- Exactly 183/199 P0 CASE-IDs locally observed in current JUnit; remaining 16 unchanged in `backlog/M20_BACKLOG.json` (G0-C/G0-E/G3/G4). No claim of official wheel, Windows, vendor error-code validation or independent acceptance.
- JUnit inputs, unique node IDs, CASE-ID inventory and hashes: `evidence_m22/M22_AUDIT.json`.

## How to run
From the repo root (Python >=3.11):

```shell
python -m scripts.m22_soak --out /tmp/VPLC_M22_FRESH --clients 1,4,8 --iterations 150
```

Windows command prompt from repo root:

```bat
RUN_M22_LOCAL_SOAK.cmd "D:\VPLC_M22_FRESH" "1,4,8" "150"
```

The output folder **must not exist beforehand**. Do not store evidence inside a public Git checkout. Nonzero exit or a missing RSS measurement is a HOLD. The `MANIFEST_SHA256.json` binds result JSON, literal console transcript and JUnit.

## M23
- Extend the independent workload engine to multiple fault-cycle scenarios (opt-in delay/disconnect -> retry/recovery), detect server exit and resource starvation without manufactured SLA thresholds.
- Add duration-bounded long-running soak and leak-trend *research*; report time series and confidence limitations, with acceptance decision manual.
- Existing external evidence/Windows/vendor/signoff tasks remain unchanged in backlog. Maintain Draft PR, main and CI policies.
