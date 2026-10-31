# RnCPU CPU built-in Ethernet — remote RUN/STOP opening-method preflight

Evidence snapshot: 2026-11-01 (Mitsubishi documentation only). This is a
**reference-only, offline configuration risk inspector**, not a hardware test,
a MELSOFT implementation, or a new runnable VirtualPLC hardware profile.
The CPU's **built-in Ethernet** is not the RJ71EN71 Ethernet network module
and not the separate RnENCPU network part.

## 1. Direct manufacturer evidence and scope

- [Mitsubishi MELSEC iQ-R Programmable Controller CPU Module User's Manual
  SH-082488ENG-E](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh082488eng/sh082488enge.pdf),
  printed **p.3 Design Precautions**: when externally changing CPU status
  via remote RUN/STOP, choose **Do Not Open by Program** for
  `Opening Method`. Choosing **Open by Program** can cause remote STOP to
  close the communication line; the external device then cannot send
  remote RUN over that closed line. This is an operational warning,
  *not* documentation of the factory opening method.
- The same official CPU manual **Appendix 8 pp.684–685** maps
  **Basic Settings → Own Node Settings → Opening Method** to parameter
  group **A031H**. The adjacent `External Device Configuration` also
  references A031H/A032H: the number is not unique to only one field.
- That CPU manual separately lists **Application Settings → Timer Settings
  for Data Communication** as parameter **A038H**. The identifier confirms
  where a CPU-side timer setting belongs, but does **not** establish
  CPU/firmware-specific defaults, ranges, running behaviors, or that
  RJ71EN71 timer constants apply to RnCPU.
- Older [iQ-R Ethernet Application SH-081257ENG-AD](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf)
  includes module-related defaults and multiple interface families.
  No RJ71EN71 or RnENCPU *network-part* timer is copied into RnCPU
  *CPU built-in* runtime settings on the basis of shared editor pages.
- Vendor-system-port metadata 5005/5006/5007 remains separately scoped
  in `reference_catalog()["rncpu_builtin"]`; this preflight never
  binds these ports.

## 2. Safe reference state machine (not a vendor runtime model)

| User-supplied opening_method | reconnect_risk_status | Meaning |
| --- | --- | --- |
| omitted / None | `UNKNOWN` | No CPU config read; do not infer factory value |
| `open_by_program` | `DOCUMENTED_REMOTE_RUN_RECONNECT_FAILURE` | Manufacturer warns remote STOP may close the line, preventing a following remote RUN |
| `do_not_open_by_program` | `NO_SPECIFIC_OPENING_METHOD_RISK_DOCUMENTED` | Matches vendor recommendation, but other reconnect risks remain and success is NOT guaranteed |

Both explicit choices must be spelled exactly. Empty strings, null-like
strings, lists, booleans, integers and other hardware names fail validation.
No underlying hardware or simulated PLC state is changed.

## 3. Example from a source checkout

~~~python
import json
from virtual_plc.ethernet import inspect_reference_rncpu_remote_opening as inspect

print(json.dumps(inspect(), indent=2))  # UNKNOWN: no factory guess
print(json.dumps(inspect("open_by_program"), indent=2))  # documented risk
print(json.dumps(inspect("do_not_open_by_program"), indent=2))
~~~

All results include exact `source`, `gxworks3_path`, `parameter_id`,
`recommended_opening_method`, `factory_default=None`,
`remote_run_after_stop_guaranteed=False`,
`physical_hardware_certified=False`, and
`simulator_network_affected=False`. The metadata is sourced from
`virtual_plc/ethernet.py` and independently deep-copied into
`virtual-plc guide ethernet --json` under
`reference_only_models.rncpu_builtin.remote_opening_reference`.

## 4. Verification boundary and follow-up gates

Tests: `tests/test_rncpu_remote_opening_reference.py` covers 23
positive/negative cases, no socket operations, JSON projection, source
immutability and hardware separation. TDD RED/GREEN and complete CI
evidence are recorded in [PR #34](https://github.com/greatgc-flow/VirtualPLC/pull/34)
and [issue #14](https://github.com/greatgc-flow/VirtualPLC/issues/14).

**UNKNOWN / HOLD** (not invented): RnCPU CPU-specific editable timer values,
connection budgets by exact CPU revision, firmware support boundaries,
remote-control handshake/ownership and error codes, physical PLC packet
behavior, reconnect timing and SLMP frame/device parity. They require
model-specific manufacturer verification and isolated physical bench
evidence (#2, #14, #22). No PyPI or production hardware changes.
