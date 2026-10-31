# FX5-ENET alive-check timer settings — reference-only verification

This document is a source-scoped comparison for the **FX5-ENET
expansion Ethernet module**, not the FX5 CPU built-in Ethernet port.
No vendor hardware, program, or network traffic was accessed.
Track against GitHub [#14](https://github.com/greatgc-flow/VirtualPLC/issues/14)
and [#2](https://github.com/greatgc-flow/VirtualPLC/issues/2).

## Official manufacturer evidence

[Mitsubishi SH-082026ENG-H FX5 Ethernet Module User's Manual,
printed page 70 (PDF page index 71)](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082026eng/sh082026engh.pdf)
contains the GX Works3 Operational Setting screen and parameter table.
The PDF page was also visually checked.

| Setting | Factory value | Permitted range / type | Implementation |
| --- | --- | --- | --- |
| Change/Set Timer Value | No | No / Yes | REFERENCE_ONLY |
| Destination Alive Check Start Interval Timer | 600 s | Integer s: 1–16383; integer ms: 100–16383000 | REFERENCE_ONLY |
| Destination Alive Check Interval Timer | 10 s | Integer s: 1–16383; integer ms: 100–16383000 | REFERENCE_ONLY |
| Destination Alive Check Resend Count | 3 times | Integer 1–32767 | REFERENCE_ONLY |

Important distinction: the vendor page lists *seconds* and
*milliseconds* as separate selectable units. It does **not**
independently establish a 100ms step when the unit is milliseconds.
Avoid inventing extra constraints or making the FX5 CPU built-in
inherit this expansion-module-specific timer list.

## Very Simple read-only verification

~~~python
import json
from virtual_plc.ethernet import inspect_reference_fx5_enet_alive_timers

print(json.dumps(inspect_reference_fx5_enet_alive_timers(), indent=2))
result = inspect_reference_fx5_enet_alive_timers({
    "change_set_timer_value": True,
    "start": {"value": 600, "unit": "s"},
    "interval": {"value": 250, "unit": "ms"},
    "retry": 3
})
print(json.dumps(result, indent=2))
~~~

The value of `change_set_timer_value` is false by default. To
supply any explicit timer override, set it to true. A value exactly
equal to its factory default still appears as `overridden=true`
when explicitly supplied. Omitted fields retain defaults. Inputs
like null timer values, empty arrays, boolean numeric values,
extra keys, unsupported units and values outside the documented
ranges are rejected with `ValueError`. The root `None` or empty
dictionary means **no overrides**.

The result records milliseconds consistently for start/interval and
a plain retry count. Its manufacturer source and individual values
are visible via `reference_catalog()["fx5_enet"]`, also projected
by `virtual-plc guide ethernet --json`; source metadata and
bounds are not duplicated in executable runtime.

This API **never opens a socket or touches the Server**. The result
states `status=OFFICIAL_MANUAL_REFERENCE_ONLY`,
`simulator_network_affected=false` and
`physical_hardware_certified=false`.
This is not a simulator of Ethernet keepalive retransmissions,
OS socket options, an FX5 protocol execution or a physical PLC test.

## Verification and remaining gates

Independent tests `tests/test_fx5_enet_alive_reference.py`
verify defaults, both units and boundaries, wrong types, partial
overrides, immutability, reference catalog projection, unrelated
Q/L/R and FX5 CPU model isolation, and the no-socket contract.
Check the exact branch CI before treating the implementation as
accepted; distinguish PR candidate results from post-merge CI.

P1 remaining: actual module firmware/version differences, real
connection timeout behavior and end-code policy, physical test
captures, and a separate FX5 CPU built-in parameter contract.
No PyPI release.
