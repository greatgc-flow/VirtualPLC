# VirtualPLC M20 — Nonblocking, evidence-based backlog

**Policy:** All 16 external P0 cases are **BLOCKED / RELEASE HOLD** until their real external evidence exists. An external dependency never prevents further independent internal development or local regressions. Never use fabricated or synthetic evidence to complete an external case. This project's GitHub repository is public; Windows/operator data stays private.

| Backlog | Gate | Cases | Dependency | Trigger |
|---|---|---:|---|---|
| BL-EXT-CLIENT | G0-C | 6 | Original SHA-verified `pymcprotocol==0.3.0` wheel and real Windows loopback capture | Original private `M14_CLIENT_RUN.zip` + preflight |
| BL-EXT-VENDOR | G0-E | 6 | Exact Mitsubishi CPU/module/firmware and relevant manual page | Precise vendor profile received |
| BL-EXT-WINDOWS | G3 | 2 | Native Windows 3.11+ run and environment evidence | Actual native test JUnit + platform details |
| BL-EXT-REVIEW | G4 | 2 | Independent acceptance, licensing, no production traffic and failback | All prerequisite evidence passes and reviewer signs |
| **TOTAL** | | **16** | | |

Full per-group owner roles, case IDs, acceptance conditions and next actions: `backlog/M20_BACKLOG.json`. The local historical P0 183/199 is NOT a released or independently attested result. Do not count historical duplicate test observations twice.

## Internal execution policy

External items stay in the backlog; continue with internal items in value / risk order. Stage M20 implements **BL-INT-001: optional deterministic fault injection** for CIM/EAP connection test scenarios, with the network surface unchanged. This is a new capability, not a reason to increase the 183 P0 figure.

Remaining internal plan: one-command evidence runner (BL-INT-002), bounded concurrency/resource soak (BL-INT-003), scenario sequencing and operator runbook (BL-INT-004). Always record precise local test results and negative paths.

## In-process fault injection semantics

```python
from virtual_plc.faults import FaultPlan
from virtual_plc.server import Server

plan = FaultPlan([
    {'action': 'pass'},
    {'action': 'delay', 'delay_ms': 80},
    {'action': 'disconnect'},
])
with Server(('127.0.0.1', 0), fault_plan=plan) as server:
    # Start server. Connect only to the assigned local ephemeral port.
    ...
```

A valid incoming 3E frame passing header/routing checks consumes one plan entry before memory dispatch. `disconnect` drops the connection **without changing D/M memory**; `delay` blocks only the current worker. Bad framing/route consumes no step. All steps are copied, finite (max 256), time-limited (max 500 ms per delay) and thread-safe; after exhaustion the server behaves normally. Default remains `fault_plan=None`. There is no CLI or TOML fault-control key, no remote mutation, no PLC network forwarding. Packet contents are not logged by fault injection; telemetry tracks only numeric counters.

**Concurrency limitation:** Global step assignment is ordered by frame receipt/lock scheduling across workers, not by any client's logical timestamp. Do not use concurrent sessions if deterministic association of a particular step with a specific client is required.
