# M26 — bounded multi-run local evidence orchestration (2026-10-21)

## Scope and status

- One optional command runs 3..30 independent M23 *loopback-only* subprocesses. The actual remote Mitsubishi PLC and any remote IP remain strictly inaccessible; no network configuration is added.
- Each M23 run retains its own immutable-by-policy (hash-protected, **not cryptographically signed**) evidence directory; M25 independently reconciles run folders and descriptive statistics.
- A fresh destination **outside the repository** is required. Existing directories, symlinks, unsafe sources, invalid bounds or failed measurements are rejected; no evidence overwrite, no automatic retry of uncertain writes.
- On unexpected interruption, timeout, child failure or source drift, the run is **HOLD**, writes partial evidence, retains child logs and emits failing JUnit. Timeout kills the local process group, including its child server.
- `console.log` is exact byte-for-byte output of the program's visible stdout. Each subprocess's output is separately stored as `run_stdout/NN.log`.
- `MANIFEST_SHA256.json` inventories every recorded file, excluding itself; `verify_output()` detects missing, modified and unregistered files. No signatures, trusted origin attestation or independent review is implied.

## Usage (Windows; clean working copy, Python >=3.11)

```cmd
RUN_M26_LOCAL_REPEATS.cmd "D:\VPLC_M26_NEW" 3 2 0.5 30
```

Alternative CLI (from repository root):

```cmd
py -3.11 -m scripts.m26_multi_run --out "D:\VPLC_M26_NEW" --runs 3 --clients 2 --duration 0.5 --max-cycles 30 --delay-ms 20 --timeout 30
```

Defaults are 3 runs, 2 clients, 0.5 seconds, max 30 cycles, 20ms injected fault delay, and 30-second timeout per run. Bounded options: runs 3..30, clients 1..8, duration 0.2..60s, cycles 1..5000, delay 1..500ms, timeout 5..240s and at least duration+4s. Values are options, not defaults for production. Repeated execution must choose a **new** destination.

## Evidence and observed result (Linux local, no external certification)

- M26 new TDD: **53 pytest PASS**. Full M26 group-level regression: **1,015 distinct pytest PASS**, **5 additional unittest subtests PASS**, loopback TCP **45/45 PASS**. Source code modification limited to M26 files; legacy tests remain intact.
- Independent CASE-ID parser over **11 completed JUnit files**: observed P0 **183/199**, external backlog **16**, duplicate node/CASE-ID **0**, test failures/skips **0**. One earlier combined TCP batch hit execution limit; it is **excluded** and was replaced by completed 5-case groups.
- Actual local M26 CLI execution: 3/3 M23 processes `VERIFIED`, report status `OBSERVED_NOT_CERTIFIED`, p95 observations **613/521/521 microseconds**; main console stdout exactly equals stored `console.log` (218 bytes). These are descriptive observations, **not** statistical certainty, SLA proof or memory-leak-free certification.
- M20 external backlog unchanged in `backlog/M20_BACKLOG.json`: G0-C 6, G0-E 6, G3 2, G4 2. Never mark them PASS without original independently reviewed evidence.

## Release decision

**HOLD.** Draft PR only; `main` remains unchanged and Actions must not be re-enabled without permission. No trusted origin proof, physical PLC endorsement, native Windows execution or approved failback policy. Do not publish user-machine evidence/logs on public GitHub.

## Next

M27: optional safe batch comparison dashboard/structured reports and cross-run anomaly triage, without creating performance thresholds; further platform/client/vendor checks remain externally blocked. See `M27_HANDOFF.md`.
