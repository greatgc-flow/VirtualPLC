# R04CPU CPU-built-in: one offline configuration preflight (PR #38)

Evidence checkpoint 2026-11-01. **This is a composition of independently
tested, source-scoped checks, not a new hardware protocol implementation,
native GX Works3 project parser, or Mitsubishi equipment certification.**

## Rationale and official provenance

R04CPU CPU **built-in** Ethernet is not RJ71EN71 (the separate network
module). The independent existing reference inspectors continue to own all
vendor facts; this wrapper merely runs the requested sections together and
safely exposes edition uncertainty.

- [Mitsubishi SH-081257ENG-AD](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf)
  printed pp.324–326/Appendix 10 p.554: R04CPU example's configured
  user slots **1–16**, own-port bounds and reserved system services.
  Configured slots are **not** a live TCP client limit.
- Same AD manual pp.329–330/396–397: R04CPU CPU-built-in A038H GUI
  settings and the separately validated nine data-communication timers.
  This is not proof that RJ71EN71 kernel behavior matches this CPU.
- [Mitsubishi SH-082488ENG-E](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh082488eng/sh082488enge.pdf)
  p.3/Appendix 8 pp.684–685: CPU built-in `Opening Method` and
  remote STOP→RUN reconnect hazard if configured Open by Program.
  The factory method remains UNKNOWN.
- The [manufacturer's live R04CPU download page](https://www.mitsubishielectric.com/fa/products/faspec/download.page?category=ex&formNm=RnCPU_R04CPU_3322&id=spec&kisyu=%2Fplcr&lang=2)
  currently lists **SH-081257ENG-AG** (2026-10). Its actual relevant
  clauses were **not retrieved/diffed** against AD. The verifier
  explicitly marks AG/other editions `UNVERIFIED_MANUAL_REVISION`
  and never silently upgrades to AG source parity.
  The newer SH-082488ENG-I CPU manual is likewise not treated as
  clause-identical to the earlier E manual.

## Source-check API (Python 3.10–3.13, stdlib only)

~~~python
import json
from virtual_plc.rncpu_reference import inspect_reference_r04cpu_configuration

manual_transcription = {
    "manual_revision": "AD",
    "opening_method": "do_not_open_by_program",
    "data_timers": {},  # Explicit AD reference factory timer table, NOT physical PLC readback
    "external_devices": [
        {"connection_number": 1, "plc_port": 1024},
        {"connection_number": 2, "plc_port": None},  # Blank vendor GUI field
    ],
}
print(json.dumps(inspect_reference_r04cpu_configuration(manual_transcription), indent=2))
# manual_revision_check.status == "AD_REFERENCE_ONLY"
# overall_static_review == "REFERENCE_CHECKS_ONLY"

# A newer manual is listed but its clause parity has not been established:
print(inspect_reference_r04cpu_configuration({
    "manual_revision": "AG",
    "external_devices": [],
})["overall_static_review"])
# SOURCE_REVISION_NOT_VERIFIED
~~~

This API does not bind local ports or connect to a PLC. It directly calls
`virtual_plc.ethernet`'s three existing validators for opening method,
A038H timer reference, and multi-row External Device Configuration.
All machine-readable vendor ranges, reserved ports, defaults and
source links remain in the existing `reference_catalog()` SSOT.
The new wrapper adds **no** copy of their vendor tables.

### Explicit input semantics and negative contracts

- `configuration=None` → `NOT_PROVIDED`; `{}` → `EMPTY`.
  Neither implies that any physical PLC setting was read.
- Section omitted → corresponding check `None`. Explicit
  `opening_method=None` runs the underlying inspector and returns
  `UNKNOWN` risk; no factory default is guessed.
- Explicit `external_devices=None` → batch `NOT_PROVIDED`;
  explicit `[]` → `EMPTY`. Each nonempty row has *exactly*
  `connection_number` and `plc_port` per the existing batch checker.
- Explicit `data_timers={}` → the *documented AD reference* defaults,
  not a current CPU readback. `data_timers=None` is rejected, to avoid
  accidentally converting an unknown field into asserted defaults.
- `manual_revision="AD"` → `AD_REFERENCE_ONLY`;
  omitted → `UNKNOWN_REQUESTED_REVISION`;
  other explicit uppercase edition codes (including `AG`) →
  `UNVERIFIED_MANUAL_REVISION`.
- Only the exact `R04CPU` model is allowed; `R08CPU`, `RJ71EN71`,
  invalid strings, bools, floats, wrong root/field types, unknown keys,
  bad time units or reserved ports are strictly handled by the
  wrapper or existing independent inspectors.
- The highest-level status preserves invalid static rows before
  revision uncertainty, but never asserts physical hardware parity.
  `REFERENCE_CHECKS_ONLY` does **not** mean valid GX Works3 project.
  Unknown opening method and documented remote reconnect risks remain
  review findings. `report_slot_gaps=False` merely controls the
  existing optional advisory, never masks invalid reserved ports.

## Acceptance / assurance

Tests `tests/test_r04cpu_configuration_reference.py` cover
missing/empty/null, AD/AG/unknown editions, field/model validation,
delegated range/diagnostic behavior, advisory control, read-only input,
reference defensive copies and socket-free behavior.

Reproducible first RED (missing module) and final GREEN CI links are
tracked in [PR #38](https://github.com/greatgc-flow/VirtualPLC/pull/38)
and [Issue #14](https://github.com/greatgc-flow/VirtualPLC/issues/14).
Build and Ubuntu/Windows Python 3.10–3.13 must all pass before merge,
then the new main SHA gets independent push CI. Do not misrepresent
the tests as physical PLC observations.

**HOLD:** AD→AG exact clause comparison, current R04CPU firmware/model
scope, GOT/SLMP/MELSOFT handshake and connection-budget oracle, native
GX Works3 project import, real-device RUN/STOP/timers. Track #14, #2,
#22. No PyPI release or actual factory network operations.
