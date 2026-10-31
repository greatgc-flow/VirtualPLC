# FX5 CPU firmware and mixed-generation simple communication

Evidence snapshot: 2026-11-01. All findings here are **OFFICIAL FAQ
REFERENCE ONLY**. No vendor PLC was contacted and no firmware was
read from actual equipment. The runtime VirtualPLC does **not**
enable FX5 CPU built-in or FX5-ENET real-hardware profiles.

## 1. Manufacturer model and firmware distinction

[Mitsubishi FAQ #39316 — supported firmware for simple CPU
communication](https://fa-faq.mitsubishielectric.com/faq/show/39316)
is explicitly **model-specific**:

| Built-in Ethernet CPU | Feature support | Firmware absence |
| --- | --- | --- |
| FX5U | 1.110 or newer | UNKNOWN, never silently unsupported |
| FX5UC | 1.110 or newer | UNKNOWN, never silently unsupported |
| FX5UJ | From first release | No version needed to identify this documented model rule |
| FX5S | From first release | No version needed to identify this documented model rule |

This is **simple CPU communication**, not an assertion that the SLMP
server supports 1E/3E with identical device types, device limits,
connection counts, RUN-write permissions or timeouts.
The FX5 CPU built-in aggregate external Ethernet connection count
is **8** (FAQ #22320, with documented exceptions); this is not the
simple CPU communication **target** count (FAQ #40032: 16 for U/UC,
8 for UJ/S). FX5-ENET module connections are separately scoped (32).

## 2. Documented GX Works3 interoperability example

[Mitsubishi FAQ #44329 — communicating between newer and older FX5
CPU firmware](https://fa-faq.mitsubishielectric.com/faq/show/44329)
describes a mixed-firmware scenario:

- **FX5U/FX5UC >=1.110**: GX Works3 Ethernet Port → Application
  Settings → Simple CPU Communication Settings; choose
  **SLMP-compatible device (QnA-compatible 3E frame)** for the
  connection destination and configure the simple CPU function.
- **FX5U/FX5UC earlier than 1.110**: GX Works3 Ethernet Port →
  Basic Settings → External Device Configuration; configure the
  SLMP connection device for this mixed-version example.
- **FX5UJ/FX5S**: FAQ #39316 establishes support from first
  release, but these two FAQs do not independently verify the
  exact GX Works3 option path for each earliest UJ/S revision.
  Our inspector deliberately returns unknown for that path,
  even when the function itself is documented supported.

The destination type **QnA-compatible 3E** in this specific
interop example is not evidence that every FX5-ENET module,
other firmware or network listener uses that frame exclusively.
It does **not** enable a runnable VirtualPLC hardware model.

## 3. Minimal, offline-only reference check

Run from the source checkout (Python 3.10+, stdlib only).

~~~python
import json
from virtual_plc.ethernet import inspect_reference_fx5_simple_cpu_communication as inspect

print(json.dumps(inspect("FX5U", "1.109"), indent=2))
print(json.dumps(inspect("FX5UC", "1.110"), indent=2))
print(json.dumps(inspect("FX5UJ"), indent=2))
print(json.dumps(inspect("FX5U"), indent=2))  # UNKNOWN_FIRMWARE
~~~

The inspector accepts exactly **FX5U, FX5UC, FX5UJ, FX5S**.
An optional firmware string uses ASCII decimal vendor notation
`1.110` (three digits after the dot); no float, null-to-zero,
partial version, non-ASCII digits or guesswork. Missing firmware
for U/UC yields `UNKNOWN_FIRMWARE`, not `NOT_SUPPORTED`.

The result includes:
- `support_status`: SUPPORTED / NOT_SUPPORTED / UNKNOWN_FIRMWARE
- `gxworks3_configuration_path` and `destination_device_type`
  only for the cited U/UC newer/legacy mixed-generation example
- independent simple-CPU target count and 8 aggregate Ethernet
  connections, with explicit scope
- exact official FAQ links and `physical_hardware_certified=false`,
  `simulator_network_affected=false`.

All values are produced from `virtual_plc/ethernet.py`'s
reference-only single source of truth and exposed in
`virtual-plc guide ethernet --json`.
Runtime `Server`, listeners, `--max-clients=64`, memory and
SLMP 1E/3E/4E remain unchanged.

## 4. Validation and remaining work

`tests/test_fx5_simple_cpu_firmware_reference.py` covers
boundary 1.109 / 1.110, initial UJ/S support, missing version,
case-sensitive model IDs, malformed/null/float versions, defensive
metadata copy, no-socket guarantee, and the separation between
simple-CPU target count and SLMP server socket count.

Evidence level: **official FAQ + synthetic unit tests**; **no
PHYSICAL_VERIFIED** hardware. An actual FX5 CPU/FX5-ENET/RnCPU
hardware model requires independent firmware/port/frame/device
oracle verification under issues #14, #22 and #2.

Official sources:
- https://fa-faq.mitsubishielectric.com/faq/show/39316
- https://fa-faq.mitsubishielectric.com/faq/show/44329
- https://fa-faq.mitsubishielectric.com/faq/show/22320
- https://fa-faq.mitsubishielectric.com/faq/show/40032
