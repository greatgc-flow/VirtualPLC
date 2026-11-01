# R04CPU CPU E/I vs Ethernet AD/AG: independent manual revision gates

Evidence checkpoint: 2026-11-01. This is **source provenance metadata** and a
strict *offline* simulator reference check, not a manufacturer-approved comparison
of revised clauses or a physical PLC acceptance test. Tracks issue #14.

## Manufacturer publication vs verified clauses

| Manual | Current official listing | Actually reviewed source scope | Updated clause parity |
| --- | --- | --- | --- |
| Ethernet Application `SH-081257ENG` | AG, 2026-10, 19.23MB | AD pp.324-326 (R04CPU built-in user slots / ports), pp.329-330/396-397 (A038H timer GUI), App.10 p.554 (system ports) | **AD→AG NOT_VERIFIED** |
| CPU Module `SH-082488ENG` | I, 2026-08, 18.39MB | E p.3 and App.8 pp.684-685: remote STOP/RUN Opening Method / A031H | **E→I NOT_VERIFIED** |

- Official current [Mitsubishi iQ-R manual listing](https://www.mitsubishielectric.com/fa/download/search.page?kisyu=%2Fplcr&mode=manual) (both edition labels).
- Official [R04CPU CPU manual listing](https://www.mitsubishielectric.com/fa/products/faspec/download.page?category=ex&formNm=RnCPU_R04CPU_3322&id=spec&kisyu=%2Fplcr&lang=2) (I).
- Previous reviewed [Ethernet AD primary source](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf) and [CPU E primary source](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh082488eng/sh082488enge.pdf).

**Retrieval limitation:** the PDF retrieval environment could not fetch these large
manuals for a clause-by-clause extraction/comparison; the current AG direct
file was also inaccessible. Manufacturer **catalogue edition metadata** does not
establish that ranges, system ports, timer increments, model scope or Opening
Method behavior remain identical in the newer PDF. Do not mark either
`newer_revision_comparison` as `VERIFIED` without authenticated full source,
specific page/section comparison and reviewed evidence.

## Exact owner and user input

The machine SSOT for both gates is `reference_catalog()["rncpu_builtin"]`
(defined in `virtual_plc/ethernet_reference.py`):

- `external_device_configuration_reference.manual_revision_gate`:
  reviewed AD, manufacturer-listed AG, `NOT_VERIFIED`.
- `remote_opening_reference.manual_revision_gate`:
  reviewed CPU E, manufacturer-listed CPU I, `NOT_VERIFIED`.

The composition API `virtual_plc.rncpu_reference.inspect_reference_r04cpu_configuration`
accepts **two distinct optional fields**:

~~~python
from virtual_plc.rncpu_reference import inspect_reference_r04cpu_configuration

report = inspect_reference_r04cpu_configuration({
    "manual_revision": "AD",         # Ethernet Application AD, not CPU E
    "cpu_manual_revision": "I",      # CPU Module I, not Ethernet AG
    "opening_method": "do_not_open_by_program",
})
assert report["manual_revision_check"]["status"] == "AD_REFERENCE_ONLY"
assert report["cpu_manual_revision_check"]["status"] == "UNVERIFIED_MANUAL_REVISION"
assert report["cpu_manual_revision_check"]["affects_supplied_opening_method"]
assert report["overall_static_review"] == "SOURCE_REVISION_NOT_VERIFIED"
assert report["physical_hardware_certified"] is False
~~~

Missing `cpu_manual_revision` remains `UNKNOWN_REQUESTED_REVISION` and
**does not change existing API's top-level status**: old callers can remain
on their prior AD-only reference preflight, which never claimed CPU-I parity.
Explicit CPU `E` is `E_REFERENCE_ONLY`, **not verified physical behavior**.
Explicit CPU `I`/other uppercase edition with a supplied Opening Method
(including explicit `None`) blocks an AD-only `REFERENCE_CHECKS_ONLY`
result. CPU E→I uncertainty does not block purely AD external-device/timer
checks when `opening_method` is omitted; the independent CPU edition
check still reports `UNVERIFIED_MANUAL_REVISION`.
Only exact `R04CPU` is eligible, no RJ71EN71/R08CPU inheritance. Strings
must contain one or two uppercase ASCII letters; explicit null/empty/
nonstring/whitespace is rejected. Static invalid user ports still take
precedence in the top-level status and all per-check diagnostics remain.

## Independent review / test gates

- `tests/test_r04cpu_cpu_manual_revision_gate.py`:
  E/I/wrong editions, AD/AG independence, missing-vs-null opening,
  unrelated source scope, rejected rows, strict types, defensive
  output copies, no socket calls.
- `tests/test_r04cpu_configuration_reference.py`:
  old legacy behavior for existing callers.
- Full Windows and Ubuntu × Python 3.10–3.13 + wheel build must pass 9/9
  on exact PR head and again after merge on exact main SHA. References in
  [PR #41](https://github.com/greatgc-flow/VirtualPLC/pull/41).

**Future work remains OPEN:** authenticated full-source comparison of AD
and AG (configured user slot/port/ranges, A038H timer units/defaults,
system ports) and E versus I (A031H opening method and remote STOP/RUN
warning). Record differences and evidence before any source upgrade.
Neither test success nor publication listing is hardware certification.
No network listeners, real PLC access, production connection or PyPI
publication was made by this feature.
