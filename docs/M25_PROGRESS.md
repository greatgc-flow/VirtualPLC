# M25 — Evidence intake and bounded repeated-observation analysis

Status: **IMPLEMENTED + LOCALLY OBSERVED; RELEASE HOLD**. Updated 2026-10-21.

## Scope and boundaries

- Add `scripts/m25_replicates.py` as a **separate read-only input auditor and aggregator** for M23 local `report.json` + `console.log` + `junit.xml` + `MANIFEST_SHA256.json`.
- Reject symlinks, unexpected/incomplete inventories, excessive input sizes, bad manifests, altered payloads, JUnit failures/skips/duplicates, contradictory report status, inconsistent recovery outcomes, ill-formed RSS time-series and request counts.
- Require at least three *distinct* reports by default. **Same OS/Python version, source fingerprint, workload and injected fault delay** are required; mismatches become `INCOMPARABLE`, not a silent performance verdict.
- Report median, min, max, and median absolute deviation (MAD) across raw run-level measurements. The values are **descriptive only**; no confidence interval, p-value, vendor SLA, or memory-leak conclusion is calculated or implied.
- Write one fresh output folder outside source tree. Store `summary.json`, `console.log`, and SHA-256 manifest. Console output equals `console.log` byte-for-byte.
- Explicit limitation: locally computed SHA-256 **does not prove independent origin**, signed machine identity or reproducibility under production load. No code may approve its own release.
- Production PLC endpoints are never used. Existing M20 external 16 P0 remain in backlog; no code-changing vendor support is claimed.

## Usage (Python >= 3.11, from repository root)

```bash
python -m scripts.m23_recovery_soak --out /tmp/vplc_run_1 --clients 2 --duration 0.6 --max-cycles 500
python -m scripts.m23_recovery_soak --out /tmp/vplc_run_2 --clients 2 --duration 0.6 --max-cycles 500
python -m scripts.m23_recovery_soak --out /tmp/vplc_run_3 --clients 2 --duration 0.6 --max-cycles 500
python -m scripts.m25_replicates --inputs /tmp/vplc_run_1 /tmp/vplc_run_2 /tmp/vplc_run_3 --out /tmp/vplc_m25_output
```

All output paths must **not exist** and must be outside the Git worktree. The option `--min-runs` can change the acceptance floor within 2..30, but the default is 3, and fewer runs have limited evidential usefulness.

## Verified local evidence

- Three actual Linux loopback M23 runs, same requested 2 clients / 0.6 seconds / 500 max cycles / 35ms fault. All completed with successful disconnect-before-write/reconnect/readback checks.
- Requested socket operations observed: 216, 224, 224 successful, zero failed. Per-run p95: 811, 651, 571 µs; **median p95 651 µs, MAD 80 µs**. These are run-level estimates and must not be pooled as 664 independent observations.
- Samples taken on separate isolated **same-process-within-each-run** server instances. None proves memory-leak freedom, actual Mitsubishi device equivalence or Windows behavior.
- M25 synthetic test suite: 40/40 PASS. Full local replay: 962/962 pytest PASS + 5 unittest subtests. TCP loopback 45/45 PASS.
- Unique P0 CASE-ID audited from eight actual JUnit inputs: **183/199 observed**, 16 precisely match `backlog/M20_BACKLOG.json`, zero duplicate CASE-ID or test node. Release HOLD.

## Deferred to later backlog / M26

- Source-identity and Windows/native client/vendor proof remain external dependencies; do not auto-upgrade P0.
- Optional M26: stable multi-run one-click wrapper with explicit run count and duration caps, crash-safe evidence, source-stability evidence, and all output paths outside repo. Keep approval opt-in.
- Independent reviewer should inspect local machine provenance and raw reports. Never present M25 self-hash checks as attestation.
