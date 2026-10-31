# FX5 SLMP frames and X/Y ASCII numbering — implementation gate

Evidence snapshot: 2026-10-31. Implementation: [PR #21](https://github.com/greatgc-flow/VirtualPLC/pull/21) for a **small numeric-encoding prerequisite**; [issue #22](https://github.com/greatgc-flow/VirtualPLC/issues/22) for actual 1E frame support; [issue #14](https://github.com/greatgc-flow/VirtualPLC/issues/14) for per-hardware Ethernet configuration and physical parity. Read alongside [hardware model differences](ETHERNET_HARDWARE_NEXT_20261031.md).

**Status legend:** `IMPLEMENTED_SIMULATOR` means observed behavior in VirtualPLC tests; `OFFICIAL_MANUAL` means documented vendor behavior but not verified on live equipment; `NOT_IMPLEMENTED` means unsupported. Green CI is not physical PLC certification.

## 1. Critical distinction: 1E != 3E != 4E

The official [MELSEC iQ-F FX5 SLMP manual JY997D56001-K](https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/jy997d56001/jy997d56001k.pdf) documents the **1E application frame** in pp.41–55 and command inventory in pp.119–135. The [FX5-ENET official product specifications](https://www.mitsubishielectric.com/fa/products/faspec/detail.page?formNm=FX5_ENET_FX5-ENET_3695&kisyu=%2Fplcnet&lang=2&popup=1) identify SLMP 1E/3E as server protocols. Current VirtualPLC accepts **3E/4E** generically; **4E simulator support is not evidence that FX5 equipment supports 4E**.

| Aspect | Official 1E frame | Current VirtualPLC 3E/4E |
| --- | --- | --- |
| Request subheader (binary) | **1 byte** such as `01H` | **2 bytes** `50H 00H` (3E) / `54H 00H` (4E) |
| Response subheader (binary) | 1 byte (command + `80H`, e.g. `81H`) | 2 bytes `D0H 00H` or `D4H 00H` |
| Request header | Command-specific subheader, PC No. (FFH), monitoring timer, request data | Subheader, (4E serial), network/PC/IO/station route, length, monitoring timer, command/subcommand, request data |
| Request framing | **No 3E-style common total-length field**; command-specific lengths for TCP reassembly | Explicit per-message length in header |
| Response errors | 1-byte end code; special `5BH` includes an additional error code | 2-byte end code and existing 3E/4E error-information section |
| Transport | TCP/IP and UDP/IP, with module/application restrictions | Existing TCP/UDP support for 3E/4E only |
| Status | `OFFICIAL_MANUAL` and `NOT_IMPLEMENTED` | `IMPLEMENTED_SIMULATOR` |

The 1E parser must not be wired into the existing 3E decoder just by accepting subheaders. It needs its **own bounded command-aware framing adapter**, with explicit opt-in and canonical dispatch only for validated mappings.

## 2. 1E command inventory — official manual p.119 (reference, NOT implementation)

| 1E code | Function | Bound / caveat |
| --- | --- | --- |
| `00H` | Batch bit read (1-bit units) | Up to 256 points; request count `00H` denotes 256 |
| `01H` | Batch read 16-bit bit groups / 1-word units | Up to 32 bit-words / 64 word points |
| `02H` | Batch bit write | Up to 160 points |
| `03H` | Batch write 16-bit bit groups / 1-word units | Up to 10 bit-words / 64 word points |
| `04H`, `05H` | Test / random write | Up to 80 bit points / 10 word points as applicable |
| `13H`, `14H` | Remote RUN / STOP | May have owner-specific state restrictions |
| `15H`, `16H` | Read PC type / loopback | Need independent response format and identity |

The exact packet layout and supported code combinations depend on device family and module firmware. These values are **not** enabled by a setting in this phase.

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

Future 1E milestone [#22](https://github.com/greatgc-flow/VirtualPLC/issues/22) must independently verify 1E binary and ASCII packets, command-specific length bounds, TCP partial/coalesced input, one-frame UDP, 1E end-code formatting, vendor point limits and model-specific device compatibility. A hardware preset requires additional manufacturer/physical gates under #14 and #2. Never equate configured TCP timers or `--idle-timeout` with Mitsubishi firmware behavior.

**Operating topology:** one independent PLC per OS process; its TCP/UDP listeners share a single CPU/memory state. No in-process multi-PLC supervisor.
