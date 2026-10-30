# VirtualPLC — Design

Status: implemented M0–M7. Public behavior is documented in [BEHAVIOR](BEHAVIOR.md),
response faults in [FAULTS](FAULTS.md), and installation/safety in [README](../README.md).
Purpose: a local Mitsubishi MC-protocol PLC simulator compatible with the wire-visible
features of
[pymcprotocol](https://github.com/greatgc-flow/pymcprotocol) 0.3.0 (the client). Default
profile: **Q series**.
Not for industrial use. Binds 127.0.0.1 by default.

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
| D1 | Old assets remain under `archive/m1-m29`; Keep concrete test scenarios and the wheel-hash pin; omit gates/evidence/progress scripts. |
| D2 | Five named profiles (Q, L, QnA, iQ-L, iQ-R) mapped to two wire classes (`Q-class`, `iQ-R`). Same wire class != same capabilities; ranges, CPU names and batch point caps (QnA vs Q/L/iQ-L/iQ-R) are per profile. Addressed requests using the opposite wire class's subcommands return an error in either direction. Q-class names and non-addressed packets are indistinguishable on the wire; see BEHAVIOR. |
| D3 | Layout `virtual_plc/{server,codec,commands,memory,profiles,faults,__main__}.py`; tables in Python. stdlib + pytest only. One lock per request; validate whole request before any mutation; each response fully written via `sendall`/checked send loop; `TCP_NODELAY`; tests bind port 0. M7 explicitly injects response faults after dispatch. |
| D4 | Tests generated from tables over **applicable** combinations only (explicit exclusions with reasons). Oracles: (i) real pymcprotocol 0.3.0 = *client-compat*; (ii) hand-authored expected bytes in test code, independent of `codec.py`/tables/client = *manual-derived* (never "manual-correct", never "capture"). Oracle pin = PyPI 0.3.0 wheel hash (verify checkout matches). |
| D5 | Numbering policy is explicit (`compat` default = decimal text as client sends; opt-in `manual` policy parses hex digits for base-16 devices via `ascii_numbering="manual"` / `--ascii-numbering manual`). Never autodetect. ASCII dword order is a separate endpoint option: `swapped` (default, low word first) or `client` (high word first); physical PLC ordering remains unverified. All manual claims from memory are marked `unverified`. |
| D6 | Milestones below. 4096 is a *client receive limit*, documented separately from server limits; large valid responses tested with a raw-socket client. |
| D7a | Timers/counters (TS/TC/TN, CS/CC/CN, SS/SC/SN): independent storage, no timer execution. Own milestone step. |
| D7b | SM/SD writable by default; no read-only ranges are currently enforced. |
| D7c | Dword on word devices = two consecutive words, low word at lower address. M6 native LTN/LSTN/LCN/LZ store one uint32 per native point; word counts stream low/high halves, random dwords occupy one native point, odd word writes preserve the other half. Native stride is an unverified simulator policy, not proven by client encoding. |
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
  nibble 0. Batch point caps from SH-080008 (p.87/91/96, Ethernet E71 column) are stored
  per profile in `profiles.py` keyed by `(profile, wire, unit)`: `Q`, `L`, `iQ-L`, `iQ-R`
  allow word `960`, bit binary `7168`, bit ASCII `3584`; `QnA` allows word `480`, bit
  binary `3584`, bit ASCII `1792`. Zero or over-limit points return
  `POINTS_OUT_OF_RANGE` (`0xC051`) for word units or `BIT_POINTS_OUT_OF_RANGE` (`0xC052`)
  for bit units (SH-081257 3.5; manual-derived, code assignment unverified, real-PLC
  verification still open in #2). `--max-points` defaults to `None` and acts as an
  optional additional cap (`min(manual_cap, max_points)` when set); direct `Memory` calls
  are uncapped.
- Server: length-framed parser (total = 9 + len), fragmentation, merged requests, clean
  EOF; malformed frame -> close.
- Q-class random read (0403/0000): uint8 word count + uint8 dword count, followed by
  word addresses then dword addresses (each addr(3 LE) + devcode(1)). Response: word
  values (2 LE each), then dword values (4 LE each), with no counts.
- Q-class random write (1402/0000): the same two counts, followed by interleaved word
  address/value entries (4+2 bytes), then dword address/value entries (4+4 bytes).
- Q-class random bit write (1402/0001): uint8 count, then address(4) + value(1) entries;
  values must be 0 or 1, not packed nibbles.
- Zero and over-limit random counts are rejected with RANDOM_POINTS_OUT_OF_RANGE
  (0xC054) for words/dwords or RANDOM_BIT_POINTS_OUT_OF_RANGE (0xC053) for bits per
  manuals SH-080008 (p.98/105/108) and SH-081257 3.5 (manual-derived; C053/C054
  assignment unverified, not verified PLC behavior). Keyed on the request wire class
  (`Wire` in `profiles.py`: Q-class subcommands 0000/0001 vs iQ-R 0002/0003), limits are:
  random read (0x0403) `words + dwords <= 192` (Q-class) / `96` (iQ-R); random word/dword
  write (0x1402) `words*12 + dwords*14 <= 1920` (Q-class) / `960` (iQ-R); random bit write
  (0x1402 bit subcommand) `points <= 188` (Q-class) / `94` (iQ-R), independent of
  `--max-points`. Check order: zero total, then over-limit, then payload length/format
  checks. A single zero count with the other nonzero is valid. Count 256 has no wire
  representation; raw tests send wrapped/widened counts with 256 entries and require
  rejection. See [random access behavior](BEHAVIOR.md).
- The same codec is parameterized by frame (3E/4E) and wire (binary/ASCII).
  Request headers auto-detect the transport on every request, including mixed
  requests on a single connection. This does not autodetect address numbering.
- ASCII uses `5000`/`5400` requests, `D000`/`D400` responses, character lengths,
  uppercase hexadecimal output, and case-insensitive hex input. Q descriptors
  are two code characters followed by six **decimal** address digits (`compat`).
  Overwidth addresses and invalid payloads return a nonzero error without mutation;
  the manual hex-address policy remains deferred.
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
Extension point = command registry dict (no extension milestone).

M7's optional FaultPlan reserves the first eligible declared step under the
request lock, after dispatch. Encoding and the existing response hook run next;
socket faults run outside the lock. None retains normal response delivery.
Steps match command, per-connection request ordinal and/or accepted connection
ID, with once/N uses. See [fault schema and policies](FAULTS.md); waits cancel on stop,
faults do not roll back committed writes.

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

## 7. End-code table (all `unverified` until manual cross-check)

0x0000 OK; 0xC051 word points out of range; 0xC052 bit points out of range; 0xC053
random bit points out of range; 0xC054 random word/dword points out of range; 0xC056
address out of range; 0xC059 unsupported command; 0xC05C request data error; 0xC057 data
length mismatch. Opposite wire-class subcommands return C059; invalid
device/access/alignment returns C05C. Some regression scenarios assert only nonzero until
vendor verification.

Response bodies: cputype = 16-byte name filled with `text_pad` (default 0x00) + 2-byte
code; echo = 2-byte length + echoed data.

0xC200 LOCKED and 0xC201 WRONG_PASSWORD (`source: memory`,
`status: unverified`), and 0xC202 INVALID_STATE (`source: design`,
`status: unverified`). Bad M5 payload lengths use C057; invalid fields use C05C.
C200, C201 and C202 are not supported by manual SH-081257 3.5; C203/C204 are the documented remote-password codes; remap tracked in issue #5. Their meanings and classifications are unverified simulator policies.
See [control behavior](BEHAVIOR.md) for the state table and server-wide, control-only
lock gating (vendor comparison unverified). Initial/transition SD203 values are
STOP=0, RUN=1, PAUSE=2 (unverified). Default latch ranges cover L; clearing
never touches SM/SD, apart from the explicit SD203 state mirror on transitions.

## 8. Open items

Vendor verification of CPU-name text fill (configurable, default NUL); authoritative
per-series limits/ranges; vendor verification of the selected native dword stride; SM/SD
per-range RO; vendor verification of M5 lock/reset/state-code policies; real-PLC
unaligned bit-head word reads; bit-device
dword views; vendor verification of ASCII dword word order (configurable: default
`swapped`, optional `client`; low-word-first PLC behavior remains suspected/unverified).
ASCII overwidth requests are rejected; manual numbering is implemented as an opt-in policy (`ascii_numbering="manual"`). Client 0.3.0
is pinned and checked by the oracle test.


## 9. Server lifecycle and CLI

Use `virtual-plc guide options` (generated from argparse), `--help`, and the
[human CLI reference](../README.md#cli-reference), plus
[embedding/snapshot examples](../README.md#memory-seeding-snapshots-and-embedding).
Package exports are Server, Memory, FaultPlan and the installed version.
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
does not block a bumped oracle. CI covers Linux/Windows on Python 3.10–3.13
and installs built wheels in clean environments. Trusted publishing requires
the repository PyPI publisher and GitHub environment pypi to be configured.

Open verification remains: vendor capacities, native stride, CPU-name fill,
ASCII dword order, error meanings and physical lock/reset/state behavior.
Windows SIGBREAK needs a console; TerminateProcess cannot flush snapshots.
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

The following simulator policies await physical PLC verification or manual cross-check:

- **ASCII hex addressing for X/Y/B/W**: default behavior (`compat`) accepts decimal digits only; `manual` opt-in policy accepts hex digits for base-16 devices; real PLC numbering is unverified.
- **0xC057 vs 0xC05C on length mismatch**: which end code a real PLC returns is unverified.
- **Random-access point limits (zero and upper bounds)**: total count 0 and over-limit counts rejected with C053 (random bit points) or C054 (random word/dword points) per SH-080008 (p.98/105/108) and SH-081257 3.5 (applied; manual-derived, C053/C054 assignment unverified, not verified PLC behavior). Limits keyed on request wire class (`Wire` in `profiles.py`, independent of `max_points`): read 0x0403 `words + dwords <= 192` (Q-class) / `96` (iQ-R); word/dword write 0x1402 `words*12 + dwords*14 <= 1920` (Q-class) / `960` (iQ-R); bit write 0x1402 `points <= 188` (Q-class) / `94` (iQ-R).
- **Batch point limits (zero and upper bounds)**: per-profile `(profile, wire, unit)` caps in `profiles.py` from SH-080008 (p.87/91/96, Ethernet E71 column): `Q`, `L`, `iQ-L`, `iQ-R` allow word `960`, bit binary `7168`, bit ASCII `3584`; `QnA` allows word `480`, bit binary `3584`, bit ASCII `1792`. Zero or over-limit points rejected with `C051` (word units) or `C052` (bit units) per SH-081257 3.5 (applied; manual-derived, code assignment unverified, real-PLC verification still open in #2). `--max-points` defaults to `None` (optional additional cap `min(manual_cap, max_points)`); direct `Memory` calls are not capped.
- **Error information and bad_end_code frame shape**: abnormal responses (and `bad_end_code` with code != 0) append error information per SH-080008 5.2/5.3 (route, command, subcommand; response data dropped; length field = end code + error info; manual-derived). Other-station routing and real-PLC no-error-info cases remain unverified.
- **Echo (0x0619) payload**: 0-9, A-F, a-f only, otherwise `0xC05C`; pinned by tests/test_pinned_behavior.py; unverified (case).
- **Remote STOP (0x1002) mode**: only mode 1 accepted, otherwise `0xC05C`; pinned by tests/test_pinned_behavior.py.

Manual cross-check results (SH-080008, see `docs/manual/PROVENANCE.md`): STOP mode `0001H` verified; echo data is 0-9/A-F only (simulator accepts a-f, unverified (case)); X/Y/B/W numbers are hexadecimal; error information in abnormal responses per 5.2/5.3 applied (manual-derived; other-station routing and real-PLC no-error-info unverified); batch zero and upper point limits (SH-080008 p.87/91/96, Ethernet E71 column) mapped to C051 (word) and C052 (bit) per SH-081257 3.5 (manual-derived; code assignment unverified, real-PLC verification still open in #2); random-access zero and upper point limits (SH-080008 p.98/105/108) mapped to C053 (bits) and C054 (words/dwords) per SH-081257 3.5 (manual-derived; C053/C054 assignment unverified); C057 is the documented length mismatch code in SH-081257 3.5; C200/C201/C202 are not supported by manual SH-081257 3.5; C203/C204 are the documented remote-password codes; remap tracked in issue #5.

### Restart semantics

- Calling `stop()` then `start()` works and accepts new client connections cleanly (`_stopping` event is cleared on `start()`).
- Port 0 rebinds a new ephemeral port on each `start()`.
- Calling `start()` twice without an intermediate `stop()` is a safe no-op that preserves the existing listener and does not leak sockets.
