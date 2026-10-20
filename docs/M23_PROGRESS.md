# VirtualPLC M23 — fault/recovery and bounded same-process soak

## Goal and scope

M23 adds two **opt-in** local test workflows without changing the default simulator wire server:
1. A deterministic `FaultPlan` disconnect **before** a write, followed by explicit reconnection, a delayed read of the unchanged word, then a successful write/readback. This is a synthetic fault scenario, **not** proof of a real Mitsubishi PLC failure mode or safe retry of an ambiguously committed request.
2. A short bounded soak using **one separate simulator server PID** across multiple client waves, collecting p50/p95/p99 and per-wave server RSS time-series. This corrects the M22 limitation where each stage starts a new server process. Memory trend is **descriptive only**, not a memory-leak or SLA guarantee.

The implementation is standard-library Python 3.11+, loopback `127.0.0.1` only. The host/IP, outbound PLC connections, production trace replay, payload capture, and fault activation through TCP/configuration are deliberately unavailable. No automatic workload runs on import, GitHub Actions or a background scheduler.

## How to run (explicit opt-in only)

From repository root, provide a **nonexistent** output directory outside the checkout:

```sh
python -m scripts.m23_recovery_soak --out /tmp/VPLC_M23_FRESH --clients 4 --duration 2 --max-cycles 200 --delay-ms 45
```

Windows command prompt:

```bat
RUN_M23_LOCAL_RECOVERY.cmd "D:\\VPLC_M23_FRESH" "4" "2" "200" "45"
```

Limits: 1–8 clients, 0.2–60 seconds requested measurement time, max 1–5000 waves, delay 1–500 ms. **Duration is a soft deadline**: already-running socket operations may complete afterwards, bounded by socket and shutdown timeouts. Each wave runs four D/M requests per client. A workload failure or unavailable RSS yields HOLD/nonzero exit, with sanitized failure type only.

Results: `report.json`, `console.log`, `junit.xml`, `MANIFEST_SHA256.json`. Output is **write-once**; preexisting targets and source-tree destinations are refused. Console text is byte-identical to `console.log`. SHA-256 detects accidental postrun modification; without an external trust anchor it **does not** prove authorship or protect against a coordinated forgery. JUnit contains no P0 CASE-ID and may not close external gates.

## Observed local execution (Linux only)

Run: 4 concurrent clients, 2-second requested duration, at most 200 cycles, injected 45-ms delay. **83 cycles** and **1,328 D/M requests succeeded, zero observed failures**. p50 **348 μs**, p95 **1,557 μs**, p99 **2223 μs**; RSS 83 time-series samples (see run `report.json` for raw values, timestamps, platform). One synthetic disconnect/reconnect verified: dropped write left D100 and memory version unchanged, then a single successful write and readback completed.

As with M22 these figures are **noncertifying local observations**, not transferable to real PLC hardware, production traffic, other CPUs, or Windows. Fixed memory preallocation, process warm-up, short time window, scheduler and allocator effects all influence RSS trends. Never infer leak freedom from a finite positive or negative slope.

## Verification

- M23 newly introduced pytest: **42 PASS**.
- Unmodified M22 regression test inventory rerun on M23 source: **755 PASS + 5 unittest subtests**.
- New combined rerun: **797 unique pytest PASS + 5 subtests**, including **45/45 loopback TCP**, no duplicate test node IDs or CASE-ID values.
- **183/199 P0 locally observed** in these JUnit sources; the remaining **16 external-dependent P0 cases** have not been promoted.
- Fault path after midrun source mutation, missing sub-scenario, timeout, output reuse, manifest alteration and forged release state is fail-closed.
- Reproducible local source and run fingerprints: `M23_AUDIT.json` and `M23_MEASURED_FINAL/*` in the M23 handoff ZIP (not published to the public repository).

## Externally blocked tasks

Keep `backlog/M20_BACKLOG.json` unchanged: official `pymcprotocol` 0.3.0 wheel execution, Mitsubishi vendor error/CPU/firmware manual verification, Windows environment runs, and independent release sign-off. These remain backlog **HOLD** until new external evidence arrives. GitHub Draft PR #1 stays unmerged; automated CI remains disabled.

## Next M24

- Add opt-in scenario taxonomy for timeout, reconnect and high-percentile latency with bounded deterministic seeds, retaining one simple core.
- Build cross-run metric comparison that reports changes without asserting SLAs or memory-leak proof; keep measurement environments explicit.
- Establish reproducible evidence lineage / source drift checks and compact failure reproduction recipe, without mixing external gate approval.
