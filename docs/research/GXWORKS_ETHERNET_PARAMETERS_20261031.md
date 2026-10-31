# GX Works2 / GX Works3 Ethernet parameter research

> Research snapshot: 2026-10-31 KST. Applies to VirtualPLC main >= `b6a3450`.  
> Implementation tracking: [#14](https://github.com/greatgc-flow/VirtualPLC/issues/14).  
> **Scope:** one virtual PLC per **OS process** (owner decision [#13](https://github.com/greatgc-flow/VirtualPLC/issues/13)); multiple TCP/UDP ports within that process share one PLC state.  
> Official-manual facts below do **not** imply the simulator already emulates them or is physically PLC-validated.

## 1. Source and model identification (do not select by GX Works version alone)

| Engineering context | Hardware/module scope | Parameter paths / evidence |
| --- | --- | --- |
| GX Works2, Q/L external E71 | QJ71E71-100/-B5/-B2, LJ71E71-100 | Network Parameter -> Ethernet/CC IE/MELSECNET (Q) or Ethernet/CC IE Field (L) -> Operation Setting / Initial Setting / Open Setting. [GX Works2 common, SH-080779ENG](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080779eng/sh080779engar.pdf); [Q/L E71 application, SH-080010](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080010/sh080010r.pdf) |
| GX Works2, built-in CPU Ethernet | QCPU / LCPU built-in port | PLC Parameter -> Built-in Ethernet Port Setting -> Open Setting (Protocol TCP/UDP, MC Protocol, local port, data code). Not interchangeable with external E71 module. [GX Works2 common](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080779eng/sh080779engar.pdf), [LCPU built-in manual](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080891eng/sh080891engs.pdf) |
| GX Works3, iQ-R network module | RJ71EN71 or RnENCPU **network part** | Parameter -> Module Information / relevant RJ71EN71 module -> Basic Settings (own node, external device configuration, transmission ports); Application Settings -> Timer Settings for Data Communication. [SH-081257ENG rev AD](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf), pp.321-325, 396-398, Appx 10 |
| GX Works3, iQ-R built-in CPU | RnCPU or RnENCPU **CPU/built-in Ethernet part** | Parameter -> CPU -> Module Parameter -> Basic / Application Settings. System port numbers differ from RJ71EN71. [SH-081257ENG rev AD](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf), Appx 10 |
| GX Works3, iQ-F | FX5U/FX5UC, FX5-ENET / FX5-ENET/IP (check exact edition/firmware) | Parameter -> module -> Module Parameter -> Ethernet Port -> Basic Settings / External Device Configuration. [SH-082625ENG rev G](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082625eng/sh082625engg.pdf), pp.39,47,95 |
| GX Works3 navigation only | GX Works3 editor | Basic Settings -> External Device Configuration -> Detailed Setting; for CPU/module the navigation path differs. [GX Works3 Operating Manual SH-081215ENG](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081215eng/sh081215engaq.pdf) and [training manual SH-081820ENG](https://dl.mitsubishielectric.com/dl/fa/document/schooltext/school_text/sh081820eng/sh081820enga.pdf) |

The editor is an interface to *hardware-specific module parameters*. Avoid generic `gxworks2` and `gxworks3` factory-default presets with unqualified applicability.

**LJ71E71-100 confirmed independently:** [SH-081105ENG-G pp.35–36](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081105eng/sh081105engg.pdf) lists buffer words 11–19 defaults 60/20/20/40/10/60/1200/20/3 (500ms unit except retry count), word 20 auto-open UDP 0x1388 (5000), and initial word 31 = 0 (Binary, RUN write disabled). The runnable model is `lj71e71` with `profile=L`, **not a Q hardware alias**. See [RnCPU/FX5 next hardware evidence](ETHERNET_HARDWARE_NEXT_20261031.md) for more distinctions and remaining unknown defaults.

## 2. Confirmed default Ethernet timer matrix

Values in this table are **module defaults** in seconds (or counts). The Q/L E71 raw GX Works2 field is in **500ms ticks**, so raw 60 means 30s. iQ-R uses seconds or milliseconds with a 100ms step.

| Canonical key | GX Works2 Q E71 raw 500ms ticks | Q E71 effective default | GX Works3 iQ-R Ethernet default | Purpose |
| --- | ---: | ---: | ---: | --- |
| `tcp_ulp_ms` | 60 | 30s | 30s | Lifetime/timeout of TCP segment delivery in module |
| `tcp_zero_window_ms` | 20 | 10s | 10s | Check flow-control window recovery |
| `tcp_resend_ms` | 20 | 10s | 10s | TCP retransmission wait |
| `tcp_end_ms` | 40 | 20s | 20s | TCP FIN close monitoring |
| `ip_assembly_ms` | 10 | 5s | 5s | IP fragment reassembly wait |
| `response_monitor_ms` | 60 | 30s | 30s | Module-specific command response/fragment monitoring |
| `alive_start_ms` | 1200 | 600s | 600s | Begin idle-peer existence confirmation |
| `alive_interval_ms` | 20 | 10s | 10s | Repeat existence check |
| `alive_retries` | 3 (count) | 3 | 3 | Number of repeated checks |

Sources: Mitsubishi [Q-series transition handbook, p.3-28 (GX Works2 screenshot)](https://dl.mitsubishielectric.co.jp/dl/fa/document/catalog/plca/l08050eng/l08050engi.pdf), [Q E71 Basic SH-080009ENG, buffer memory default table](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080009/sh080009x.pdf), and [iQ-R Ethernet Application SH-081257ENG rev AD, pp.396-398](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf).

**Q/L E71 change ranges:** ULP, zero-window, resend, end, response monitor generally 2..32767 * 500ms; IP assembly 1..32766 * 500ms; alive start/interval 1..32767 * 500ms; alive retry 1..32767 counts, per [SH-080010ENG application p.35](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080010/sh080010r.pdf) (cross-check hardware edition).

**iQ-R range:** timer settings in seconds 1..16383 or milliseconds 100..16,383,000 in 100ms increments; alive retry 1..99999 counts, per SH-081257ENG pp.396-398. `Change/Set Timer Value = No` is the default; in that state the module uses factory defaults. The manual recommends
`response_monitor >= tcp_ulp >= tcp_end >= tcp_resend >= ip_assembly`
and `tcp_resend == tcp_zero_window` for the module. Enforce this **only for applicable hardware profiles**, not as a global restriction on user-defined simulator TCP idle behavior.

## 3. Feature-specific timers are NOT universal Ethernet timeouts

- **iQ-R Simple Device Communication (application function)**, in the Send/Receive Parameter Setting: `Timeout Time = 1000ms`, `Timeout Retry Count = 3`, `Monitoring Time At Error = 30s` (ranges 10..65535ms / 0..255 / 1..300s). These fields govern that application flow, **not** a generic MC/SLMP read timeout. Source [SH-081257ENG p.392](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf).
- **SLMP request header monitoring timer (each request):** `0000H` means unlimited waiting for the access destination; `0001H..FFFFH` = 1..65535 * 250ms. Own-station normal-operation recommendation 0.25..10s; other-station 0.5..60s. It is neither a server-side socket idle timeout nor a fixed client API timeout. Source [SLMP Reference Manual SH-080956ENG p.24](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080956eng/sh080956engm.pdf). VirtualPLC currently parses but does **not** enforce `request.timer`, because own-station command dispatch executes immediately without a modeled PLC scan/end-processing delay.
- **FX5 built-in Ethernet in the MELSOFT/GOT via hub context:** source describes TCP KeepAlive beginning at 5s of inactivity, repeating at 5s intervals and closing after 45s without response. This must not be generalized to every iQ-F SLMP server connection or mapped to application `idle_timeout`. Source [SH-082625ENG rev G p.47](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082625eng/sh082625engg.pdf). FX5 other default timer fields require a separate model/firmware verification.

## 4. Basic / open / port defaults differ materially by model

| Item | Verified scope | Default / range | Simulator gap |
| --- | --- | --- | --- |
| Communication Data Code | iQ-R own node settings | Binary (ASCII available) | VirtualPLC currently auto-accepts both; strict hardware profile may need code-mode restriction |
| Opening Method | iQ-R basic | Do Not Open by Program (other choice Open by Program) | VirtualPLC currently listens when started; no ladder-controlled OPEN state |
| Enable/Disable Online Change | iQ-R basic, SLMP writes while CPU RUN | Disable All (SLMP) | VirtualPLC allows writes during RUN; optional hardware profile must test CPU-state gating without breaking legacy Q compatibility |
| Passive connection restrictions | RJ71EN71 and FX5 external-device configuration | Unpassive (any peer) vs Fullpassive (specified peer), TCP Active for outbound | VirtualPLC is currently a passive MC server; no outbound active-open or peer-allowlist emulation |
| QJ71E71 auto-open UDP | Q E71 module | UDP/5000 = `1388H` | Do not silently bind without explicit profile/opt-in |
| iQ-R RJ71EN71/RnENCPU *network part* system ports | That network module only | auto UDP/5000; MELSOFT UDP/5001; MELSOFT TCP/5002 | MELSOFT is not equivalent to generic MC server support |
| iQ-R RnCPU / RnENCPU *CPU built-in* system ports | That CPU part only | auto UDP/5005; MELSOFT UDP/5006; MELSOFT TCP/5007 | Separate model key needed; do not copy network-part ports |
| FX5 SLMP Connection Module host-port range | FX5 built-in Ethernet / FX5-ENET per SH-082625ENG p.95 | 1..5548 or 5570..65534; 5549..5569 reserved | Optional model-specific validation; `--listen ...:0` remains useful for synthetic tests |

Sources: [Q E71 Basic SH-080009ENG](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080009/sh080009x.pdf) p.39; [iQ-R Ethernet Application](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh081257eng/sh081257engad.pdf) pp.322-325 and Appx 10 pp.553-555; [FX5 Communication](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/sh082625eng/sh082625engg.pdf) p.95.

**Critical distinction:** Actual iQ-R models reserve/open several ports for automatic SLMP, MELSOFT, discovery and other purposes. If an emulator has no matching service implementation, opening those ports and advertising their behavior would be misleading. Port defaults should first be presented as reference metadata; `--listen` remains explicit unless opted into a validated model port plan.

## 5. Technical feasibility: what can be accurately implemented

| Class | Example | Fidelity plan |
| --- | --- | --- |
| Fully deterministic application | Explicit TCP/UDP port plan, profile-specific port validation, binary-vs-ASCII accept, configured CPU RUN write gate, source-peer restriction, connection ceilings, start/stop policy | Implement behind opt-in hardware model and independent tests with well-defined simulated behavior |
| Module/application behavior with limited fidelity | Simulated response delay/monitor error, simple-device communication timeout/retry, alive-check scheduling | Implement only with a matching application state machine and evidenced error semantics; never equate to client-side timeout |
| Host OS / kernel behavior | TCP RTO/ULP, zero-window probing, FIN close timing, IP fragment reassembly, ICMP/PING and kernel KeepAlive | Windows/Linux sockets own these; native Python cannot promise bit-for-bit Mitsubishi firmware behavior. Record defaults and report `reference-only` or explicitly `approximate`, not pretend exact emulation |
| SLMP client behavior | Per-request 250ms monitoring timer, client connect/read timeout, retries | Keep separate from module settings; optional simulator test scenarios may defer responses within a documented emulation mode |

All behavior stays local/test-only; nonlocal binding still needs explicit `--allow-nonlocal` + positive `--idle-timeout`, irrespective of model's manufacturer defaults. This safety guard is **not** overwritten by hardware profile defaults.

## 6. Minimal implementation plan (separate issue #14)

1. **Single source of truth**: define model IDs `qj71e71`, `lj71e71` (alias only if verified), `rj71en71`, `rn_cpu_builtin`, `fx5_builtin`, `fx5_enet`. Add per-setting type, units, range, factory-default, source citation/page, applicability, and fidelity status. Unknown defaults stay explicitly unknown. Verify L and FX5 independently instead of copying Q/R.
2. **Minimal UX**: optional `--ethernet-model MODEL`, optional `--ethernet-config FILE` JSON overrides, and `virtual-plc guide ethernet --json` (names proposed, not implemented). Effective-settings reporting must distinguish *configured reference value* from *applied simulated behavior*. No automatic multi-PLC process supervision.
3. **Preserve legacy**: unchanged `virtual-plc --port 5000` TCP-only, `Server(profile="Q")` existing semantics, and existing multi `--listen` syntax. New strict model behavior is opt-in and defaults to the selected **hardware** profile, not the selected editor version.
4. **Priority for actual behavior**: (P1) model-specific binary/ASCII, RUN write policy, open/passive peer policy, port/duplicate/reserved constraints; (P2) optional alive-check and application timeout state machines; (P3) reference-only OS-stack timers without a false operational claim.
5. **Validation**: table-driven exact factory defaults and units/limits; override precedence, invalid ranges; run/stop writes, one shared PLC across ports, UDP/TCP interleaving, Win/Linux network behavior, release and compatibility gates; manual cross-verification and physical-PLC evidence remain separate. `pymcprotocol==0.3.0` stays the pinned upstream oracle.

## 7. Open evidence / limitations

- Different GX Works software versions may expose different fields. Apply only to identified CPU/module (and firmware when semantics differ); project-file parsing and native GX Works configuration import are **not** validated.
- Confirm Q built-in, L built-in, FX5 built-in/module limits and timeout defaults separately before claiming a full vendor-fidelity preset. The Q E71 and iQ-R values above are *official-manual verified*, not measured on physical hardware.
- Determine whether or how the source module honors SLMP monitoring timers for own-station access and any timeout-related end codes before emulating them; no invented end codes.
- Preserve manual verification backlog [#2](https://github.com/greatgc-flow/VirtualPLC/issues/2) and remote-password [#5](https://github.com/greatgc-flow/VirtualPLC/issues/5) unchanged.

## 8. Owner topology decision

**One process = one independent PLC.** Independent PLCs use independent processes; all listeners within one process share its memory and control state. No embedded multi-PLC manager, cross-Server shared memory, or in-process supervisor (see [#13](https://github.com/greatgc-flow/VirtualPLC/issues/13)).
