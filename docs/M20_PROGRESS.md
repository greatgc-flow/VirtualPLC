# VirtualPLC M20 — External backlog and optional deterministic fault injection

**Date:** 2026-10-20. **Release: HOLD.** **GitHub:** `greatgc-flow/VirtualPLC`, Draft PR #1; do not merge `main` or activate Actions without explicit authorization.

## Decision and backlog

Per user direction, stop blocking independent work on the 16 external evidence requirements. See `docs/M20_BACKLOG.md` and `backlog/M20_BACKLOG.json` for the complete *owner role → dependency → original evidence → acceptance → resume trigger* chain. These 16 cases are grouped into G0-C (6), G0-E (6), G3 (2), G4 (2). They remain **unverified**; the archive contains no real Windows wheel, PLC vendor profile, or independent sign-off.

## Delivered internally — BL-INT-001

- New `virtual_plc/faults.py` provides optional, deterministic, bounded, in-process `FaultPlan`. Supported steps: `pass`, `disconnect`, and `delay` (1..500 ms). At most 256 steps per plan; no infinite loops or remote network configuration.
- `virtual_plc/server.py` applies a plan after a full, route-accepted 3E frame but **before any D/M memory operation**. Disconnect prevents a state mutation. Delay affects the one current client worker. Unrecognized route/header never consumes the next step.
- `virtual_plc/telemetry.py` tracks numeric event names `fault_disconnect` and `fault_delay`; it never records client IP, frame payload or PLC register values.
- Default `fault_plan=None` is fully backward compatible; no TOML/CLI API for fault injection. The TCP listener remains hard-restricted to loopback `127.0.0.1`. Physical Mitsubishi PLC connection functionality was not added.
- Previous M7 mock omitted the optional new field. M20 adapted `Handler` to tolerate the absent optional property, restored CASE-0068 and reran the associated regression. Initial failing JUnit is retained as a diagnostic artifact; only subsequent completed rerun is used for the final gate tally.

**Determinism limit:** The globally shared plan is consumed in order of *completed frames reaching the plan lock*, not by upstream logical timestamps. Across concurrent clients, their mapping to particular steps is scheduling-dependent. If per-client deterministic association is required, serialize clients in the harness.

## Actual local test execution, no overlap

| JUnit | pytest PASS |
|---|---:|
| `M20_CORE_A.xml` | 122 |
| `M20_CORE_B.xml` | 81 + 5 separate unittest subtests |
| `M20_EVIDENCE.xml` | 291 (includes 24 M20 fault-plan tests) |
| `M20_GOVERNANCE.xml` | 7 (exact backlog 16 case-ID governance) |
| `M20_TCP_0.xml`, `M20_TCP_1.xml` | 16 + 16 |
| `M20_TCP_2A.xml` ... `M20_TCP_2D.xml` | 4 + 4 + 3 + 2 |
| **TOTAL pytest** | **546** |

The 10 completed JUnit sources report no pytest failure/error/SKIP, and no duplicate pytest node ID or duplicate P0 CASE-ID property. **160 unique P0** are directly observable in the M20 JUnit files. The separately verified historical local P0 figure remains **183/199**, independently unattested. Remaining **16 are external HOLD**. The newly added tests are not new manufacturer-certified P0s, and no automatic release approval was issued.

The first unsplit TCP group-2 attempt was terminated before producing valid JUnit and is preserved as `M20_TCP_2.log`. Independent subgroups A–D completed all 13 remaining wire cases, so the counted TCP total is 45/45.

## Following internal work

**M21 next:** BL-INT-002, make a one-command, non-destructive loopback smoke/evidence runner that fails closed, mirrors all console bytes into files and records exact source/test hashes. The internal stress/soak test (BL-INT-003) and scenario runbook (BL-INT-004) follow. External dependencies resume only on original evidence, never on another synthetic test.
