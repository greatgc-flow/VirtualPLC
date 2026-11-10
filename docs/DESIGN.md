# VirtualPLC — Design

**Whole-pack PDF input preflight (PR #46, 2026-11-02):**
The developer-only manual evidence kit validates every edition's tuple shape,
file signature/size and SHA-256 uniqueness before performing any text
extraction. Malformed or duplicate late sources no longer cause earlier
`pdftotext` subprocess calls. Existing post-extraction and final whole-pack
source rechecks remain, with unchanged report schema and manufacturer
`NOT_VERIFIED` status. This is a COMPACT, delivery-tool-only safeguard,
not PDF authenticity or hardware qualification.

**Final cross-source evidence integrity audit (PR #45):**
The optional offline PDF kit re-fingerprints *all* originals after scanning
every supplied edition and family. The previous per-file post-extraction
checks remain in place. A later extraction that alters an earlier PDF now
invalidates the entire report rather than retaining an obsolete SHA-256.
This does not establish publisher authenticity, preserve PDFs through all
concurrent filesystem races, verify AD/AG or E/I clause parity, or affect
runnable PLC networking. The report schema and tool dependencies stay fixed.
[PR #45](https://github.com/greatgc-flow/VirtualPLC/pull/45).

**Atomic offline evidence report publication (PR #44):**
The developer-only PDF evidence kit stages JSON in the destination
directory, flushes/fsyncs the staging file, and publishes via atomic
replace only with explicit `--overwrite`, or exclusive hard-link creation
otherwise. On publication failure, existing reports are preserved and
staging is cleaned. Filesystems without hard-link support fail closed.
Console/JSON output, source-revision `NOT_VERIFIED` gates and simulator
runtime semantics remain unchanged. This is not vendor PDF authentication
or guaranteed power-loss durability (parent directory not fsynced).
[PR #44](https://github.com/greatgc-flow/VirtualPLC/pull/44).

**PDF evidence chain-of-custody safeguard (PR #43):**
Local offline manual-evidence reports reject duplicate input SHA-256
across all edition roles and rehash each source after text extraction,
failing closed if the original bytes changed. This ensures a report's
captured digest is consistent with its source during extraction and
prevents one document from masquerading as multiple revisions.
It is not vendor authentication or a complete defense against
concurrent filesystem modification; human clause review remains
mandatory. The tool remains separate from the installed simulator.
[PR #43](https://github.com/greatgc-flow/VirtualPLC/pull/43).

**Developer-only offline manual PDF evidence candidate utility (PR #42):**
`tools/manual_revision_evidence.py` is an independent stdlib-only
local CLI, separate from the runnable simulator and manufacturer SSOT.
It requires locally obtained PDF edition **pairs** (Ethernet AD+AG,
CPU E+I) and optional local `pdftotext`; it does not download or
publish source PDFs, access a PLC, or update `ethernet_reference.py`.
It fingerprints each PDF with SHA-256, checks a weak edition label,
and emits bounded, 1-based *PDF-page* keyword candidates for manual
clause comparison. Identical keyword counts cannot certify that
pages/clauses or hardware behavior are equivalent: output status
remains `SOURCE_CLAUSE_REVIEW_REQUIRED`,
`manual_revision_equivalence=NOT_VERIFIED`, and
`physical_hardware_certified=false`. GitHub CI uses synthetic
PDF headers/text rather than proprietary source PDFs. Manual review
and source provenance evidence are still required to lift a gate.
[Runbook](research/RNCPU_MANUAL_PDF_EVIDENCE_KIT_20261101.md),
[PR #42](https://github.com/greatgc-flow/VirtualPLC/pull/42).

**Two independently revision-gated R04CPU manual sources (PR #41):**
`inspect_reference_r04cpu_configuration` keeps the existing
`manual_revision` input for Ethernet Application `SH-081257ENG-AD`
(new manufacturer-listed AG, clauses **NOT_VERIFIED**) and now accepts
optional `cpu_manual_revision` for CPU Module `SH-082488ENG-E`
(new manufacturer-listed I 2026-08, clauses **NOT_VERIFIED**).
Only CPU opening-method `A031H` uses the CPU manual gate; Ethernet
A038H timer and external-device port/slot checks remain independently
AD-scoped. An explicitly newer/unverified CPU edition blocks
`REFERENCE_CHECKS_ONLY` if the Opening Method was supplied; omitted
CPU edition preserves legacy status, and missing Opening Method is
not replaced by invented default settings. Both revision gates derive
from the one `ethernet_reference.py` vendor registry. Exact specs and
strict input semantics:
[dual-manual source evidence](research/RNCPU_R04CPU_DUAL_MANUAL_REVISION_GATES_20261101.md).
This does not certify GX Works3, manufacturer edition parity or real PLC
behavior. [PR #41](https://github.com/greatgc-flow/VirtualPLC/pull/41).

**Runnable vs offline manufacturer-reference ownership (PR #40):**
`virtual_plc/ethernet.py` owns only runnable Q/L/iQ-R Ethernet settings
and validates effective overrides; `virtual_plc/ethernet_reference.py`
owns the FX5/FX5-ENET/RnCPU official-source-scoped **offline** reference
registry and all seven reference inspectors plus `reference_catalog`.
The legacy `virtual_plc.ethernet` re-exports the exact same function/data
objects (no wrapper or second vendor table). The dependency is one-way:
runnable module -> offline-only reference; not vice versa. The source registry
was moved byte-for-byte unchanged apart from new module header/import.
Reference-only models never become executable `EthernetSettings` presets.
No new runtime API, network behavior, manuals/source equivalence claims or
physical hardware certification. Revision AG vs reviewed AD remains
**NOT_VERIFIED**. Structural/parity tests: `tests/test_ethernet_reference_boundary.py`;
existing run/client/CLI/source tests are unchanged. See
[PR #40](https://github.com/greatgc-flow/VirtualPLC/pull/40) and
[VerySimpleGuide](https://github.com/greatgc-flow/VerySimpleGuide).

**UDP transport/dispatch boundary (behavior-preserving refactor, PR #39):**
`Server._udp_loop` owns OS datagram receive/drop, socket send and shutdown;
private `Server._udp_response(packet)` owns exactly-one-frame validation,
1E or 3E/4E source-specific dispatch under the existing shared request
lock, post-dispatch response_hook once, and response-size gating.
The caller continues to reject empty or >8192-byte UDP datagrams before
dispatch, preserve malformed-frame drop and catch behavior, and suppress
response sends during shutdown. No TCP framing/fault changes, real PLC
network access, public CLI options or hardware parity claim.
Characterization is in `tests/test_udp_dispatch_refactor.py`, while the
existing socket integration suites retain on-wire parity coverage.
See [PR #39](https://github.com/greatgc-flow/VirtualPLC/pull/39).

**R04CPU CPU built-in complete *offline* settings review:**
`virtual_plc.rncpu_reference.inspect_reference_r04cpu_configuration`
composes the existing R04CPU opening-method, A038H timer and multi-entry
external-device inspectors without duplicating their vendor SSOT.
Input sections are explicitly optional, missing/null/empty are distinct,
and the caller's manual revision is gated against the reviewed
SH-081257ENG-AD (newer AG: **NOT_VERIFIED**, not assumed equivalent).
It checks only manually transcribed source-scoped settings and returns
independent diagnostics, never a GX Works3 native-project verdict,
SLMP/OS timing claim, active client count or physical PLC certification.
Only `R04CPU` CPU **built-in** is accepted; RJ71EN71 remains separate.
See [composite preflight](research/RNCPU_R04CPU_COMPOSITE_PREFLIGHT_20261101.md)
and [PR #38](https://github.com/greatgc-flow/VirtualPLC/pull/38).

Status: implemented M0–M7. Public behavior is documented in [BEHAVIOR](BEHAVIOR.md),
response faults in [FAULTS](FAULTS.md), and installation/safety in [README](../README.md).
Purpose: a local Mitsubishi MC-protocol PLC simulator compatible with the wire-visible
features of
[pymcprotocol](https://github.com/greatgc-flow/pymcprotocol) 0.3.0 (the client). Default
profile: **Q series**.
Not for industrial use. Binds 127.0.0.1 by default.

`virtual_plc/server.py` `is_loopback_host` is the single predicate used by `Server()` (server.py) and the CLI (__main__.py) for the localhost-only rule; [README Safety](../README.md#safety) is the user-facing SSOT.

**Offline manufacturer vector oracle (separate from simulator networking):**
`virtual_plc/oracle.py` defines four manual-derived 1E 15H/16H binary/ASCII
read-only request/response cases and a minimal offline plan/template/compare CLI.
A self-reported model/interface/firmware provenance contract, strict
request matching, SHA-256-only redacted report, and atomic stdout-identical
file output avoid confusing a manual/simulated result with real PLC parity.
No socket or PLC control operation exists in this utility; see
[offline procedure](PHYSICAL_ORACLE.md).

**SLMP 1E (opt-in):** `virtual_plc/one_e.py` owns the 1E parser/codec and 1E-specific codes `0xC05B`, `0xC05F`, `0xC060` (shared codes in [BEHAVIOR](BEHAVIOR.md#slmp-1e-transport-opt-in)), with `Server.get_1e_remote_control_status()` and `reset_1e_remote_control()`; `guide divergences` points to `BEHAVIOR` for the 1E contract, and [FX5 1E/3E protocol scope](research/FX5_SLMP_FRAME_SCOPE_20261031.md) owns manual vectors.

**FX5 offline SLMP host-port metadata (not a runtime model):**
`virtual_plc.ethernet.inspect_reference_slmp_port(model, port)` reads
reference-only GX Works3 FX5 CPU/ENET vendor port ranges and classifies
recommended/permitted/system-reserved/invalid values. It never binds a
socket or modifies the default server. The FX5 CPU 8 combined Ethernet
sessions and the FX5U/UC 16 targets for *simple CPU communication* are
separate scoped counts with independent official sources. See
[FX5 scope matrix](research/FX5_SLMP_PORT_SCOPE_20261031.md).

**RnCPU built-in application-specific external settings (reference-only):**
`reference_catalog()["rncpu_builtin"]["service_connection_reference"]`
separates the receiving RCPU auto-open UDP *simple CPU communication*
scenario from the multiple-GOT built-in-port TCP/UDP configuration
scenario. These source-only Mitsubishi FAQ facts do not imply a generic
SLMP socket/open setting, automatic listeners or MELSOFT/GOT protocol
support. RnCPU built-in remains separate from RJ71EN71 network module;
see [RnCPU service matrix](research/RNCPU_BUILTIN_SERVICE_CONNECTIONS_20261101.md).

**FX5 CPU simple communication firmware gate (reference-only):**
`inspect_reference_fx5_simple_cpu_communication(model, firmware_version)`
uses official Mitsubishi FAQ #39316's distinct FX5U/FX5UC >=1.110 and
FX5UJ/FX5S from-first rules. FAQ #44329's mixed-firmware interop
GX Works3 path applies only where documented; unsupported/unknown
firmware is not conflated and early UJ/S path remains unknown.
The SSOT belongs in `virtual_plc/ethernet_reference.py` (re-exported by `virtual_plc/ethernet.py`),
not runnable settings; simple CPU target limits are not SLMP TCP sockets.
See [FX5 firmware gate](research/FX5_CPU_FIRMWARE_SIMPLE_COMM_20261101.md).

**FX5-ENET alive-check timer range (reference only):**
`inspect_reference_fx5_enet_alive_timers(overrides=None)` performs pure
metadata validation for the FX5-ENET expansion module's documented
existence-check settings (start, interval, retry), with an explicit
Change/Set Timer Value flag. The SSOT is `virtual_plc/ethernet_reference.py` (re-exported by `virtual_plc/ethernet.py`);
seconds/milliseconds are different allowed units with documented bounds,
not host TCP retransmission/idle timeouts. No server configuration changes.
See [manufacturer comparison](research/FX5_ENET_ALIVE_REFERENCE_20261101.md).

**GX Works2 / GX Works3 hardware-specific Ethernet mode (opt-in):**
[usage/config/effective-settings guide](ETHERNET_MODEL_SETTINGS.md) and
[official-manual timer/port/open-setting research](research/GXWORKS_ETHERNET_PARAMETERS_20261031.md).
The single source of truth for the implemented runnable model defaults, ranges, sources
and fidelity is `virtual_plc/ethernet.py` (with offline FX5/RnCPU reference metadata in `virtual_plc/ethernet_reference.py` and `virtual_plc/rncpu_reference.py`), exposed through
`virtual-plc guide ethernet --json` and `--show-effective-ethernet`.
The supported model keys are `qj71e71` (Q), `lj71e71` (L), and
`rj71en71` (iQ-R), with independent official manual sources.
[Remaining RnCPU/FX5 hardware gaps](research/ETHERNET_HARDWARE_NEXT_20261031.md)
are separate from runnable presets. Those interfaces are exposed as
`reference_only_models` in the existing `guide ethernet --json` output;
only entries under `models` may be used with `--ethernet-model`.
The CLI infers the matching wire profile unless the user specifies an explicit
`--profile` (then mismatches are errors). Explicit override provenance is
preserved even when a configured value equals the factory default.
This follows [VerySimpleGuide](https://github.com/greatgc-flow/VerySimpleGuide):
small interfaces, one source of truth, no invented unknown vendor defaults.
Only model-selected binary/ASCII wire mode and RUN-write policy are simulated;
OS network-stack and manufacturer timers are reference-only. Legacy Q mode and
socket `idle_timeout` are not modified. The broader fidelity backlog remains
in [#14](https://github.com/greatgc-flow/VirtualPLC/issues/14).
**One independent PLC per OS process**; multiple listeners within that
process share one PLC state.

## Optional multi-listener transport extension

A per-Server reentrant lifecycle lock serializes externally invoked
`start()` and `stop()`, including rollback that calls `stop()` during a
partially started worker group. It closes a race where stop returned while
start was still binding and a race where two starts created separate packs.
The existing request lock remains independent: concurrent TCP writes and
UDP reads share atomic memory dispatch, but lifecycle locking does not
hold the request lock across normal command handling. Other Server
instances keep independent lifecycle locks; one PLC remains one process.

**In-flight shutdown boundary (PR #50):** `_serve_frames` has an outer
recv loop and an inner loop for pipelined TCP frames. The outer stop check
alone did not protect buffered later frames: if shutdown happened during
dispatch of the first frame, a subsequent buffered write could still mutate
memory. The inner loop now checks the existing shutdown event before
starting *each next frame*. An in-flight dispatch still completes; no
transaction cancellation/rollback is implied. The UDP worker already
suppresses response sends after stop; a separate real-loopback regression
covers its pending response hook and restart. This is not a physical PLC
shutdown/firmware behavior claim.

**UDP receive/parse shutdown boundary (PR #51):** response suppression
alone does not prevent a late UDP write from mutating Memory. The UDP
worker now checks `_stopping` immediately after `recvfrom` returns,
in addition to its outer loop/send checks. If decoding or 1E framing
overlaps shutdown, `_udp_response` checks the same stop event *inside*
the existing shared request lock, just before starting 1E or 3E/4E
dispatch. This does not add a second lock, change wire formats, or
cancel a dispatch already in progress. The policy applies to one Server
per PLC process; real equipment behavior remains unverified.

Accepted TCP peers are configured with `TCP_NODELAY` and `idle_timeout`
independently of the listener lifecycle. A socket-configuration `OSError`
closes only the failed accepted peer; the accept worker continues processing
future peers, without allocating a worker or reserving a global client slot
for the failed connection. This fail-isolated behavior is tested for both
socket options under issue #13; no UDP, wire, vendor or release changes.

`Server(listeners=[("tcp", 5000), ("udp", 5000)])` optionally binds
several protocol/port pairs in one process; the CLI equivalent is repeatable
`--listen`. Omitted means the legacy single TCP port. The listener collection
is transport-only: **one Server instance** owns memory, CPU state, password
simulation, fault selection and the one request lock, so no shared-Memory
cross-Server concurrency is introduced. Per-protocol duplicate fixed ports
are rejected; TCP and UDP can share a numeric port, and port 0 requests a
fresh ephemeral bind. Bind all sockets before any worker starts; rollback on
a failed bind or listener timeout configuration error. The current socket
must be closed even when it has not yet been added to the rollback list;
already opened TCP/UDP endpoints are also closed. No workers start on a
partial startup failure. The same Server can be started after failure;
stop/close/join all workers on ordinary shutdown.

UDP is a datagram adapter over the existing MC 3E/4E decoder/dispatcher:
one exact 8192-byte-maximum frame per packet, no stream reassembly, silent
discard on malformed/oversized packet, reply to sender address. It does not implement retransmission, client sessions, UDP request
faults, authentication or rate limiting; the independently opt-in UDP
**response** drop/delay actions are documented in the next subsection. TCP-specific FaultPlans are rejected for
mixed/UDP configurations rather than being silently misapplied. Loopback
guard stays in effect; `--allow-nonlocal --idle-timeout` is required for
any nonlocal bind, with no UDP timeout semantics implied. A separate
process provides an independent PLC instance. Physical PLC behavior remains
unverified; this is a simulator transport policy only.

UDP observability semantics are specified in [BEHAVIOR.md](BEHAVIOR.md#udp-observability-opt-in).
Opt-in TCP session counters mirror that contract (no CLI flag, `None` when
disabled, cumulative across restarts) and are updated under the session-table
lock; see [BEHAVIOR.md](BEHAVIOR.md#tcp-session-counters-opt-in).

### UDP datagram response faults (PR #52)

Separate `UdpFaultPlan` (`virtual_plc/udp_faults.py`) reserves post-dispatch UDP `drop`/`delay` atomically under its own plan lock and waits outside the shared PLC request lock; full schema and matching semantics are owned by [FAULTS.md](FAULTS.md#udp-datagram-response-faults-opt-in). Duplicate, corruption, reorder, scheduler and rate limiting are held for separate #13 slices.

## 1. Verified client facts (pinned pymcprotocol 0.3.0)

- Only `plctype == iQ-R` changes wire format. Q, L, QnA, iQ-L share one **wire class**.
- Client sends one `send`, reads one `recv(4096)`; never validates response
  subheader/serial/length; reads end code at fixed offset (3E bin 9, 3E ascii 18, 4E bin
  13, 4E ascii 26).
- Only end code 0xC059 raises a distinct error; any other non-zero is generic
  (mcprotocolerror.py).
- ASCII device numbers are sent as **decimal text** even for hex-numbered devices
  X,Y,B,W,SB,SW,DX,DY,ZR.
- Truncated binary response decodes status 0 == success — client misbehaviour, label in
  tests.
- `remote_reset` sets a 1 s socket timeout; on any receive/status failure it sleeps 1 s
  and reconnects (connect restores the configured `soc_timeout`); on success the
  existing socket keeps the 1 s timeout.
- Random cmds: <=255 words and <=255 dwords per request; word values signed 16-bit,
  dword signed 32-bit, checked client-side.
- Echo: 1-960 alphanumeric chars. CPU type: 16 raw name bytes + code; the client removes
  spaces but retains NULs in both encodings. LSTC unreachable from the client.
- Falsy options (`network=0`, `pc=0`, `timer_sec=0`) ignored by `setaccessopt`.
- Random binary layouts checked against the installed pinned 0.3.0 client at M2;
  parser names STS/STC/STN select constants SS/SC/SN respectively.
- ASCII/4E layouts checked against the same installed client at M3/M4: ASCII
  batch bits are single characters, words are four hex characters, dwords are
  one eight-digit hex value. 4E serials are uint16; reserved fields are zero.
- M6 source inspection: iQ-R binary descriptors are 4-byte addresses + 2-byte
  codes; ASCII descriptors are 4-character codes + 8 decimal digits. Data
  subcommands are 0002/0003; random bit values are uint16; passwords are 6–32
  ASCII characters. LSTC has a constant but no client lookup. LTN's client
  get_devicetype result is inconsistent (bit); see [native storage
policy](BEHAVIOR.md#native-dword-stride-policy-unverified).
- M7 real-client fault tests observe binary truncation as false success, ASCII
  truncation as a decode error, and corrupt response subheaders being ignored.
  Silent/RST reset responses exercise the actual timeout/sleep/reconnect path;
  these are client-compat observations, labelled client-misbehaviour where applicable.

## 2. Decisions

| ID | Decision |
|---|---|
| D1 | Historical M1–M29 scaffold assets were retired before git history; keep concrete test scenarios (`tests/`) and the wheel-hash pin (`tests/oracle_pin.txt`); omit gates/evidence/progress scripts. |
| D2 | Five named profiles (Q, L, QnA, iQ-L, iQ-R) mapped to two wire classes (`Q-class`, `iQ-R`). Same wire class != same capabilities; ranges, CPU names and batch point caps (QnA vs Q/L/iQ-L/iQ-R) are per profile. Addressed requests using the opposite wire class's subcommands return an error in either direction. Q-class names and non-addressed packets are indistinguishable on the wire; see BEHAVIOR. |
| D3 | Layout `virtual_plc/{server,codec,commands,memory,profiles,faults,__main__}.py`; tables in Python. stdlib + pytest only. One lock per request; validate whole request before any mutation; each response fully written via `sendall`/checked send loop; `TCP_NODELAY`; tests bind port 0. M7 explicitly injects response faults after dispatch. |
| D4 | Tests generated from tables over **applicable** combinations only (explicit exclusions with reasons). Oracles: (i) real pymcprotocol 0.3.0 = *client-compat*; (ii) hand-authored expected bytes in test code, independent of `codec.py`/tables/client = *manual-derived* (never "manual-correct", never "capture"). Oracle pin = PyPI 0.3.0 wheel hash (verify checkout matches). |
| D5 | Numbering policy is explicit (`compat` default = decimal text as client sends; `manual` parses declared device bases including hex X/Y/W/B; `fx5-octal` parses **X/Y octal only**, other devices retain declared bases). Never autodetect. FX5 JY997D56001-K p.67 confirms the OCT/HEX distinction; opt-in 1E framing is in `virtual_plc/one_e.py`, while full FX5 hardware parity remains out of scope. ASCII dword order is separate: `swapped` (default) or `client` (high first); physical ordering remains unverified. |
| D6 | Milestones below. 4096 is a *client receive limit*, documented separately from server limits; large valid responses tested with a raw-socket client. |
| D7a | Timers/counters (TS/TC/TN, CS/CC/CN, SS/SC/SN): independent storage, no timer execution. Own milestone step. |
| D7b | SM/SD writable by default; no read-only ranges are currently enforced. |
| D7c | Dword on word devices = two consecutive words, low word at lower address. M6 native LTN/LSTN/LCN/LZ store one uint32 per native point; word counts stream low/high halves, random dwords occupy one native point, odd word writes preserve the other half except odd-count batch writes to LCN, which return C051 (SH-081257 3.5 p.453: long-counter write points must be two-word units). Native stride is an unverified simulator policy, not proven by client encoding. |
| D7d | M5 agreed: server-wide lock gates run/stop/pause/latchclear/reset only; survives disconnect. Wrong password changes nothing. Reset succeeds only in STOP, normally replies on the same open connection and clears no memory; M7 faults may alter delivery. See BEHAVIOR and FAULTS. |
| D7e | Error-table rows carry `source: manual|client|design|memory` + `status: verified|unverified`. C200/C201 use memory provenance; their meanings may be swapped and remain unverified. Tests never hard-assert `unverified` rows without the marker; reported separately. |

## 3. Memory model

- Sparse unsigned storage per device family. Bit devices: 1 bit/point. Word view of a
  bit device: for head address h, response word j bit i == point h+16j+i (LSB first;
  `M16` word-read yields M16..M31); head must be a multiple of 16 (unverified vs real
  PLC -> reject otherwise, flagged). Bit access to word devices (D etc.): rejected with
  error.
- Overlapping/duplicate random-write entries applied in request order.
- Validation (range, count, legality) completes before any write (atomic).

## 4. Codec (both wire classes)

- 3E binary request: `50 00 | net | pc | io(2 LE) | stn | len(2 LE)=2+cmd+sub+data |
  timer(2) | cmd(2) | sub(2) | data`.
- Response: `D0 00 | net pc io stn | len(2) | end(2) | data` (end code first inside len).
- Q-class batch read/write (cmd 0401/1401), sub 0000 (word) / 0001 (bit): `addr(3 LE)
  devcode(1) points(2)`; words LE; bits 2/byte high nibble first, odd count padded low
  nibble 0. Per-profile batch point caps (`BATCH_MAX` in `virtual_plc/profiles.py`), `--max-points` interaction, and `0xC051`/`0xC052` rejection rules are documented in [BEHAVIOR.md](BEHAVIOR.md#public-api).
- Server: length-framed parser (total = 9 + len), fragmentation, merged requests, clean
  EOF; malformed frame -> close.
- Q-class random read (0403/0000): uint8 word count + uint8 dword count, followed by
  word addresses then dword addresses (each addr(3 LE) + devcode(1)). Response: word
  values (2 LE each), then dword values (4 LE each), with no counts.
- Q-class random write (1402/0000): the same two counts, followed by interleaved word
  address/value entries (4+2 bytes), then dword address/value entries (4+4 bytes).
- Q-class random bit write (1402/0001): uint8 count, then address(4) + value(1) entries;
  values must be 0 or 1, not packed nibbles.
- Random-access point limits per wire class (`WIRE_CLASSES` in `virtual_plc/profiles.py`), check order, and `0xC053`/`0xC054` error codes are owned by `virtual_plc/commands.py` (`random_access`) and documented in [BEHAVIOR.md](BEHAVIOR.md#public-api).
- The same codec is parameterized by frame (3E/4E) and wire (binary/ASCII).
  Request headers auto-detect the transport on every request, including mixed
  requests on a single connection. This does not autodetect address numbering.
- ASCII uses `5000`/`5400` requests, `D000`/`D400` responses, character lengths,
  uppercase hexadecimal output, and case-insensitive hex input. Q descriptors
  are two code characters followed by six **decimal** address digits (`compat`).
  Overwidth addresses and invalid payloads return a nonzero error without mutation;
  opt-in `manual` and `fx5-octal` numbering policies are selected via `--ascii-numbering` (see D5 and [BEHAVIOR.md](BEHAVIOR.md#fixed-width-text-padding)).
- 4E inserts serial(2 binary bytes / 4 hex characters) and reserved zeros of
  the same width after the subheader. Responses echo serials. End-code offsets
  are 9/18 for 3E binary/ASCII and 13/26 for 4E binary/ASCII.
  See [transport behavior](BEHAVIOR.md), including configurable ASCII dword ordering
(`swapped` default, `client` optional; physical PLC order unverified).
- M6 parameterizes descriptor sizes, subcommands, random bit-value width and
  password bounds through profile wire tables. Framing remains shared. iQ-R
  adds LTS/LTC/LTN, LSTS/LSTC/LSTN, LCS/LCC/LCN, LZ and RD; LSTC is covered by
  raw requests because the pinned client cannot name it. Z is not client-supported.
  See [profile behavior](BEHAVIOR.md) for synthetic identities/ranges and native stride
policy.

## 5. Milestones

| M | Scope | Exit criteria | Status |
|---|---|---|---|
| M0 | Scaffold, migration, pinned oracle, test generator skeleton, `pytest` green | `pytest` runs; old assets archived | Complete |
| M1 | Transport + error table + 3E binary Q: batch word/bit R/W for D,M,X,Y,B,W,R,ZR,SM,SD; echo (0619) and cputype (0101); response-transform hook seam; basic disconnect/timeout tests | Real client round-trips every M1 cell; manual-derived vectors pass | Complete |
| M2 | Random read/write (+bit random write, mixed word/dword) | boundary counts (0, 1, manual maxima, max+1 rejection) via client and raw socket; malformed 256-entry attempts via raw socket (client rejects 256 separately) | Complete |
| M2b | Timers/counters, SB, SW, DX, DY, L, F, V | per-device base/range table complete | Complete with synthetic ranges; vendor limits unverified |
| M3 | 3E ASCII (incl. ascii overflow policy, uppercase out/lowercase in) | cross product generated | Complete (compat numbering) |
| M4 | 4E (serial echo, reserved zeros) | All implemented commands across all four transports | Complete |
| M5 | Control: run/stop/pause/latchclear/reset, lock/unlock; CPU state machine | Agreed semantics, all four transports; vendor behavior unverified | Complete |
| M6 | All named profiles; iQ-R 4+2 addressing, LT*/LST*/LC*/LZ/RD, pw 6-32, 2-byte random bit | Profile-driven handlers and generated transport cells; raw LSTC; native stride documented | Complete; vendor ranges/stride unverified |
| M7 | Declarative delay/drop/truncate/end-code/close/RST/hold/corruption/partial-send faults on the response hook; JSON CLI | Counted thread-safe matching, real reset reconnect, client-misbehaviour labels | Complete |
Extension point = command registry dict (no extension milestone). See [fault schema and policies](FAULTS.md) for M7 `FaultPlan` and `UdpFaultPlan` reservation and post-dispatch delivery.

## 6. Transport and command regression scenarios

T1 batch word write->read roundtrip D0..D(n); T2 bit roundtrip incl. odd count; T3 word
read over M (16-pt packing); T4 hex-base devices X/Y/B/W/ZR addressing; T5 range
overflow -> end code; T6 points=0 / over-limit -> end code; T7 unsupported command ->
0xC059; T8 iQ-R subcommand on Q profile -> error; T9 fragmented request (1 byte at a
time); T10 two requests in one segment; T11 EOF mid-frame; T12 atomic failure
(partial-range write mutates nothing); T13 concurrent clients, no torn writes; T14 echo
1/960 chars; T15 cputype name+code; T16 manual batch cap (960 words) accepted and >cap
rejected; T18 word-read of `M16` observes M16..M31 (not M256..); T17 golden
request bytes: client encoder vs hand-authored vectors.

## 7. End-code table (codes manual-listed; mapping `unverified`)

0x0000 OK; 0x0055 write denied while CPU RUN (QJ71E71/iQ-R SLMP/MC error lists, not
SH-081257; see ETHERNET_MODEL_SETTINGS.md); 0xC051 word points out of range; 0xC052 bit points out of range; 0xC053
random bit points out of range; 0xC054 random word/dword points out of range; 0xC056
address out of range; 0xC059 unsupported command; 0xC05C request data error; 0xC057 data
length mismatch. C051..C054, C056, C057, C059 and C05C are listed in SH-081257 3.5
(p.453), so `ERROR_CODES` marks them (and 0055) `source: manual`; which request path maps to
which code remains `status: unverified`. Opposite wire-class subcommands return C059; invalid
device/access/alignment returns C05C. An odd-word batch write to LCN returns C051 (p.453). Some regression scenarios assert only nonzero until
vendor verification.

Response bodies: cputype = 16-byte name filled with `text_pad` (default 0x00) + 2-byte
code; echo = 2-byte length + echoed data.
CPU type requests require an empty payload (`C057` otherwise) on 3E/4E binary
and ASCII. Data commands check counts and exact wire lengths before ASCII
normalization, so zero/over-limit counts precede length and device errors on
both wires; see the check order and malformed-field exceptions in BEHAVIOR.md.

0xC200 LOCKED and 0xC201 WRONG_PASSWORD (`source: memory`,
`status: unverified`), and 0xC202 INVALID_STATE (`source: design`,
`status: unverified`). Bad M5 payload lengths use C057; invalid fields use C05C.
C200, C201 and C202 are not supported by manual SH-081257 3.5; C203/C204 are the documented remote-password codes; remap tracked in issue #5. Their meanings and classifications are unverified simulator policies.
See [control behavior](BEHAVIOR.md) for the state table and server-wide, control-only
lock gating (vendor comparison unverified). Initial/transition SD203 values are
STOP=0, RUN=1, PAUSE=2 (unverified). Default latch ranges cover L; clearing
never touches SM/SD, apart from the explicit SD203 state mirror on transitions.

## 8. Open items

Canonical simulator policies and unverified vendor behaviors live in `virtual-plc guide divergences` (`DIVERGENCES` in `virtual_plc/guide.py`). Remaining open design items: SM/SD per-range read-only enforcement, real-PLC unaligned bit-head word reads, bit-device dword views, keyword-only `Server` parameters for 1.0 (#78) and an optional stored-cell cap (#79); see [FX5 1E/3E frame distinction and limits](research/FX5_SLMP_FRAME_SCOPE_20261031.md) and [BEHAVIOR.md](BEHAVIOR.md#slmp-1e-transport-opt-in).


## 9. Server lifecycle and CLI

CLI options: build_parser is the SSOT; see `virtual-plc guide options`.

Use `virtual-plc guide options` (generated from argparse), `--help`, and the
[human CLI reference](../README.md#cli-reference), plus
[embedding/snapshot examples](../README.md#memory-seeding-snapshots-and-embedding).
Package exports are `Server`, `FaultPlan`, `UdpFaultPlan`, `Memory`, `OutOfRange`, `EthernetSettings` and `__version__`.
Context exit stops/joins workers. Seed direct memory before start and take
snapshots after stop; wire requests remain the synchronization boundary.
Invalid configuration fails before bind. Bind failures exit 1 without a
traceback; graceful signals stop workers and save an optional snapshot.
Verbose logging is opt-in and reports summaries and close reasons.

## 10. Fixed-width text

`text_pad` is an integer 0..255 or a single byte-valued character, normalized
to an integer at construction; default 0x00. CLI `--text-pad` accepts numeric
hex/decimal input. CPU model names are the only emitted padded text and use
the same fill byte in binary and ASCII on both frames. The pinned client
retains NULs and removes spaces: default Q returns
`"VirtualPLC-Q\x00\x00\x00\x00"`; 0x20 restores `"VirtualPLC-Q"`.
Non-UTF-8 fills can cause client decoding errors. This is an explicit simulator
policy; physical PLC fill is unverified.

Request ASCII device identifiers accept canonical `*` fill or the configured
byte in their unused suffix; ambiguous alternate names are rejected. Echo and
passwords have explicit lengths and no unused text area, so padding-valued
content is significant and is not stripped. Numeric and bit padding are
unchanged. See [text behavior](BEHAVIOR.md#fixed-width-text-padding).


## 11. Hardening and remaining verification

Monitoring timers are parsed/ignored. Routes alias one target. SD203 is a
one-way state mirror. The installed-client coverage guard explicitly maps
public Type3E/Type4E methods, device constants and lookup-only names to covering
test modules. Lookup names come from the client's name->code/type branches;
a mutation test proves that an added lookup-only name fails coverage.
requirements-dev.txt is the only exact oracle pin; tests/oracle_pin.txt records
only wheel version/hash/provenance metadata. The test extra declares compatibility.
Dependency bumps must add tests for new features; a stale wheel hash alone
does not block a bumped oracle. CI covers Linux/Windows on Python 3.10–3.14
and installs built wheels in clean environments. Python 3.10 stays supported
after its October 2026 end of life until a user-approved drop (classifiers,
CI matrix and `requires-python` move together; test-enforced). Third-party
actions are pinned to commit SHAs (Dependabot updates them). Trusted publishing requires
the repository PyPI publisher and GitHub environment pypi to be configured.

Open verification items follow `virtual-plc guide divergences`. Windows SIGBREAK needs a console; TerminateProcess cannot flush snapshots.
Artifact builds need setuptools>=77; build/twine are release tools, not runtime
dependencies. Workflow execution/publishing require configured hosted runners.

## 12. Compact usage guide

`main` dispatches a leading `guide` before parsing server arguments; existing
server invocations keep their syntax. The console script and module use the
same entry point. Guide rendering never creates or starts a server.

`guide.py` owns English prose. `build_parser()` supplies option names, defaults,
choices and help. Profile/device tables and command dispatch registries supply
the matrix; codec frame/wire constants describe its transport product. Fault
action fields are shared with validation. JSON exposes structured options and
profiles, or version/topic/text for other topics. No runtime dependencies added.

Tests enforce 45 overview lines, 40 lines per topic, parser/table coverage,
valid JSON examples, no stale flags and marked README recipe equality. README
remains the human entry point without duplicating generated reference tables.
Root llms.txt is a usage index; AGENTS.md describes repository development.
Both ship in the sdist through MANIFEST.in.

The runnable embed fixture seeds memory before start and closes clients in
finally; its test body runs in guide tests. Q uses port 5000 and the iQ-R
recipe/client pair uses 5001. Live timer tests check socket timeouts before and
after setaccessopt, ignored zero and successful subsequent requests on all
transports. Latch ranges are cleared by latchclear and preserved by
remote_run(clear_mode=1); SM/SD remain exempt from clearing.

Configuration errors are one line ending with a relevant guide topic. Argument
errors use the option name; file loading uses the faults/memory stage, and
constructor validation uses options (or memory for latch ranges). Diagnostics
collapse embedded newlines. Unknown guide topics list available topics, exit 2.

## 13. Unverified / deferred

Canonical simulator divergences live in `virtual-plc guide divergences` (`DIVERGENCES` in `virtual_plc/guide.py`), and manual cross-check provenance is in [docs/manual/PROVENANCE.md](manual/PROVENANCE.md) (remote-password `C200..C202` vs `C203/C204` remap in #5). Additional pinned/manual items awaiting physical PLC verification:

- **0xC057 vs 0xC05C on length mismatch**: which end code a real PLC returns is unverified. Malformed echo lengths return C057 on both wires (2026-11-10).
- **C050 / C05A / C05B vs C05C (issue #2)**: SH-081257 3.5 (p.453) lists C050 for non-convertible ASCII data and C05A/C05B (identical text) for unreadable/unwritable devices; 3E/4E keeps C05C for non-hex ASCII fields and unknown device codes until a physical oracle fixes check order and the C05A/C05B choice.
- **1E error-code width (issue #2)**: JY997D56001-K pp.43-45 examples show a 1-byte error code after `5BH`; pp.137-138 list only 16-bit codes with no 1-byte mapping. The simulator keeps the 16-bit code.
- **Error information and bad_end_code frame shape**: abnormal responses (and `bad_end_code` with code != 0) append error information per SH-080008 5.2/5.3 (route, command, subcommand; response data dropped; length field = end code + error info; manual-derived). Other-station routing and real-PLC no-error-info cases remain unverified.
- **Echo (0x0619) payload and Remote STOP (0x1002) mode**: echo accepts 0-9, A-F, a-f (`0xC05C` otherwise, case unverified); STOP accepts mode 1 only (`0xC05C` otherwise); both pinned by `tests/test_pinned_behavior.py`.

### Restart semantics

- Calling `stop()` then `start()` works and accepts new client connections cleanly (`_stopping` event is cleared on `start()`).
- Port 0 rebinds a new ephemeral port on each `start()`.
- Calling `start()` twice without an intermediate `stop()` is a safe no-op that preserves the existing listener and does not leak sockets.

### 2026-11-01 RnCPU built-in remote opening-method risk, CPU-specific

An isolated `inspect_reference_rncpu_remote_opening` helper reads
`_REFERENCE_HARDWARE["rncpu_builtin"]["remote_opening_reference"]`
without mutating runtime models/listeners. Official CPU manual
SH-082488ENG-E p.3 says `Open by Program` can close a remote STOP
connection so remote RUN cannot recover on that line. Its Appendix 8
pp.684-685 identifies the CPU-built-in `Opening Method` parameter A031H
and separately `Timer Settings for Data Communication` A038H.
The preflight rejects invalid values, leaves omitted factory
configuration UNKNOWN, never certifies recovery for a recommended
choice, and has no physical-hardware side effects. The related
[RnCPU documentation](research/RNCPU_REMOTE_OPENING_SAFETY_20261101.md)
and issue #14 define the pending CPU/firmware/timer oracle gates.
Do not share RJ71EN71 network-module defaults without direct evidence.

### 2026-11-01 R04CPU built-in A038H reference validator

`inspect_reference_rncpu_data_timers("R04CPU", overrides)` uses a
**separate, CPU-built-in-only** metadata table inside
`_REFERENCE_HARDWARE["rncpu_builtin"]["data_timer_reference"]`.
SH-081257ENG-AD pp.329–330 R04CPU Application Settings explicitly
points to shared timer table pp.396–397, and CPU manual
SH-082488ENG-E p.685 identifies parameter A038H.
The nine values are R04CPU GX Works3 **documented GUI defaults**,
not a runtime claim or a copied RJ71EN71 module preset.
`Change/Set Timer Value` defaults to No; overrides require Yes.
Validation is pure/strict: numeric unit conversion, bounds, step,
equality and five-field `>=` chain, copies, model rejection, and
no socket operations. Other RnCPU CPU/firmware variants remain UNKNOWN.
See [R04CPU timer reference](research/RNCPU_R04CPU_A038H_DATA_TIMER_REFERENCE_20261101.md).

### 2026-11-01 R04CPU CPU built-in external-device GX Works3 slot/port checker

An isolated, pure `inspect_reference_rncpu_external_device` reads
`_REFERENCE_HARDWARE["rncpu_builtin"]["external_device_configuration_reference"]`
and never starts a listener. SH-081257ENG-AD pp.324–326 documents
configuration slot 1..16 vs RJ71EN71 network module 1..64 and
PLC own-port ranges; Appendix 10 p.554 defines system-reserved ports
that can lie inside the broader numeric bounds. *Reservation precedes
range*. The API treats missing slot as UNSPECIFIED, blank PLC port as
a GUI default, refuses invalid types and other CPU families, and
never equates setting slots with simultaneous client sockets.
See [scope/edge cases](research/RNCPU_R04CPU_EXTERNAL_DEVICE_PORTS_20261101.md).
No changes to max_clients, runtime ports, protocol or PyPI.

### 2026-11-01 R04CPU built-in external-device multi-entry static lint

`inspect_reference_rncpu_external_device_batch(entries=None,
model="R04CPU", report_slot_gaps=True)` is a small, pure offline
function, composed of the existing independently sourced **per-row**
`inspect_reference_rncpu_external_device`. It adds stable,
separately documented developer-side diagnostics: invalid own-port
(per-row vendor classification), duplicate configured slot (static
error), potentially repeated numeric port (review only without
transport type) and optional gap advisory (no vendor rejection
claim). Input None means not supplied; [] means explicitly empty;
no active sockets, hardware capabilities or vendor end codes are
inferred. The RnCPU SSOT now also records a **newer manufacturer
AG (2026-10)** revision with actual AD-to-AG diff NOT VERIFIED,
instead of assuming current firmware parity. See
[batch research](research/RNCPU_R04CPU_BATCH_LINT_20261101.md).
