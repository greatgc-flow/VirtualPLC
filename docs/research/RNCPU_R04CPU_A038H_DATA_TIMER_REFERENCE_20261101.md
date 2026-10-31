# R04CPU CPU built-in Ethernet A038H — offline timer reference

Evidence date: 2026-11-01. Applies to the **R04CPU GX Works3 example**
shown in the Mitsubishi manual, not all RnCPU firmware. This is
**OFFICIAL_MANUAL_REFERENCE_ONLY**, neither a runnable RnCPU emulator
profile nor a physical PLC acceptance result.

## Direct manufacturer provenance and scope

1. [Mitsubishi MELSEC iQ-R Ethernet User's Manual (Application),
   SH-081257ENG-AD](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf)
   printed **pp.329-330** explicitly labels the
   **CPU module (built-in Ethernet port part)** R04CPU Module Parameter
   screen and directs its **Timer Settings for Data Communication**
   application setting to **p.396**. This independent CPU example is
   why the reference is associated with `R04CPU`, not by guessing
   `rj71en71` network-module equivalence.
2. The same official manual, printed **p.396**, specifies *Change/Set
   Timer Value* default **No**, individual default values, input units
   and bounds. Time fields accept integer **1..16383 seconds** or
   **100..16383000 milliseconds** in **100-ms increments** (p.396
   footnote). Alive-check retry count accepts integer **1..99999**.
3. Printed **p.397** specifies
   `response_monitor >= tcp_ulp >= tcp_end >= tcp_resend >= ip_assembly`
   and `tcp_resend == tcp_zero_window`. Equality is allowed in
   this source (do not copy the separate runnable RJ71EN71 stricter
   validation). Some special zero-time retry arrangements are
   separately discussed on p.398; they are NOT accepted by this
   conservative positive-range inspector.
4. [Mitsubishi CPU Module User's Manual SH-082488ENG-E](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh082488eng/sh082488enge.pdf)
   printed **p.685** independently lists **Timer Settings for
   Data Communication = A038H** as a CPU-built-in Ethernet module
   parameter. A038H is a group ID, not evidence of real PLC timing
   behavior or proof of all CPU firmware defaults.

### Default reference matrix (R04CPU GUI example only)

| Key | Factory value | Dimension | Parameter type |
| --- | ---: | --- | --- |
| `tcp_ulp_ms` | 30000 | 30 seconds | TCP stack reference |
| `tcp_zero_window_ms` | 10000 | 10 seconds | TCP stack reference |
| `tcp_resend_ms` | 10000 | 10 seconds | TCP stack reference |
| `tcp_end_ms` | 20000 | 20 seconds | TCP stack reference |
| `ip_assembly_ms` | 5000 | 5 seconds | IP stack reference |
| `response_monitor_ms` | 30000 | 30 seconds | Application reference |
| `alive_start_ms` | 600000 | 600 seconds | Existence-check reference |
| `alive_interval_ms` | 10000 | 10 seconds | Existence-check reference |
| `alive_retries` | 3 | count | Existence-check reference |

The **same numeric values** sometimes appear for RJ71EN71 and L/Q
E71, but this R04CPU subset is sourced separately via the explicit
CPU-built-in application-setting pointer. It neither changes nor
reuses the runnable `EthernetSettings("rj71en71")` implementation.

## Minimal offline usage

~~~python
import json
from virtual_plc.ethernet import inspect_reference_rncpu_data_timers as inspect

print(json.dumps(inspect(), indent=2))  # R04CPU built-in, Change/Set Timer Value = No
print(json.dumps(inspect("R04CPU", {
    "change_set_timer_value": True,
    "timers": {
        "tcp_resend_ms": {"value": 10, "unit": "s"},
        "tcp_zero_window_ms": {"value": 10000, "unit": "ms"},
        "alive_retries": 3,
    },
}), indent=2))
~~~

The `model` field accepts only exact `R04CPU`. Explicit wrong-model
requests, unknown keys, non-object configuration, null timer entries,
invalid units, bool/float numeric entries, out-of-range values,
100-ms increment violations, mismatch between resend/zero-window,
and broken timer inequalities fail closed with `ValueError` before
any network side effect. `None` root (omitted overrides) means
defaults, but explicit nested null is not an omitted value.
Timer overrides require `change_set_timer_value=True`.
An explicitly supplied value equal to its default has
`overridden=True`; no host-kernel timer is applied.

All settings and provenance live in the independent source-of-truth
`virtual_plc/ethernet.py`, exposed through read-only
`reference_catalog()["rncpu_builtin"]["data_timer_reference"]`
and `virtual-plc guide ethernet --json`. The inspector returns
defensively independent JSON-compatible data, with
`physical_hardware_certified=False` and
`simulator_network_affected=False`.

## Boundary, RED→GREEN, and follow-up gates

- TDD tests `tests/test_rncpu_data_timers_reference.py`: positive
  defaults, units/ranges, equality constraints, malformed, unknown,
  negative values, source provenance, defensive copies and no sockets.
  [PR #35](https://github.com/greatgc-flow/VirtualPLC/pull/35).
- **Still UNKNOWN:** full RnCPU family/firmware applicability beyond
  the R04CPU example, actual GX Works3 firmware/UI version-specific
  differences, connection-count budgets per service, real TCP timing
  and retry/end-code behavior, remote RUN/STOP locks and SLMP
  hardware frame parity. Do not promote to runnable RnCPU model.
- No actual PLC link, outbound commands, automatic manufacturer
  system-port bindings, release tag or PyPI publish. Test only offline
  and use independently approved isolated bench hardware for #2.
