# GX Works2/3 Ethernet settings — VirtualPLC runtime contract

Implementation: issue [#14](https://github.com/greatgc-flow/VirtualPLC/issues/14). Source-of-truth code: `virtual_plc/ethernet.py`. Detailed manufacturer research and model/firmware caveats: [GX Works Ethernet research](research/GXWORKS_ETHERNET_PARAMETERS_20261031.md).

> **One independent PLC = one OS process.** A process can open many TCP/UDP listeners, but they all share exactly one CPU state, one Memory and one request lock. The module presets described here are **opt-in**, local test emulation only; not a replacement for a real Mitsubishi PLC, a GX Works project importer, or an OS Ethernet stack.

## 1. Select a hardware module, not a GX Works editor version

| CLI model | Engineering environment | PLC wire profile | Source of defaults |
| --- | --- | --- | --- |
| `qj71e71` | GX Works2, QJ71E71-100/-B5/-B2 Ethernet module | `Q` | Mitsubishi SH-080009ENG, pp.38–39; timer-range notes in SH-080010ENG |
| `lj71e71` | GX Works2, LJ71E71-100 Ethernet module | `L` | Mitsubishi SH-081105ENG-G, pp.35–36, buffer-memory defaults and operation setting |
| `rj71en71` | GX Works3, iQ-R RJ71EN71 Ethernet network module | `iQ-R` | Mitsubishi SH-081257ENG rev AD, pp.322–323, 396–397 |

**Do not substitute** this RJ71EN71 network-module preset for an RnCPU built-in Ethernet port. LCPU, FX5U and FX5-ENET have their own hardware/firmware and need independent verification before implementing presets.

### Factory-default inspection (no listener opened)

```powershell
# GX Works2 Q E71:
virtual-plc --ethernet-model qj71e71 --show-effective-ethernet

# GX Works2 MELSEC-L LJ71E71-100:
virtual-plc --ethernet-model lj71e71 --show-effective-ethernet

# GX Works3 RJ71EN71:
virtual-plc --ethernet-model rj71en71 --show-effective-ethernet

# Compact help and full machine-readable model registry:
virtual-plc guide ethernet
virtual-plc guide ethernet --json
```

`--show-effective-ethernet` exits successfully **without binding any TCP or UDP ports**. Output contains every setting's `default`, `value`, `overridden`, `unit`, range/step or choices, source manual/page/URL and `effect`. The hardware model supplies the matching CLI wire profile automatically; an explicitly
conflicting `--profile` causes a usage error. The Python `Server(profile=...)`
API remains strict and still requires the matching profile. The model catalog
includes vendor system-port **reference metadata**; those ports are not bound.
The `overridden` field means **explicitly supplied by the user**, even if
`value` equals `default`; otherwise it is `false`.

### JSON override example

Save `ethernet.json`:

```json
{
  "timers": {
    "tcp_ulp_ms": 35000,
    "response_monitor_ms": 35000
  },
  "communication_data_code": "ascii",
  "allow_write_during_run": true
}
```

Then inspect before starting:

```powershell
virtual-plc --ethernet-model qj71e71 --ethernet-config ethernet.json --show-effective-ethernet
```

Run the simulator (loopback only):

```powershell
virtual-plc --ethernet-model qj71e71 --ethernet-config ethernet.json --listen tcp:5000 --listen udp:5000
```

JSON is intentionally strict: an explicitly supplied `null`, list, string or
scalar root is **not** an omitted configuration. Only a JSON object is valid;
unrecognized fields, noninteger timers, booleans used as numbers, out-of-range
increments and incorrect types fail **before binding**. There is no live reload; change the file and restart. Do not pass `--ethernet-config` without selecting `--ethernet-model`.

## 2. Manufacturer timer defaults

The generated model registry is the authoritative implementation record. For **all three currently supported hardware models**, its factory values are:

| Key (milliseconds unless noted) | Factory value | Manufacturer concept | Runtime effect |
| --- | ---: | --- | --- |
| `tcp_ulp_ms` | 30000 | TCP ULP send lifetime | Reference only |
| `tcp_zero_window_ms` | 10000 | TCP zero-window probing | Reference only |
| `tcp_resend_ms` | 10000 | TCP retransmit wait | Reference only |
| `tcp_end_ms` | 20000 | TCP FIN closing | Reference only |
| `ip_assembly_ms` | 5000 | IP fragment reassembly | Reference only |
| `response_monitor_ms` | 30000 | Ethernet module response monitoring | Reference only |
| `alive_start_ms` | 600000 | External-station existence check start | Reference only |
| `alive_interval_ms` | 10000 | Existence-check interval | Reference only |
| `alive_retries` (count) | 3 | Existence-check retries | Reference only |

Ranges and increments **differ by hardware**, so do not simply reuse GX Works2 values in GX Works3:

- **QJ71E71 and LJ71E71-100** use 500ms increments; most TCP timers have a minimum of 1000ms, IP assembly and alive intervals a minimum of 500ms. Defaults and Q-format buffer-memory ticks are reported as **milliseconds**, not raw GX Works 500ms units. The manufacturer permits up to 32767 ticks for most fields, IP assembly up to 32766 ticks, retries 1–32767.
- **RJ71EN71** allows 100ms increments across 100–16,383,000ms, and retries 1–99,999. For this model, the following manual constraints are validated for each override: `response_monitor >= tcp_ulp >= tcp_end >= tcp_resend > ip_assembly` and `tcp_zero_window == tcp_resend`.
- A single override only replaces named keys; the remaining values retain their factory defaults. Reporting distinguishes inherited defaults from explicitly specified values, including an explicit value equal to its default. Use an explicit, locally saved JSON file so configuration can be inspected/reproduced.

**All nine timers are reference-only.** VirtualPLC does **not** replace Windows/Linux TCP RTO, zero-window, TCP FIN, kernel keepalive or IP reassembly logic. It does not implement a firmware-equivalent response-monitor state machine, retry count, UDP reliability or silent timeouts. `--idle-timeout` is strictly a separate simulator **TCP socket** idle limit / nonlocal-bind safety guard.

The MC/SLMP request-frame monitoring timer (request timer field, 250ms units) and the iQ-R Simple Device Communication timeout/retry parameters are separate subsystems; **neither is silently mapped to the above settings**. The simulator currently parses but does not enforce the SLMP request timer.

## 3. Applied simulation policies (opt-in)

| Setting | QJ71E71 / LJ71E71 / RJ71EN71 factory value | Effective behavior |
| --- | --- | --- |
| `communication_data_code` | `binary` | Only the selected binary or ASCII MC encoding is accepted on all TCP/UDP listeners. Mismatch **closes TCP** or **drops UDP** (documented simulator policy; exact physical-module mismatch response unverified). |
| `allow_write_during_run` | `false` | When CPU state = RUN, MC batch/random write commands 1401/1402 are rejected with end code `0x0055`; memory remains intact. STOP allows the writes. `true` permits them during RUN. |

The `0x0055` status is manual-derived (QJ71E71 and iQ-R SLMP/MC error lists). The precise firmware/transport behavior is **not physically validated**. No other vendor packet semantics should be inferred from this simulator.

Without `--ethernet-model` or `Server(ethernet_model=...)`, existing behavior is **unchanged**: no strict binary/ASCII restriction, RUN-time writes allowed. When selected, all listeners in the process see the **same** policy, CPU state and data.

## 4. Programmatic use

```python
from virtual_plc import Server, EthernetSettings

# Snapshot: values immutable; report() is independent JSON-compatible data.
config = EthernetSettings("qj71e71", {
    "timers": {"tcp_ulp_ms": 35000, "response_monitor_ms": 35000},
    "allow_write_during_run": True
})
print(config.report()["parameters"]["tcp_ulp_ms"])

# One simulated PLC / process; its listeners share one policy & CPU state.
with Server(profile="Q", ethernet_model="qj71e71",
            ethernet_overrides={"allow_write_during_run": True},
            listeners=[("tcp", 0), ("udp", 0)]) as plc:
    print(plc.addresses, plc.ethernet.report()["model"])
```

The `Server` constructor validates model/PLC profile matching before listening. `ethernet_overrides` without `ethernet_model` is an error. Selecting LJ71E71 requires `profile="L"`; RJ71EN71 requires `profile="iQ-R"`. Q/L timer defaults match numerically, but their manual provenance and hardware identity remain separate.

## 5. Nonfeatures / forward-compatibility gate

- **No auto-open of manufacturer default system ports.** QJ71E71's UDP/5000 and RJ71EN71's auto UDP/5000 or MELSOFT UDP/5001, TCP/5002 are described only as reference metadata. Only explicitly provided `--listen` endpoints bind. MELSOFT service handshake is not implemented.
- **No in-process independent PLC supervisor.** Run another independent OS process for another PLC, each with its own network ports, memory, configuration file, fault plan and snapshot file.
- **No external network or physical PLC guarantee.** Default local-only binding and nonlocal explicit opt-in + finite TCP idle timeout still apply. The selected manufacturer idle/ULP values do not override this safety policy.
- **No native GX Works project import, no outbound active-open, no fullpassive restriction or vendor socket-state machine.** These may require separate simulator milestones and official manual/firmware evidence. Keep [#14](https://github.com/greatgc-flow/VirtualPLC/issues/14) open for future model parity and RnCPU/FX5 coverage.

## 6. Regression and verification

`tests/test_ethernet_settings.py` provides table-driven model defaults, Q/R units/ranges, invalid JSON, override precedence, introspection without binding, profile mismatch, legacy-mode safety, TCP/UDP data-code isolation, shared RUN-write protection, STOP/enable overrides and source/fidelity reporting. CI covers Linux and Windows on Python 3.10–3.13.

Read-only discovery for unimplemented interfaces:

```powershell
virtual-plc guide ethernet --json
```

The top-level `models` object contains **runnable** Q/L/R Ethernet models.
The separate `reference_only_models` object describes `fx5_cpu_builtin`,
`fx5_enet`, and `rncpu_builtin` with independently sourced known settings and
an explicit `unverified` list. These are **not** valid `--ethernet-model`
values; their missing timer defaults are not inferred from Q/L/R.
See [the hardware gap matrix](research/ETHERNET_HARDWARE_NEXT_20261031.md)
for model-specific open questions and firmware differences.

Manufacturer citations: [L E71 Basic SH-081105ENG-G](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081105eng/sh081105engg.pdf) pp.35–36, [Q E71 Basic SH-080009ENG](https://www.mitsubishielectric.com/dl/fa/document/manual/plc/sh080009/sh080009x.pdf) pp.38–39, [Q E71 Application SH-080010ENG](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080010/sh080010r.pdf), [iQ-R Ethernet Application SH-081257ENG](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf) pp.322–323, 396–397. These are **manual** references, not captured measurements from real hardware.
