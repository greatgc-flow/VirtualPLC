# RnCPU built-in Ethernet: service-specific connection settings

Evidence snapshot 2026-11-01. **Reference-only**, no live iQ-R
PLC access, no direct device control, no captured vendor packets.
The built-in Ethernet CPU part is **not** the separate RJ71EN71
network interface. Never borrow a network module's timer or
default listener policy just because both use GX Works3.

## 1. Independent, official Mitsubishi service scenarios

| Scenario | Exact receiving interface | Transport | Opening/configuration requirement | Manufacturer source |
| --- | --- | --- | --- | --- |
| RCPU is the receiving peer in *simple CPU communication* | iQ-R RCPU CPU **built-in Ethernet** | **auto-open UDP** | No additional opening setting at the receiving RCPU | [Mitsubishi FAQ #20230 (Japanese, 2018)](https://fa-faq.mitsubishielectric.co.jp/faq/show/20230) |
| Several GOTs connected to one iQ-R controller | iQ-R CPU **built-in Ethernet** | **TCP** | **GX Works3 External Device Configuration per GOT** | [Mitsubishi FAQ #45267 (English, 2025)](https://fa-faq.mitsubishielectric.com/faq/show/45267) |
| Several GOTs connected to one iQ-R controller | iQ-R CPU **built-in Ethernet** | **UDP** | No GOT-side UDP opening setting needed | [Mitsubishi FAQ #45267](https://fa-faq.mitsubishielectric.com/faq/show/45267) |

These facts must **not** be collapsed into "all RnCPU UDP
needs no configuration" or "all RnCPU TCP requires per-client GOT
configuration." The FAQ statements concern their named services
and exact operating roles only.

For the GOT TCP case, the documented GX Works3 path is:

~~~text
Navigation Window > Parameter > RnCPU > Module parameter >
Basic Settings > External Device Configuration > Detail settings >
Ethernet configuration (built-in Ethernet port)
~~~

The existing RnCPU **system port reference** (SH-081257ENG-AD
Appendix 10) lists default auto-open UDP **5005**, MELSOFT UDP
**5006**, and MELSOFT TCP **5007**. The FAQ #20230 itself describes
the **auto-open UDP function** without independently proving
the port number or all CPU/firmware editions. Do not interpret
the system port table as an instruction to bind these service
ports in the simulator; MELSOFT, GOT and firmware handshakes
are not implemented by a generic MC/SLMP listener.

## 2. Single-source-of-truth reference inspection

From a source checkout (Python 3.10+):

~~~python
import json
from virtual_plc.ethernet import reference_catalog

info = reference_catalog()["rncpu_builtin"]
print(json.dumps(info["service_connection_reference"], indent=2))
# Contains simple_cpu_communication_partner and multiple_got,
# exact official FAQ links, separate UDP and TCP setting rules.
~~~

The same read-only data is projected by
`virtual-plc guide ethernet --json` under
`reference_only_models.rncpu_builtin`.
The catalog produces a deep defensive copy.
It still refuses
`EthernetSettings("rncpu_builtin")`, and the runnable model
keys remain qj71e71, lj71e71 and rj71en71.

## 3. Feedback and verification gates

- `tests/test_rncpu_builtin_service_connections.py` independently
  checks each official scenario, service provenance, exact
  GX Works3 route, defensive copies, JSON catalog projection,
  isolated hardware scopes and zero network access.
- **OFFICIAL_FAQ_REFERENCE_ONLY** means the rule is supported by
  the linked Mitsubishi FAQ; it does not mean that the
  simulator exposes GOT/MELSOFT-specific services.
- `physical_hardware_certified=false` and
  `simulator_network_affected=false` by construction.
- Actual RnCPU firmware, service count/connection limits,
  SLMP command/frame parity, module-specific timers, physical
  network captures and error-code behavior remain UNKNOWN or
  under follow-up issues #14, #22, #2.

No real PLC connection, auto-OPEN, PyPI release, or hardware
compatibility certification is performed in this change.
