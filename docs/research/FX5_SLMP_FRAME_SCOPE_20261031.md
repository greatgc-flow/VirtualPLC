# FX5 SLMP frames and X/Y ASCII numbering — implementation gate

Evidence snapshot: 2026-10-31. Implementations: [PR #21](https://github.com/greatgc-flow/VirtualPLC/pull/21) for the ASCII X/Y octal prerequisite and [PR #23](https://github.com/greatgc-flow/VirtualPLC/pull/23) for the opt-in **1E batch 00..03** parser; [PR #24](https://github.com/greatgc-flow/VirtualPLC/pull/24) for **15H/16H diagnostic** frames; [merged PR #26](https://github.com/greatgc-flow/VirtualPLC/pull/26) covers manual-scoped 04/05 random and 13/14 remote; [issue #22](https://github.com/greatgc-flow/VirtualPLC/issues/22) retains the remaining 1E commands/physical-verification gate; [issue #14](https://github.com/greatgc-flow/VirtualPLC/issues/14) for per-hardware Ethernet configuration and physical parity. Read alongside [hardware model differences](ETHERNET_HARDWARE_NEXT_20261031.md).

**Status legend:** `IMPLEMENTED_SIMULATOR` means observed behavior in VirtualPLC tests; `OFFICIAL_MANUAL` means documented vendor behavior but not verified on live equipment; `NOT_IMPLEMENTED` means unsupported. Green CI is not physical PLC certification.

## 1. Critical distinction: 1E != 3E != 4E

The official [MELSEC iQ-F FX5 SLMP manual JY997D56001-K](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/jy997d56001/jy997d56001k.pdf) documents the **1E application frame** in pp.41–55 and command inventory in pp.119–135. The [FX5-ENET official product specifications](https://www.mitsubishielectric.com/fa/products/faspec/detail.page?formNm=FX5_ENET_FX5-ENET_3695&kisyu=%2Fplcnet&lang=2&popup=1) identify SLMP 1E/3E as server protocols. VirtualPLC defaults to **3E/4E** generically and supports a separate
`--slmp-1e` option for a **bounded 1E batch + random-write + remote-control + diagnostic** parser.
**4E simulator support is not evidence that FX5 equipment supports 4E**.

| Aspect | Official 1E frame | Current VirtualPLC 3E/4E |
| --- | --- | --- |
| Request subheader (binary) | **1 byte** such as `01H` | **2 bytes** `50H 00H` (3E) / `54H 00H` (4E) |
| Response subheader (binary) | 1 byte (command + `80H`, e.g. `81H`) | 2 bytes `D0H 00H` or `D4H 00H` |
| Request header | Command-specific subheader, PC No. (FFH), monitoring timer, request data | Subheader, (4E serial), network/PC/IO/station route, length, monitoring timer, command/subcommand, request data |
| Request framing | **No 3E-style common total-length field**; command-specific lengths for TCP reassembly | Explicit per-message length in header |
| Response errors | 1-byte end code; special `5BH` includes an additional error code | 2-byte end code and existing 3E/4E error-information section |
| Transport | TCP/IP and UDP/IP, with module/application restrictions | Existing TCP/UDP support for 3E/4E only |
| Status | `OFFICIAL_MANUAL`; 00..03 batch + 15H/16H diagnostics `IMPLEMENTED_SIMULATOR` | `IMPLEMENTED_SIMULATOR` |

The 1E parser is **separate** from the 3E decoder, with per-command
bounded frames rather than an invented common 3E header. The adapter handles 00..05 on a narrow synthetic device subset, 13/14 owner-checked remote control, and 15/16 diagnostics. Further device/firmware variants require independent proof
and parser lengths.

### First runnable 1E subset / manual-derived frames

Use `--slmp-1e` or `Server(slmp_1e=True)`. The mode accepts
**only 1E**, not mixed 3E/4E. It exposes the *synthetic* Q memory,
not a vendor `fx5_enet` model; `--ethernet-model` and 3E fault plans
are incompatible. No automatic vendor listener ports or kernel timer
fidelity.

| Item | Simulated behavior | Manual reference |
| --- | --- | --- |
| Binary 01H D100..102 request | `01 FF 00 00 64 00 00 00 20 44 03 00` | p.124 |
| Binary response (D100=1234H, D101=0005H, D102=6789H) | `81 00 34 12 05 00 89 67` | p.124 |
| ASCII request, same words | `01FF00004420000000640300` | p.124 |
| ASCII response | `8100123400056789` | p.124 |
| Header | 1-byte binary / 2-character ASCII command subheader, PC=FF, timer=0, per-command device/count/fixed0 | pp.42,122,125 |
| Response | 1-byte status; errors `5B` plus 16-bit additional code | pp.44,47,137–138 |
| Count caps | 00=256 bits (count 00 =>256), 01=64 D words/32×16-bit groups, 02=160 bits, 03=64 D words/10×16-bit groups | pp.119,122,125 |
| First supported devices | M 0..7679, X/Y 0..255, D 0..7999; other devices deliberately rejected | p.121 |
| TCP/UDP | 1E TCP fragmentation/coalescing, UDP one exact frame, shared PLC state; bad header closes TCP/drops UDP | Simulator policy, no physical-equivalence claim |
| 15H binary / ASCII request | `15 FF 00 00` / `15FF0000` | p.134 |
| 15H binary / ASCII reply | **Only** `F3` byte / `F3` ASCII characters; **no batch 95/00 header** | p.134 |
| 16H binary request / reply | `16 FF 00 00 05 41 42 43 44 45` → `05 41 42 43 44 45` | pp.135–136 |
| 16H ASCII request / reply | `16FF0000054142434445` → `054142434445` | pp.135–136 |
| 16H limit | 1..254 raw bytes; ASCII 2 hex digits per byte, up to 518 request characters; reply is just count+data | pp.135–136 |

A response `5BH` with source code `C051`, `C052`, `C056`, etc.,
is a **simulated mapping from the official error-code table**, not a
measured FX5 device response. Fixed fields and unsupported/ambiguous
1E commands fail closed instead of guessing a packet length.

## 2. 1E command inventory — official manual p.119 (reference, NOT implementation)

| 1E code | Function | Bound / caveat |
| --- | --- | --- |
| `00H` | Batch bit read (1-bit units) | Up to 256 points; request count `00H` denotes 256 |
| `01H` | Batch read 16-bit bit groups / 1-word units | Up to 32 bit-words / 64 word points |
| `02H` | Batch bit write | Up to 160 points |
| `03H` | Batch write 16-bit bit groups / 1-word units | Up to 10 bit-words / 64 word points |
| `04H`, `05H` | Test / random write | Simulator: 80 individual bit points / 10 word or aligned bit-group items, atomic commit |
| `13H`, `14H` | Remote RUN / STOP | Simulator: STOP TCP owner must RUN; ownership survives disconnect; local reset clears; UDP denied |
| `15H`, `16H` | Read PC type / loopback | Implemented synthetic `F3` and raw count+data respectively; not a physical model identity |

The exact packet layout and supported code combinations depend on device family and module firmware. **00..05 plus 13..16 are in the opt-in `--slmp-1e` simulator subset**; hardware compatibility is not established. Do not claim the bounded simulator devices are a complete manufacturer list.

## 3. Implemented numeric prerequisite: FX5 3E X/Y ASCII OCT (opt-in)

FX5 manual **pp.66–67** lists input X and output Y device descriptors and the note:

- ASCII `X,Y OCT`: **octal** address numbers
- ASCII `X,Y HEX`: hexadecimal address numbers
- W/B/SB/SW remain **hexadecimal**; D/M remain **decimal**
- Binary device addresses use their own numeric fields and are unaffected

Existing `--ascii-numbering compat` remains **decimal text** (compatible with pinned `pymcprotocol==0.3.0`). `--ascii-numbering manual` remains **per-device base**, including X/Y hexadecimal. New **`--ascii-numbering fx5-octal`** parses X/Y ASCII digits in base 8 and other devices in their declared base.

Examples (when available from a source checkout):

```powershell
# Synthetic Q-class 3E/4E transport to test FX5-style ASCII OCT addressing.
# This does NOT turn the Q simulator into a real FX5 CPU or FX5-ENET.
virtual-plc --ascii-numbering fx5-octal --listen tcp:5000 --listen udp:5000
```

With this mode, `X*000010` addresses synthetic X8 (octal 10 = decimal 8), `X*000017` addresses X15 and `Y*000077` addresses Y63; `X*000008` and `X*00001A` produce a request-data error without changing memory. `W*00010A` still addresses W266. The option applies to **ASCII MC device field parsing only**; it does not change binary wire behavior, configure physical hardware, automatically select an FX5 model or enable 1E.

Legacy 4E acceptance remains a **generic simulator capability**, not an FX5-ENET vendor claim. No firmware parity inferred from the numeric mapping alone.

## 4. Hardware selection remains explicitly gated

- FX5 **CPU built-in**: max 8 external connections (service-specific exceptions).
- **FX5-ENET** module: up to 32 aggregate Ethernet connections. 1E/3E server, different port configuration, X/Y OCT/HEX option; NOT a runnable VirtualPLC hardware model.
- RnCPU **CPU built-in**: distinct RJ71EN71 network interface and system ports; NOT a runnable hardware model.
- Existing QJ71E71/LJ71E71/RJ71EN71 Ethernet options remain the only runnable `--ethernet-model` values. The metadata-only entries live in `virtual-plc guide ethernet --json` under `reference_only_models`.

References: [official Mitsubishi FX5 Ethernet product comparison](https://fa-faq.mitsubishielectric.com/fa/products/cnt/plcf/pmerit/communication/ethernet.html), [JY997D56001-K](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/jy997d56001/jy997d56001k.pdf) pp.41–45, 66–67, 119, 122.

## 5. Testing and feedback gates

New `tests/test_fx5_ascii_octal.py` verifies decimal/octal distinction, invalid digits, 3E/4E synthetic response handling, UDP reuse, legacy default behavior and that `fx5_enet` remains unsupported as hardware. The exact-source branch CI is the candidate evidence; a post-merge `main` workflow is distinct.

Tests in `tests/test_slmp_1e.py`, `tests/test_slmp_1e_random_write.py`, `tests/test_slmp_1e_remote_control.py` and `tests/test_slmp_1e_diagnostics.py`
cover manual literal replies, diagnostic framing/1..254 limits and
TCP/UDP transport boundaries; the first 1E batch tests cover binary/ASCII manual vectors, 00..03 reads/writes, 00=>256 bits, point limits, 16-bit bit groups, malformed/overlong PC and fixed fields, TCP fragmentation/coalescing, UDP and shared-memory safety. [#22](https://github.com/greatgc-flow/VirtualPLC/issues/22) remains open for expanded device/firmware maps, vendor close/owner/error semantics and physical verification. A hardware preset requires additional manufacturer/physical gates under #14 and #2. Never equate configured TCP timers or `--idle-timeout` with Mitsubishi firmware behavior.

**Operating topology:** one independent PLC per OS process; its TCP/UDP listeners share a single CPU/memory state. No in-process multi-PLC supervisor.


## 6. Official 04/05 and 13/14 layout, implementation boundary

Official evidence: Mitsubishi JY997D56001-K, printed pp.128–133
(PDF pp.129–134). These packet contracts are manual-derived, not an
actual PLC wire capture.

| 1E command | Binary request fields | ASCII request fields | Successful response |
| --- | --- | --- | --- |
| 04 bit random | 04 FF 0000 count(1) 00 + count × (head 4LE, name 2 swapped, value 1) | 04FF0000 count(2) 00 + count × (name 4 hex, head 8 hex, value 2 hex) | 84 00 / 8400 |
| 05 word random | 05 FF 0000 count(1) 00 + count × (head 4LE, name 2 swapped, value 2LE) | 05FF0000 count(2) 00 + count × (name 4 hex, head 8 hex, value 4 hex) | 85 00 / 8500 |
| 13 RUN | 13 FF 0000 | 13FF0000 | 93 00 / 9300 |
| 14 STOP | 14 FF 0000 | 14FF0000 | 94 00 / 9400 |

For 04, supported M/X/Y bit values are strictly 0/1, max 80 items.
For 05, supported D words and M/X/Y 16-point bit groups are max 10 items;
bit groups must be 16-aligned. The full request is validated before
a single staged memory commit; duplicate destinations apply in request
order (last wins). Untrusted count up to 255 is bounded to a maximum
4092-byte 1E request for an ASCII 05H frame, while actual point caps
remain enforced by error response.

**Owner safety policy vs manufacturer:** The manual states remote STOP
can only be released by RUN from the same originating external device,
with remote-operation information lost on power reset. It does **not**
grant rights to a second connection merely because the first closed.
VirtualPLC stores the accepted TCP connection ID, denies foreign 13/14
using a *simulated* C05F error, and keeps STOP on disconnect. Explicit
local `Server.reset_1e_remote_control()` clears ownership
without automatically starting the CPU. UDP 13/14 is rejected because
there is no trustworthy connection continuity. Neither the selected
error code nor the fail-closed recovery policy claims real FX5 firmware
parity. Physical oracle, hardware variant and PyPI release remain HOLD.


### Offline read-only manual vectors (no network or PLC access)

The separate [offline oracle guide](../PHYSICAL_ORACLE.md) and
`virtual_plc/oracle.py` expose a 15H/16H binary/ASCII manual plan,
unfilled observation template and redacted comparison report. These
manufacturer pp.134–136 examples may be compared against separately
collected responses; a match never certifies full real-hardware parity.

### Physical RUN/STOP selector switch: confirmed hardware gap

Mitsubishi JY997D56001-K, printed page 132 (PDF zero-index page
133), states that an authorized remote RUN command can **return normally
without moving the accessed CPU to RUN** when its physical selector is
STOP. PR #28 introduces an explicit static simulator switch via
`slmp_1e_run_switch="STOP"` with `initial_state="STOP"`. Authorized 13H
returns 93 00/9300 while SD203 and state remain STOP, but STOP owner
information clears. This is an **opt-in simulator model** of one documented
condition; no verified physical-device behavior or dynamic selector changes
are implied. Omitted/default switch remains RUN as before.

Local `Server.get_1e_remote_control_status()` exposes
`cpu_state`, `owned`, `owner_connected`, `orphaned` and
`owner_connection_id` under the shared request lock. Connection closure
does not release STOP ownership; a worker must observe EOF/timeout before
`owner_connected` becomes false. Local reset leaves STOP. This is an
operator-facing simulator invariant, not a hardware specification.
