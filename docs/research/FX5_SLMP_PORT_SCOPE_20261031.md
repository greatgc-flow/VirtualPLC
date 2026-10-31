# FX5 SLMP port & connection scope — reference-only preflight

Verified 2026-10-31 against Mitsubishi official published material.
**No hardware traffic was generated.** Research gate: #14, #2, #22.
The reference catalog is the single source of truth:
`virtual_plc/ethernet.py` -> `reference_catalog()` ->
`virtual-plc guide ethernet --json`. Reference entries do NOT
become runnable Ethernet hardware profiles.

## Model and life-cycle matrix (MECE by interface)

| Exact interface | Editor | SLMP | Simultaneous Ethernet connections | Host SLMP port | Timer fidelity | Current runnable status |
| --- | --- | --- | --- | --- | --- | --- |
| FX5 CPU **built-in** Ethernet (FX5U/UC/UJ/S) | GX Works3 | 1E, 3E [official] | Up to **8** combined external Ethernet connections, documented service exclusions [official] | 1–5548, 5570–65534 [official; 5549–5569 reserved] | CPU keepalive facts reference-only; TCP timer/default host-port parity unknown | **REFERENCE_ONLY** |
| **FX5-ENET** expansion module | GX Works3 | 1E, 3E [official] | **32** aggregate module connections [official] | Same documented permitted/reserved range; SLMP own-port initially blank | Existence check 600s / 10s / 3 reference-only; Q/R stack timers unknown | **REFERENCE_ONLY** |
| **RnCPU built-in** Ethernet | GX Works3 | Exact scope/firmware under separate vendor study | **UNKNOWN** in this comparison | Auto UDP 5005, MELSOFT UDP 5006/TCP 5007 in older R module study; not equivalent to an SLMP custom port default | Exact CPU ranges **UNKNOWN** | **REFERENCE_ONLY** |
| **QJ71E71** Ethernet module | GX Works2 | Existing generic 3E/4E simulator capability; physical parity not implied | Not inferred from FX5 | Auto UDP 5000 from module study; no implicit binding | Q E71 nine reference timer values, not host kernel controls | **IMPLEMENTED_SIMULATOR** opt-in `qj71e71` |
| **LJ71E71-100** Ethernet module | GX Works2 | Existing generic 3E/4E simulator capability; physical parity not implied | Not inferred from FX5 | Auto UDP 5000 from module study; no implicit binding | L E71 nine reference timer values | **IMPLEMENTED_SIMULATOR** opt-in `lj71e71` |
| **RJ71EN71** network module | GX Works3 | Existing generic 3E/4E simulator capability; physical parity not implied | Not inferred from FX5 | Auto UDP 5000; MELSOFT UDP 5001/TCP 5002 are **not bound** | iQ-R nine reference timer values | **IMPLEMENTED_SIMULATOR** opt-in `rj71en71` |

SLMP is a server/network service, not the same thing as the FX5
**simple CPU communication function**. Mitsubishi FAQ #40032 gives
**target devices** for that feature: FX5U/FX5UC **16**, FX5UJ/FX5S
**8**. These figures must never overwrite the CPU's **8 aggregate
external Ethernet connections** cited in FAQ #22320. In particular,
16 simple-CPU-communication targets does not mean 16 simultaneous
inbound SLMP TCP sessions. The FX5-ENET 32 connection limit is
module-specific, not the same setting as Q/L/R client caps.

## FX5 CPU firmware-dependent simple communication (2026-11-01 update)

The [official FAQ-backed firmware matrix](FX5_CPU_FIRMWARE_SIMPLE_COMM_20261101.md)
separates the simple CPU communication feature from SLMP inbound
connections. **FX5U/FX5UC >=1.110**, FX5UJ/FX5S from first revision;
unsupported/unknown firmware does not imply any new SLMP port count.
The pure reference API and the `guide ethernet --json` catalog
retain model-specific provenance. FX5-ENET has its own separate
expansion-module reference behavior and is not inherited here.

## Port classes (FX5 CPU built-in / FX5-ENET only)

| Inclusive vendor port range | Classification | Meaning |
| --- | --- | --- |
| 0 | `simulator_only_ephemeral` | VirtualPLC socket port 0 chooses a free OS port; invalid as GX Works3 vendor port |
| 1–1023 | `permitted_not_recommended` | Vendor setting range includes it; IANA/well-known services caution |
| 1024–5548 | `recommended` | Explicit vendor recommendation |
| 5549–5569 | `vendor_system_reserved` | System reserved; do not configure for SLMP |
| 5570–61439 | `recommended` | Explicit vendor recommendation |
| 61440–65534 | `permitted_not_recommended` | Vendor allows in setting range, but other module services may use them |
| 65535 | `outside_vendor_range` | Not in vendor's SLMP host-port setting range |

Recommended != permitted, and neither proves that a port is free,
that the target firmware accepts the chosen service, or that the
host OS socket binder can open it.

## Minimal offline preflight

From a source checkout (Python 3.10+, stdlib only):

~~~powershell
# Inspect one vendor host port; opens NO network socket.
python -c "import json; from virtual_plc.ethernet import inspect_reference_slmp_port; print(json.dumps(inspect_reference_slmp_port('fx5_enet', 5000), indent=2))"

# Read all reference-only models (none activated):
virtual-plc guide ethernet --json
~~~

Programmatic API: `inspect_reference_slmp_port(model, port)`, where
`model` is exactly `fx5_cpu_builtin` or `fx5_enet`; `port` is
an integer 0–65535 (bool/string/null and out-of-range values fail
closed). The JSON-compatible result includes `classification`,
`permitted`, `recommended`, `source`,
`status=OFFICIAL_MANUAL_REFERENCE_ONLY`,
`physical_hardware_certified=false`, and
`simulator_bind_affected=false`. This is **not** a real-time port
availability test and does not check device connectivity or traffic.
An attempted `--ethernet-model fx5_enet` remains unsupported.

For future hardware emulation, add a **distinct opted-in firmware/model**
contract before enforcing vendor ranges on actual Server listeners.
Do not change `Server(port=0)` or the default `--max-clients=64`
as a side-effect of reference research. Independent PLCs stay in
separate OS processes; multiple ports per PLC share its state.

## Evidence (manual versus simulator versus physical)

1. **OFFICIAL_MANUAL** — [Mitsubishi SH-082625ENG-H
   FX5 CPU Communication p.100](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082625eng/sh082625engh.pdf):
   SLMP host port 1–5548 or 5570–65534; 5549–5569 reserved.
2. **OFFICIAL_MANUAL** — [Mitsubishi SH-082026ENG-H FX5-ENET
   p.79](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082026eng/sh082026engh.pdf):
   same vendor port range; separate module protocol defaults.
3. **OFFICIAL_MANUAL** — [Mitsubishi JY997D56201-U FX5 Ethernet
   Communication p.60](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/jy997d56201/jy997d56201u.pdf):
   1024–5548 and 5570–61439 **recommended**, explains reserved
   well-known and other-module service ranges, CPU 8 versus module
   32, including special MELSOFT counting exception.
4. **OFFICIAL FAQ** — [Mitsubishi #22320](https://fa-faq.mitsubishielectric.com/faq/show/22320):
   FX5 built-in combined connection maximum 8 with service exclusions.
5. **OFFICIAL FAQ** — [Mitsubishi #40032](https://fa-faq.mitsubishielectric.com/faq/show/40032):
   simple CPU communication target counts 16/16/8/8 by CPU variant.
6. **IMPLEMENTED_SIMULATOR** — `tests/test_fx5_reference_slmp_port.py`
   checks every boundary, wrong/null/bool types, immutable SSOT
   projection, no network binding changes, and distinct service
   counts. Candidate CI must be observed before any readiness claim.
7. **PHYSICAL_VERIFIED** — **NONE**. CPU firmware, model-specific
   RUN write settings, real SLMP end codes, timers, exception
   counting, default listener openings, and physical response
   oracles remain unverified and are gated under #14/#2/#22.

No PyPI release, direct PLC test, real network capture, auto-OPEN
service, or hardware control is performed by this reference checker.
