# R04CPU CPU built-in Ethernet — offline multi-entry GX Works3 configuration lint

Evidence date: 2026-11-01 (KST). **This is developer-authored static
preflight, not a Mitsubishi GX Works3 project validator or real PLC
certification.** It never opens a socket, reads PLC memory or enables
a runnable RnCPU profile.

## 1. Manufacturer boundary and 2026-10 revision gap

- **Validated reference edition:** [Mitsubishi Ethernet User's Manual
  (Application) SH-081257ENG-AD](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf):
  printed **pp.324–326** cover CPU built-in configured user numbers
  **1..16** (the separate RJ71EN71 network module shows 1..64), own
  port ranges 1..4999/5010..65534 with factory default Blank, and
  recommended ranges 1024..4999/5010..61439. **Appendix 10 p.554**
  identifies RnCPU CPU built-in manufacturer-reserved system services;
  these override otherwise permitted generic port numbers.
  These facts belong to the *R04CPU CPU built-in* example and have
  already been implemented by the independent per-row inspector.
- **Newest currently listed manufacturer edition:** [official Mitsubishi
  downloads](https://www.mitsubishielectric.com/fa/download/search.page?kisyu=%2Fplcr&mode=manual)
  lists **SH-081257ENG-AG, October 2026** with R04CPU among target
  models. The **actual AG PDF sections could not be downloaded or
  page-by-page compared** here. Its applicability and changes are
  **NOT_VERIFIED**, not silently asserted equal to AD. The latest
  published CPU manual similarly has newer revisions; validate
  all current references before bench or industrial use.
- **New analysis policy is not vendor fact:** Duplicate setting numbers,
  gaps and repeated numeric PLC own ports are detected from
  supplied data. Mitsubishi end codes, GX Works3 editor enforcement,
  active TCP client budgets, transport-specific sharing permissions
  and actual physical PLC behavior are **not** inferred.
  Port reuse is **review-only** without a known transport/connection
  mode; a numeric port alone does not establish a TCP/UDP conflict.
  Slot gaps are advisory and may be disabled.

The cited manufacturer PDF is too large for the available web PDF
render/screenshot endpoint and direct vendor download access failed.
This report makes **no claim** of completed visual page-by-page
inspection of the newest AG edition or actual PLC testing.

## 2. Very Simple offline API

~~~python
import json
from virtual_plc.ethernet import (
    inspect_reference_rncpu_external_device_batch as inspect,
)

rows = [
    {"connection_number": 1, "plc_port": 1024},
    {"connection_number": 3, "plc_port": 1024},
    {"connection_number": 3, "plc_port": 5005},
]

print(json.dumps(inspect(rows), indent=2))
# Reports duplicate No.3, potential numeric-port reuse 1024,
# reserved system UDP port 5005, and advisory missing No.2.

print(json.dumps(inspect(rows, report_slot_gaps=False), indent=2))
# Same strict port/slot checks; ignores gaps for sparse configurations.

print(json.dumps(inspect(), indent=2))  # NOT_PROVIDED
print(json.dumps(inspect([]), indent=2))  # EMPTY
~~~

Only **exact `R04CPU`** is supported. The `rows` parameter accepts
an omitted `None` or a `list` of at most **16** objects with
**exactly** `connection_number` (integer 1..16) and `plc_port`
(integer 0..65535 or `None`). Missing/extra keys, duplicate
unrepresentable configuration IDs, invalid types, unsupported CPU
models or an explicit null `connection_number` raise `ValueError`.
Bool/float values do not count as valid integers. No user input is
mutated. The `report_slot_gaps` option is strictly boolean.

The routine *calls* existing
`inspect_reference_rncpu_external_device("R04CPU", number, plc_port)`
for every row; it does not duplicate the vendor port list, operating
system or socket behavior. Thus, a source-verified update to the
single-row SSOT automatically propagates to batch output.

## 3. Diagnostics and severity

| Code | Severity | Meaning and limits |
| --- | --- | --- |
| `VENDOR_PORT_NOT_CONFIGURABLE` | error | Per-row source check found invalid, ephemeral, or manufacturer-reserved PLC own port |
| `DUPLICATE_SETTING_NUMBER` | error | Two supplied rows share a GX Works3 configuration slot; **static input collision**, not vendor end code |
| `POTENTIAL_OWN_PORT_REUSE` | review | Different rows use the same numeric own-port; **not** proof of socket conflict without transport/connection mode |
| `SLOT_GAP_REVIEW` | review | Slot numbers missing between 1 and highest specified number; configurable `report_slot_gaps=False` |

Stable diagnostic order is: invalid own-port rows in input order,
duplicate slot number sorted ascending, repeated own-port sorted
ascending, then optional gap review. Each diagnostic is JSON-ready
and provides positions (zero-indexed, even if slot numbers differ).
The state is one of
`NOT_PROVIDED`, `EMPTY`, `NO_STATIC_ISSUES_FOUND`,
`REVIEW_REQUIRED`, or `REJECTED_STATIC_SETTINGS`.
**`NO_STATIC_ISSUES_FOUND` is not GX Works3 validation or physical
PLC certification.** An explicit empty list differs from omitted input.

This is not a native GX Works3 project parser. It intentionally
does not predict implicit slot allocation, local port reuse
permissions across TCP/UDP, remote peer port and transport rules,
maximum live connections or reconnect timing. Those need independent
manufacturer/bench evidence.

## 4. Single source of truth, tests and release gate

`virtual_plc/ethernet.py` owns
`_REFERENCE_HARDWARE["rncpu_builtin"]["external_device_configuration_reference"]`,
including the new
`manual_revision_gate={validated_reference_revision:"AD",
newer_catalog_revision:"AG",newer_revision_comparison:"NOT_VERIFIED"}`.
The reference catalog is projected through
`virtual-plc guide ethernet --json`.
The new function reports these exact gate values for downstream
validation and keeps all values independent of callers.

Test file: `tests/test_rncpu_external_device_batch_reference.py`,
including null vs empty; bounds; duplicate slot; advisory gap override;
port reuse classification; factory reserved ports; invalid tuples,
booleans, floats, list shape, wrong model, source defensive copies,
original scalar compatibility and **no socket**. Work tracked in
[PR #37](https://github.com/greatgc-flow/VirtualPLC/pull/37)
and [Issue #14](https://github.com/greatgc-flow/VirtualPLC/issues/14).

**Open gates:** obtain manufacturer **AG** PDF via approved supported
path and compare relevant CPU built-in section with AD. Confirm
per-service connection limits and sharing rules, optionally add
source-backed whole-project validation with transport and remote-port
metadata, then collect independent real-hardware evidence through
issue #2 on an isolated approved testbench. **No PyPI publication,
production traffic, remote RUN/STOP or physical PLC access**.
