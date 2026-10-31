# Next Ethernet hardware profiles — evidence, scope and implementation gates

Research extension: 2026-10-31 (KST). Linked from [the primary GX Works2/3 Ethernet matrix](GXWORKS_ETHERNET_PARAMETERS_20261031.md) and [runtime model guide](../ETHERNET_MODEL_SETTINGS.md). Tracks [#14](https://github.com/greatgc-flow/VirtualPLC/issues/14).

The machine-readable `virtual-plc guide ethernet --json` has separate
`models` (runnable) and `reference_only_models` (unimplemented, sourced
facts + explicit unknowns). Both are projected from `virtual_plc/ethernet.py`;
this document explains evidence and open gates without making a future model
executable.

**One independent PLC = one OS process.** Multiple TCP/UDP listeners inside that process share one simulated CPU and memory; multiple independent PLCs use separate processes. These notes apply to the *specific hardware interface*, not to every PLC configured by the same GX Works version.

### 2026-10-31 reference-only FX5 port and connection semantics

[Separate reference matrix](FX5_SLMP_PORT_SCOPE_20261031.md) documents
vendor **permitted** vs **recommended** host ports, 5549–5569 reserved,
port 0 as a simulator-only ephemeral bind, FX5 built-in 8 combined external
Ethernet sessions vs FX5U/UC 16 *simple CPU communication targets*, and
FX5-ENET 32 module connections. The port check is purely informational;
no runnable FX5 model or user listener default changes. Official source
pages and test links are in the separate matrix. Source code is the SSOT.

### 2026-11-01 FX5-ENET existence-check timer reference

[Verified FX5-ENET time-unit matrix](FX5_ENET_ALIVE_REFERENCE_20261101.md)
distinguishes `Change/Set Timer Value` factory No and the 600s/10s/3
start/interval/retry reference defaults under SH-082026ENG-H p.70. The
reference-only validator accepts documented integer seconds or milliseconds
within the official ranges; the manual page does not independently establish
an additional 100ms increment requirement. No host TCP socket timer
application or FX5 CPU built-in defaults are inferred.

### 2026-11-01 FX5 CPU firmware gate, simple CPU communication

[Official FAQ cross-check](FX5_CPU_FIRMWARE_SIMPLE_COMM_20261101.md):
FX5U/FX5UC require firmware 1.110+ for *simple CPU communication*,
whereas FX5UJ/FX5S support it from initial release (Mitsubishi
FAQ #39316). FAQ #44329 documents distinct GX Works3 setting
routes for a mixed newer/legacy CPU link. This must **not** be
mistaken for the SLMP socket server firmware matrix or a uniform
FX5 CPU/FX5-ENET threshold. The offline reference API
`inspect_reference_fx5_simple_cpu_communication` never binds a
port or changes existing listeners.

### 2026-11-01 RnCPU built-in service-specific settings

[Official RnCPU service matrix](RNCPU_BUILTIN_SERVICE_CONNECTIONS_20261101.md):
Mitsubishi FAQ #20230 states that the receiving RCPU built-in
Ethernet port uses auto-open UDP for *simple CPU communication*
and needs no extra opening configuration. FAQ #45267 establishes
a distinct *multiple GOT* scenario: TCP needs External Device
Configuration per GOT; UDP needs no open setting. Both are
reference-only and do NOT create a generic SLMP listener default,
or promote RnCPU built-in to the runnable RJ71EN71 network model.

## 1. Evidence and engineering decisions

| Hardware/interface | Editor | Officially established here | Implementation disposition |
| --- | --- | --- | --- |
| **LJ71E71-100 Ethernet module** | GX Works2 | Mitsubishi **SH-081105ENG-G** pp.35–36: buffer word 11–19 defaults and units; initial operation word 31; auto-open UDP word 20 | **Runnable opt-in model** `lj71e71` with wire profile `L`. See section 2 |
| **LCPU built-in Ethernet port** | GX Works2 | [SH-080891ENG](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080891eng/sh080891engs.pdf) includes PLC Parameter / Built-in Ethernet Port Setting, Binary vs ASCII and Enable Online Change option | **Not the LJ71E71 module**. Separate model defaults and detailed bounds need independent verification before enabling |
| **RnCPU / RnENCPU CPU built-in Ethernet portion** | GX Works3 | Existing research from [SH-081257ENG rev AD](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf), Appendix 10, identifies auto UDP/5005, MELSOFT UDP/5006, TCP/5007 | **Reference only**. Do not inherit RJ71EN71 module's nine timers, port bindings or unsupported MELSOFT handshake without own CPU verification |
| **RJ71EN71 / RnENCPU network portion** | GX Works3 | [SH-081257ENG](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf) network portion currently has an opt-in `rj71en71` preset | **Runnable, separate from CPU built-in**. Vendor TCP/IP timers remain reference only |
| **FX5 CPU built-in Ethernet (FX5U/FX5UC etc.)** | GX Works3 | [FX5 Communication SH-082625ENG-H](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082625eng/sh082625engh.pdf), SLMP setting p.100, accepts host SLMP ports 1–5548 or 5570–65534; **5549–5569 reserved**. [Mitsubishi CPU connection FAQ 24204](https://fa-faq.mitsubishielectric.co.jp/faq/show/24204) states **up to 8 concurrent external connections** for included services, with listed services excluded from the count | **Research only**. Do not force 8 on other hardware or use the simulator's global `max_clients` default as a vendor assertion. Keep port guard opt-in to the eventual FX5 hardware model |
| **FX5-ENET Ethernet module (not built-in)** | GX Works3 | [SH-082026ENG-H](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082026eng/sh082026engh.pdf), pp.69–70,79: default Binary, configurable ASCII (X/Y octal) **and** ASCII (X/Y hexadecimal), Do Not Open by Program default, SLMP own-port **blank** until configured, host ports 1–5548 or 5570–65534, system-reserved 5549–5569 | **Research only**: no fake single `ascii` mode or invented all-nine-timer factory preset. A future FX5-ENET mode needs its own ASCII numbering and supported function contract |
| **FX5-ENET module's existence-check timers** | GX Works3 | [SH-082026ENG-H p.70](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082026eng/sh082026engh.pdf): Start **600s**, interval **10s**, retry **3**, with configurable 1–16383s or 100–16,383,000ms for time (no independent 100ms step stated on this page) and 1–32767 count for retry | **Reference-only subset**. The source does *not* establish that the FX5-ENET exposes Q/R TCP ULP, zero-window, resend, FIN, IP assembly and response monitor timer knobs with identical defaults |
| **FX5 family TCP keepalive** | GX Works3 | [FX5 Communication SH-082625ENG-H p.27](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082625eng/sh082625engh.pdf) discusses keepalive probe start **5s**, repeat **5s**, and no-response disconnect **45s** in the Ethernet communications context | **Reference-only**, not a universal 5/5/45 override for every FX5 connection or a synonym of `--idle-timeout` |
| **FX5-ENET connected-count GUI** | GX Works3 | FX5-ENET module manual p.79 example screenshot shows **1/32** in a connected-count panel | An example/UI capability is not by itself the runtime simulator's default client limit. Verify application/firmware specifics before hard-coding |

## 2. LJ71E71-100 buffer memory evidence / implementation contract

[Mitsubishi **SH-081105ENG-G** pp.35–36](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081105eng/sh081105engg.pdf), section 3.5.2:

| Buffer word | Parameter | Raw initial value | Interpreted factory value |
| --- | --- | --- | --- |
| 11 (BH) | TCP ULP | 60 × 500ms | 30s |
| 12 (CH) | Zero-window | 20 × 500ms | 10s |
| 13 (DH) | Resend | 20 × 500ms | 10s |
| 14 (EH) | End | 40 × 500ms | 20s |
| 15 (FH) | IP assembly | 10 × 500ms | 5s |
| 16 (10H) | Response monitor | 60 × 500ms | 30s |
| 17 (11H) | Existence confirmation start | 1200 × 500ms | 600s |
| 18 (12H) | Existence confirmation interval | 20 × 500ms | 10s |
| 19 (13H) | Existence confirmation resend | 3 (count) | 3 |
| 20 (14H) | Auto-open UDP port | 1388H | 5000 (reference metadata; never auto-bound) |
| 31 (1FH) | Ethernet operation setting word | 0H | Binary data code (bit1=0), RUN write disabled (bit6=0), Ping existence mode (bit4=0) |

The live model id `lj71e71` must match `--profile L`. Reuse *only* confirmed shared E71 timer limits as documented by the Q/L E71 Application Manual, preserving the distinct L basic-manual provenance. Opt-in simulator behavior can enforce Binary/ASCII and RUN-write restrictions as already implemented for Q/R; report the physical hardware parity of the chosen end code/close behavior as **unverified**. All TCP/IP module timer numbers remain `reference_only` instead of configuring host TCP kernel timers.

### Example CLI (after merged model implementation)

```powershell
virtual-plc --profile L --ethernet-model lj71e71 --show-effective-ethernet
virtual-plc --profile L --ethernet-model lj71e71 --listen tcp:5000 --listen udp:5000
virtual-plc guide ethernet --json
```

Separate L and Q hardware models remain distinct even when numeric timer defaults match.

## 3. Important mismatches to avoid

1. **RnENCPU network portion != CPU built-in portion.** The first may have the RJ71EN71-compatible settings, while the CPU part has different system ports, opening controls and supported services. Never bind MELSOFT reserved ports merely because the reference matrix mentions them.
2. **LJ71E71-100 interface module != LCPU built-in Ethernet.** Do not generalize the 500ms module timer fields to the CPU's internal stack.
3. **FX5 CPU != FX5-ENET module.** The official FX5 CPU 8-connection note is not the FX5-ENET module's 1/32 GUI counter, and neither should silently replace the generic simulator `--max-clients=64`.
4. **FX5 default Binary != only two formatting modes.** FX5 offers ASCII X/Y OCT and HEX. The optional simulator `ascii_numbering="fx5-octal"` now parses octal **X/Y only** (other devices keep their base), but this is just a generic 3E/4E parser policy, **not** a runnable FX5-ENET or validated 1E interface. See [1E/3E frame contract](FX5_SLMP_FRAME_SCOPE_20261031.md) and [#22](https://github.com/greatgc-flow/VirtualPLC/issues/22).
5. **Vendor host-port restrictions != simulator operating-system rules.** The future FX5-specific strict port validation must explain that port `0` means **synthetic test-only ephemeral port**, not a PLC/GX Works configurable port; preserve local testing and refuse unsupported vendor-system service ports in strict fidelity mode.
6. **Module response monitor != SLMP per-request monitoring timer != client socket timeout != simulator idle_timeout.** They are four separate concepts. Do not import CPU/FX5 KeepAlive parameters into any other hardware model automatically.

## 4. Follow-up TDD and evidence gates

- **LJ71E71**: exact default/source/code JSON, invalid 500ms-unit overrides, `profile L` guard, RUN-write policy across TCP listeners, strict code mode, legacy `Server(profile="L")` unchanged, full Windows/Linux CI.
- **RnCPU built-in**: acquire CPU-part official parameter table (not RJ71EN71 table), verify default option status, timer set and ranges **per model/firmware**, then propose an opt-in model; no unverified whole-timer clone.
- **FX5 CPU / FX5-ENET**: verified that the official server capability is 1E/3E; **1E requires its own command-aware framing and response adapter** and is still not implemented ([#22](https://github.com/greatgc-flow/VirtualPLC/issues/22)). FX5 3E X/Y OCT numeric parsing is available as an explicit generic parser option, and a **separate opt-in `--slmp-1e` mode** handles only 1E 00..03 batch requests on synthetic Q memory; full FX5 device/subcommand and physical firmware semantics still need validation. Only then add distinct protocol profiles and module settings; validate reserved port ranges (including 5549–5569) and nonlocal safety guard before binding.
- **Timeout/KeepAlive**: first preserve sourced values as reference-only; only introduce an observable optional simulated timer when a deterministic state machine, cancellation behavior, protocol end codes and cross-platform timing tolerances are specified and tested. Avoid claiming native host kernel TCP RTO tuning reproduces firmware.
- **Physical PLC verification**: remains OPEN under [#2](https://github.com/greatgc-flow/VirtualPLC/issues/2) and [#14](https://github.com/greatgc-flow/VirtualPLC/issues/14); tests against the pinned `pymcprotocol==0.3.0` client are **client compatibility**, not physical PLC certification.

This is a source-and-gap matrix, not a claim that all models listed here are selectable by `--ethernet-model`.

### 2026-11-01 CPU-built-in remote RUN/STOP opening-method guard

[Official RnCPU preflight](RNCPU_REMOTE_OPENING_SAFETY_20261101.md):
Mitsubishi CPU manual SH-082488ENG-E p.3 explicitly warns against
`Open by Program` for external remote RUN/STOP (STOP may close the
line and prevent later remote RUN). Appendix 8 pp.684–685 identifies
Opening Method (A031H) and a *separate* CPU timer setting (A038H).
Reference-only strict offline inspector; CPU-specific factory opening
method / timer values remain UNKNOWN. No RJ71EN71 inheritance.
