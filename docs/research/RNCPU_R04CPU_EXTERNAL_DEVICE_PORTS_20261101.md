# R04CPU built-in Ethernet — GX Works3 external-device slot/port preflight

Evidence snapshot: 2026-11-01. **Official manual reference only.**
Applies to the **R04CPU CPU built-in Ethernet** example. It is not a
runnable RnCPU preset, a hardware-specific TCP connection-count limit,
a RJ71EN71 network-part module setting, or any physical PLC certification.

## 1. Source, exact applicability and caveats

Manufacturer [Mitsubishi MELSEC iQ-R Ethernet User's Manual (Application),
SH-081257ENG-AD](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf):

- Printed **pp.324–325**, External Device Configuration `No.`:
  the *configuration numbers distinguishing user connection settings*
  are **1–16** for the **CPU module built-in Ethernet port part**,
  versus **1–64** for **RJ71EN71/RnENCPU network part** (the network
  module's Q-Compatible mode has its own 1–16 restriction).
  **This is not a documented maximum live TCP/UDP client count.**
  Settings start at slot 1; do not infer that the factory populates slot
  1, or that 16 concurrent TCP clients are supported.
- The **PLC-side** `Port No.` for configured external device connections
  is **1–4999** or **5010–65534**, with **Default: Blank**. It is not the
  **Sensor/Device Port No.**, which is a separate field and can include
  other values. This offline inspector only checks the PLC own port.
- The suggested nonconflicting ranges are **1024–4999** or
  **5010–61439**. The numerically permitted low (1–1023) and high
  (61440–65534) ranges are generally *discouraged*. **Explicit
  system reservations below override both ranges.**
- Printed **Appendix 10 p.554** identifies additional **RnCPU CPU
  built-in** system ports that cannot be specified as configurable
  user ports, even though some fall within the broad numeric ranges:
  20, 21, 80, 123, 5001, 5005–5009, 61440–61442, 61448,
  61450, 61461, 61696–61999 and 62000–65534.
  Examples: auto-open UDP/5005, MELSOFT UDP/5006, MELSOFT
  TCP/5007, SLMP-SND UDP/61441 and FTP client TCP/62000–65534.
  Factory system port status is *physical manufacturer metadata* and
  **does not create a VirtualPLC listener**.
- CPU firmware/family-specific support and active sockets have not
  been independently validated; this inspector deliberately accepts
  exact **R04CPU** only. A newer revision than SH-081257ENG-AD may exist;
  re-check applicability and revision differences before physical use.

**Image-verification note:** The original manufacturer's >20 MB PDF
exceeded the available PDF screenshot endpoint or was blocked by the
mirrored host. The relevant pp.324–326 and Appendix 10 p.554 were
cross-checked in the official document's extracted text/tables.
No claim of an independent visual page image or physical hardware
capture is made.

## 2. Offline source-of-truth API

~~~python
import json
from virtual_plc.ethernet import inspect_reference_rncpu_external_device as inspect

print(json.dumps(inspect(), indent=2))
# Omitted number = UNSPECIFIED, port = Blank (documented GUI default).
print(json.dumps(inspect("R04CPU", 1, 1024), indent=2))
# Recommended own port; not an actual bound socket.
print(json.dumps(inspect("R04CPU", 16, 5005), indent=2))
# Known system auto-open UDP port; NOT user-configurable.
print(json.dumps(inspect("R04CPU", 16, 62000), indent=2))
# FTP client dynamic TCP system range; NOT user-configurable.
~~~

The same SSOT is found at
`reference_catalog()["rncpu_builtin"]["external_device_configuration_reference"]`
and is automatically projected into `virtual-plc guide ethernet --json`
under `reference_only_models.rncpu_builtin`.
Reference catalog and returned reports use defensive copies.
No new third-party dependencies, runtime flags or socket operations.

## 3. Result semantics / negative contracts

| Input | Classification / result | Meaning |
| --- | --- | --- |
| `connection_number=None` | `UNSPECIFIED` | No selected user connection; do not infer a default |
| `connection_number=1..16` | `CONFIGURATION_SLOT_VALID` | Only a GX Works3 user setting slot, not TCP client capacity |
| `plc_port=None` | `blank_default` | GUI blank setting; **not** a listener |
| `plc_port=0` | `simulator_only_ephemeral` | VirtualPLC port 0 convention, not vendor config |
| `plc_port=1024` | `recommended` | In vendor suggested/configurable range |
| `plc_port=1` | `permitted_not_recommended` | Numerically configurable but discouraged |
| `plc_port=5005` | `system_service_port_not_user_configurable` | RnCPU auto-open UDP reserved by vendor |
| `plc_port=61441` | `system_service_port_not_user_configurable` | SLMP-SND reserved system port |
| `plc_port=65534` | `system_service_port_not_user_configurable` | Within dynamic FTP client system range |
| `plc_port=5000` | `outside_vendor_configurable_range` | In the excluded 5000–5009 PLC user-port gap, not a claimed RnCPU service |
| `plc_port=65535` | `outside_vendor_configurable_range` | Above PLC user-port limit |

Invalid CPU model names, negative/overflow integers, boolean-as-integer,
float, empty strings, arrays, dictionaries and malformed explicit values
raise `ValueError`; omitted `None` is intentionally distinct.
System reservations take precedence over configurable and recommended
ranges. The report always has
`not_a_simultaneous_tcp_socket_limit=True`,
`physical_hardware_certified=False` and
`simulator_bind_affected=False`.
It does not validate a whole multi-row GX Works3 project, duplicate slot
allocation or external-device transport/protocol correctness.

## 4. Evidence and future gates

- TDD: `tests/test_rncpu_external_device_reference.py` exercises
  1/16 boundaries, invalid/null/array cases, recommended/discouraged
  port boundaries, reserved single/system ranges, source immutability,
  guide JSON and no-socket behavior.
  [PR #36](https://github.com/greatgc-flow/VirtualPLC/pull/36).
- **Next separate work:** optional whole-configuration preflight
  (duplicate slots, holes/placeholder rules from p.324, duplicate own-port
  warnings and conflicts by service) with additional official evidence.
  Also compare **current manufacturer revision** against AD.
- **HOLD:** exact RnCPU model/firmware-specific simultaneous connection
  capacity, hardware SLMP code/device/remote control parity,
  OS TCP stack behavior and physical device/packet tests. Retain
  issues #14, #2, #22. No automatic vendor-port binding, physical
  equipment connection, operational machine control, tags or PyPI.
