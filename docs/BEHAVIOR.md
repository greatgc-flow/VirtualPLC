# Behavior and public API

This reference describes simulator policy and compatibility with pymcprotocol
0.3.0. Vendor ranges, identities and error meanings remain unverified.
See [design](DESIGN.md), [fault injection](FAULTS.md), and [usage/safety](../README.md).

## SLMP 1E transport (opt-in)

`Server(slmp_1e=True)` or `virtual-plc --slmp-1e` selects a **separate
1E-only request/response parser** on all TCP/UDP listeners of the same
PLC process. Defaults and existing 3E/4E wire protocol are unaffected.
Only synthetic Q-class memory is currently implemented in this mode:
`profile="Q"`, no `ethernet_model` or 3E/4E `fault_plan`. Incompatible
settings raise `ValueError` before any port is bound.

Commands `00H` (bit read, max 256, encoded count 00H=256), `01H`
(word/group read, max 64 D words / 32 aligned groups of 16 bits),
`02H` (bit write, max 160), and `03H` (word/group write, max 64 D
words / 10 aligned bit groups), plus 04H random bit writes (1–80 points), 05H random word/aligned bit-group writes (1–10 items), TCP owner-scoped 13H RUN / 14H STOP and diagnostics `15H` / `16H` are supported in binary and ASCII.
**Unlike batch responses**, `15H` replies with only model code `F3H`
(binary) or `F3` (ASCII); `16H` echoes only the original byte count
and data (binary length byte; ASCII two-character hexadecimal length).
Neither uses the batch subheader/status. The type code is a manual-sourced,
synthetic module identity; no actual FX5 hardware identity is implied.
First-slice device validation is restricted to M (0..7679),
X/Y (0..255) and D (0..7999) synthetic points. Invalid PC numbers,
monitoring timers, reserved fields, framing and data widths do not
mutate memory. A 1E error reply uses end code 5BH plus a 16-bit
manufacturer-table-derived code; simulator error mapping and physical
PLC equivalence remain unverified. TCP fragmented and coalesced frames
are handled by **command-specific bounded lengths**, while UDP accepts
exactly one complete frame/datagram. No legacy 3E-style length/route
field is parsed. Unknown 1E commands fail closed without guessing their packet lengths.

Random 04/05 validate all device names, addresses, values, point counts,
storage ranges and alignment before one atomic commit. Duplicate destinations
are applied in request order (last value wins); invalid later records never
partially mutate memory.

Remote 14H STOP owns one unique TCP connection ID across all listener ports.
Another TCP connection cannot RUN or STOP until the same owner has sent 13H
RUN. On socket disconnect/idle timeout, ownership remains orphaned and CPU
stays STOP: no automatic transfer. Explicit local
`Server.reset_1e_remote_control()` clears ownership and leaves STOP,
incrementing reset_count. UDP 13/14 are rejected with simulator 5B/C05F
because session continuity cannot be authenticated. The simulated password
lock also prevents remote control. Mitsubishi documents same-origin RUN and
reset/power release, but exact connection identity, UDP ownership,
disconnect semantics and foreign-owner error codes are not verified hardware
facts. The deliberate fail-closed policy must not be called vendor parity. See [official-manual comparison and test vectors](research/FX5_SLMP_FRAME_SCOPE_20261031.md). All listeners share one
request lock and one Memory; separate PLCs require separate OS processes.

### 1E remote STOP diagnostics (embedded API)

`Server.get_1e_remote_control_status()` is a request-lock-protected,
side-effect-free snapshot, valid only with `slmp_1e=True`:

```python
with Server(slmp_1e=True) as plc:
    status = plc.get_1e_remote_control_status()
    # {"cpu_state": "RUN", "owned": False, "owner_connected": False,
    #  "orphaned": False, "owner_connection_id": None}
```

`owner_connected` changes when the owner worker detects EOF/timeout and
finishes; the peer socket may have closed slightly earlier. A disconnected
STOP still has `owned=True`, `orphaned=True` and remains STOP until local
reset. The reset intentionally does not RUN. The owner ID is an in-process
monotonic TCP-accept ID, not a security credential. No extra network
control plane or unauthenticated remote override is exposed. `Memory.write_atomic`
treats `[]` as a no-op and rejects `None` with `ValueError`.

## Public API

See the [canonical CLI reference](../README.md#cli-reference),
[embedding examples](../README.md#memory-seeding-snapshots-and-embedding), or `--help`.

- `.start()` binds/listens and starts workers before returning; `.address` is `(host,
  actual_port)`.
- `Server(host=...)` permits only numeric loopback hosts or `localhost` by default.
  `allow_nonlocal=True` explicitly permits an external listener **only** when
  `idle_timeout` is a finite positive value; the CLI equivalent is
  `--allow-nonlocal --idle-timeout N`. This is not network authentication.
- `max_clients=64` limits concurrent accepted clients; an excess connection is
  closed before creating a worker, without affecting existing clients.
  Positive integer overrides are supported by `--max-clients N`.
- Opt-in `ethernet_model="qj71e71"` (profile Q), `"lj71e71"`
  (profile L), or `"rj71en71"`
  (profile iQ-R) selects vendor-manual-derived Ethernet factory settings.
  `ethernet_overrides` accepts validated `timers` (integer ms or count),
  `communication_data_code` (`binary`/`ascii`) and
  `allow_write_during_run` (boolean). See [the model settings contract](ETHERNET_MODEL_SETTINGS.md).
  Model selection limits wire encoding to one configured code (wrong TCP code
  closes, wrong UDP code drops) and blocks MC writes 1401/1402 during RUN by
  default with end code `0055` (manual-derived, hardware unverified); STOP
  or explicit opt-in enables writes. With no model, legacy behavior is unchanged.
  `server.ethernet.report()` provides exact effective/default/source/fidelity
  data; all module timers are **reference-only** and do not modify OS TCP timers
  or simulator `idle_timeout`.
- `Server(listeners=[("tcp", 5000), ("udp", 5000)])` opens multiple sockets
  for one PLC state and per-request lock. When omitted, `port` remains the
  legacy single TCP endpoint. Explicit listeners require `port=0`, and
  unique protocol/port pairs except ephemeral port zero.
- `server.addresses` reports `(transport, host, actual_port)` entries; the
  legacy `server.address` reports the first endpoint. A separate process
  remains necessary for separate, independent PLC memory/state.
- UDP accepts one exact complete 3E/4E binary/ASCII MC frame per datagram,
  with an 8192-byte limit. Invalid, truncated, concatenated, empty and
  oversized datagrams receive no response. It shares CPU state, Memory and
  the request lock with all TCP listeners; no reliable delivery, retry or
  TCP-style sessions are simulated. A UDP listener cannot be combined with
  TCP-only `FaultPlan` actions. `max_clients` and `idle_timeout` govern TCP
  sessions only; the nonlocal bind guard still requires both explicit permission
  and an idle timeout option, even for UDP-only configurations.
- All requested sockets bind before any listener starts processing. Failure
  to bind one socket closes those already bound without serving requests.
- `.stop()` synchronously closes all endpoints and clients and joins workers;
  idempotent, including incomplete TCP frames.
- Accepted sockets use TCP_NODELAY; EOF, bad framing or `idle_timeout` closes only that
  client.
- `response_hook(response_bytes) -> bytes` transforms each complete encoded response
  before the fault plan.
- `faults.FaultPlan(steps)` / `.from_file(path)` supplies ordered, counted response
  faults; None is inert.
- Q/L/QnA/iQ-L/iQ-R have synthetic CPU identities; names occupy 16 bytes, filled with
  `text_pad` (default NUL).
- Echo response: length uint16 + text. ASCII encodes numeric fields as uppercase hex.
- `memory.Memory(profile='Q', limits=None)` accepts inclusive `{device: (min, max)}`
  point ranges.
- Profile devices expose `code`, `base`, `kind`, `minimum`, `maximum`; ranges remain
  synthetic.
- `.read_words(device, head, count)` / `.read_bits(...)` return unsigned lists;
  corresponding writes return None.
- Memory is sparse, initially zero and isolated by instance/family; no timer/counter
  execution.
- Native dword heads address 32-bit points; word counts stream low/high halves,
  preserving an untouched half.
- Bit-device word views pack 16 bits LSB first at aligned heads; bit access to word
  devices is invalid.
- `codec.decode_request(frame_bytes)` returns `.frame`, `.wire`, `.serial`, `.route`,
  `.timer`, `.command`, `.subcommand`, raw `.data`.
- `codec.encode_response(request, end_code=0, data=b'', *, ascii_dword_order="swapped")
  -> bytes` echoes route/serial.
- `codec.pack_words(values)` / `unpack_words(data)` use unsigned LE uint16.
- `codec.pack_bits(values)` / `unpack_bits(data, count)` use high nibble first, odd low
  nibble zero.
- Frames auto-detect 3E/4E, binary/ASCII per request; reserved fields must be zero; bad
  framing raises ValueError.
- `commands.ERROR_CODES[code]` has `name`, `source`, `status`; all current rows remain
  unverified.
- Each request validates before mutation under one lock. Batch read (`0x0401`) and batch
  write (`0x1401`) point limits come from SH-080008 (p.87/91/96, Ethernet E71 column)
  keyed on `(profile, wire, unit)` in `profiles.py`: `Q`, `L`, `iQ-L`, `iQ-R` allow word
  `960`, bit binary `7168`, bit ASCII `3584`; `QnA` allows word `480`, bit binary `3584`,
  bit ASCII `1792`. Zero or over-limit points return `C051` (`POINTS_OUT_OF_RANGE`) for
  word units or `C052` (`BIT_POINTS_OUT_OF_RANGE`) for bit units (SH-081257 3.5;
  manual-derived, code assignment unverified, real-PLC verification still open in #2).
  `max_points` defaults to `None` and acts as an optional additional batch cap
  (`min(manual_cap, max_points)` when set); direct `Memory` calls (`read_words`,
  `write_words`, `read_bits`, `write_bits`) are not capped.
- Random counts are uint8; total count zero or over-limit returns C053 (bits) or C054 (words/dwords) (manual-derived per SH-080008 p.98/105/108 and SH-081257 3.5; C053/C054 assignment unverified, not verified PLC behavior). Limits are keyed on the request wire class (`Wire` in `profiles.py`) and independent of `max_points`: read (0403) `words + dwords <= 192` (Q-class) / `96` (iQ-R); word/dword write (1402) `words*12 + dwords*14 <= 1920` (Q-class) / `960` (iQ-R); bit write (1402) `points <= 188` (Q-class) / `94` (iQ-R). A single zero count with the other nonzero is valid. Responses put words before dwords; dwords store low word first.
- Duplicate/overlapping random writes apply in wire order. SS/SC/SN use STS/STC/STN
  client names.
- `Profile.wire` selects widths/subcommands; ASCII compat addresses use 6 (Q-class) / 8
  (iQ-R) decimal digits.
- `.state` is RUN/STOP/PAUSE (default RUN); SD203 mirrors STOP=0, RUN=1, PAUSE=2
  (unverified).
- `.reset_count` starts at zero; successful reset requires STOP, replies on the same
  connection and keeps it open.
- Reset sets STOP and clears no memory; state mirroring still writes SD203. SD203 must
  be addressable.
- Profile latch ranges default to all L points; `latch_ranges={device: [(lo, hi), ...]}`
  replaces it; `{}` disables retention.
- Latchclear requires STOP and clears only latch ranges. Run clear modes: 0 none, 1
  non-latch, 2 all non-special.
- SM/SD are writable and never cleared. `.latch_ranges` contains a copied, validated
  table of inclusive point spans.
- `.locked` starts False and survives disconnect; password None disables lock/unlock
  with C059.
- Passwords are ASCII: Q-class exactly 4 characters, iQ-R 6–32; invalid configuration
  raises ValueError.
- `commands.LOCK_GATED` contains run/stop/pause/latchclear/reset; all data/echo/cputype
  commands stay available.

- `Memory.check(device, head, count, unit)` validates without mutation and returns the
  device spec.
- `Memory.clear(latch_ranges, mode)` clears stored points (`latch`, `non_latch`, `all`),
  preserving SM/SD.
- `Server.password` exposes the configured simulated lock password; `set_state(state)`
  updates state and SD203.
- Direct memory/state access is intended for test setup; callers must serialize it with
  live requests.
- An unexpected handler/hook exception is logged to stderr and closes only that
  connection; committed work is not rolled back.
- `idle_timeout=None` leaves idle sockets open indefinitely; a positive seconds value
  closes idle/incomplete clients.
- `ascii_dword_order` accepts only `swapped` (default) or `client`; invalid
  configuration raises ValueError.
- `text_pad` accepts an integer 0..255 or one character with code point 0..255;
  `.text_pad` stores the normalized integer.
  Booleans, byte strings, multi-character strings and out-of-range values raise
ValueError.

## Random access and common devices

### Wire layout and mutation

Layouts follow the installed oracle methods `randomread`, `randomwrite`
and `randomwrite_bitunits` in `pymcprotocol.type3e`.
Each Q binary device descriptor is a three-byte little-endian head and a
one-byte device code. Random word/dword counts are separate uint8 fields.

| Operation | Payload following command/subcommand | Response data |
|---|---|---|
| Random read | word count, dword count, word descriptors, dword descriptors | uint16 words, then uint32 dwords, all LE; no counts |
| Mixed random write | word count, dword count, word descriptor + uint16 value entries, then dword descriptor + uint32 value entries | Empty |
| Random bit write | count, descriptor + one-byte 0/1 entries | Empty |

Client values are signed; storage is unsigned. On word devices, a dword occupies two word
locations, with its low word at the lower address. The handler validates the
complete length, every device/range/access and every bit value before writing.
The existing server lock covers the whole request, including reads. Writes
then apply in wire order (word section first), so later duplicate or overlapping
entries overwrite earlier ones.

Random-access point limits (manual-derived per SH-080008 p.98/105/108; C053/C054
assignment unverified, not verified PLC behavior) are keyed on the request wire
class (`Wire` in `profiles.py`: Q-class subcommands 0000/0001 vs iQ-R 0002/0003)
and are independent of `--max-points` (which applies to batch only):
- Random read (`0x0403`): `words + dwords <= 192` (Q-class) / `96` (iQ-R).
- Random word/dword write (`0x1402` word subcommand): `words*12 + dwords*14 <= 1920` (Q-class) / `960` (iQ-R).
- Random bit write (`0x1402` bit subcommand): `points <= 188` (Q-class) / `94` (iQ-R).

Check order in `random_access`: zero total count (`0xC053` for bit, `0xC054` for
word/dword), then over-limit (`0xC053` for bit, `0xC054` for word/dword), then
payload length/format and device range checks. The client rejects 256 before
sending because a count field is only one byte. A valid raw count of 256 does
not exist. Tests send over-limit and 256-entry frames and require rejection with
no mutation.

### Q device table

Codes, bases and kinds match the installed client's `mcprotocolconst.py`.
Every row has an inclusive default range **0..0xFFFFFF**, a synthetic ceiling
from the three-byte address format. These are not authoritative PLC capacities.
`Memory(limits={name: (min, max)})` overrides ranges per family in device points;
word views of bit devices validate the entire 16/32-point span.

| Family | Code | Base | Kind |
|---|---|---|---|
| SM | 91 | 10 | bit |
| SD | A9 | 10 | word |
| X | 9C | 16 | bit |
| Y | 9D | 16 | bit |
| M | 90 | 10 | bit |
| B | A0 | 16 | bit |
| D | A8 | 10 | word |
| W | B4 | 16 | word |
| SB | A1 | 16 | bit |
| SW | B5 | 16 | word |
| DX | A2 | 16 | bit |
| DY | A3 | 16 | bit |
| R | AF | 10 | word |
| ZR | B0 | 16 | word |
| L | 92 | 10 | bit |
| F | 93 | 10 | bit |
| V | 94 | 10 | bit |
| TS | C1 | 10 | bit |
| TC | C0 | 10 | bit |
| TN | C2 | 10 | word |
| SS | C7 | 10 | bit |
| SC | C6 | 10 | bit |
| SN | C8 | 10 | word |
| CS | C4 | 10 | bit |
| CC | C3 | 10 | bit |
| CN | C5 | 10 | word |

Codes above are hexadecimal. The client's parser spells SS/SC/SN as
STS/STC/STN; storage and the test table use SS/SC/SN. Tests translate parser
names explicitly. Each timer contact, coil and current-value family has its
own sparse storage. Writes do not execute timers/counters or update peers.


## Framing and ASCII

The codec uses one `Layout(frame, wire)` for header sizes and numeric fields.
`Reader` checks exact widths and character sets. Framing is detected on every
request, so sequential or merged requests may use different transports on the
same connection. ASCII payloads normalize to the binary representation consumed
by the existing handlers; responses convert the handlers' binary data back to
the request encoding. Memory and command execution remain shared. The existing
response hook receives a complete frame after transport encoding.

### Checked client facts

The source inspected is the installed pinned pymcprotocol 0.3.0 distribution:

- `type3e.py`: `_make_senddata`, `_make_devicedata`, numeric encode/decode,
  batch/random methods, `echo_test`, `read_cputype`, and response offsets.
- `type4e.py`: `_make_senddata`, serial setter and response offsets.
- `mcprotocolconst.py`: Q ASCII descriptor names and padding, including the
  STS/STC/STN parser names which produce SS/SC/SN wire codes.

| Transport | Request / response prefix | Header bytes | End-code offset |
|---|---|---|---|
| 3E binary | 50 00 / D0 00 | 9 | 9 |
| 3E ASCII | 5000 / D000 | 18 | 18 |
| 4E binary | 54 00 / D4 00 | 13 | 13 |
| 4E ASCII | 5400 / D400 | 26 | 26 |

Offsets are byte offsets in the response, before the end code. Binary fields
are little-endian; ASCII numeric fields are zero-padded hexadecimal. ASCII
lengths count characters after the length field, including the timer in a
request or the end code in a response. The 4E serial is two binary bytes or
four hex characters, followed by reserved zeros of the same width. Serial is
echoed for each request; a nonzero reserved request field closes that client.

ASCII batch bits use one `0`/`1` character per point. Words use four hex digits.
The pinned client sends/decodes random dwords as one eight-digit hex integer
(high word first). The server defaults to swapped halves as described below.
Q-class random bit write values use two hex characters (`00`/`01`), unlike batch
bits; iQ-R uses four. Echo text and the CPU name remain literal ASCII, preserving text
case (unverified (case));
only numeric output is uppercased. The synthetic Q CPU code is `FFFF` in ASCII;
the client returns it as a string without normalizing case (binary yields `ffff`).

### Fixed-width text padding

`Server(text_pad=0x00)` fills the unused trailing bytes of the 16-byte CPU
model name with NUL. Use `Server(text_pad=0x20)` or `Server(text_pad=" ")`
for space fill, or any other byte-valued integer/character. The CLI accepts
hexadecimal or decimal integers, for example `--text-pad 0x00`,
`--text-pad 0x20`, or `--text-pad 32`. Invalid values are rejected before bind.

The CPU name returned by `cputype` (0101) is the **only emitted fixed-width
padded text field**. It uses the same raw 16 name bytes in 3E/4E and binary/
ASCII, across all profiles. The pinned client's `read_cputype` decodes exactly
16 bytes in both encodings, then calls `.replace("\x20", "")`; it removes all
spaces but does not remove NULs. The server does not hide or normalize this:

| Pad | Q client-visible name (Python string notation) |
|---|---|
| `0x00` (default) | `"VirtualPLC-Q\x00\x00\x00\x00"` |
| `0x20` | `"VirtualPLC-Q"` |

Other non-space fill characters also remain in the returned name. Arbitrary
byte fill is allowed on the wire; a byte such as `0xFF` is not valid UTF-8 in
this field and the pinned client raises UnicodeDecodeError. Select `0x20` for
the previous client-visible CPU name. Vendor CPU-name fill remains unverified.

Incoming ASCII device identifiers are fixed-width text with canonical `*`
suffix fill in the pinned client's constants. The parser accepts that format
and the configured `text_pad` in unused suffix positions, with unchanged field
widths and default decimal address parsing. `--ascii-numbering manual`
uses the device's declared base (including X/Y hexadecimal).
`--ascii-numbering fx5-octal` uses **octal X/Y only**, preserving W/B
hexadecimal and D decimal; 8/9 and A–F in X/Y addresses are rejected.
This is a 3E/4E *generic parser* option, not support for FX5-specific 1E
frames or a runnable FX5 hardware model. See
[FX5 SLMP frame scope](research/FX5_SLMP_FRAME_SCOPE_20261031.md).
Canonical identifiers take precedence;
ambiguous alternate prefixes are rejected rather than guessed. Fill bytes are
matched literally, including non-ASCII values, without changing device names.
Binary device codes are numeric and have no text fill.

Echo text and request passwords are length-delimited, with no unused trailing
text area. Echo replies contain exactly the declared text; lock/unlock replies
have empty data. Their request content is not trimmed: trailing pad-valued
password characters remain significant, and echo validation remains
hexadecimal (0-9, A-F, a-f, unverified (case)). Numeric zero fill, reserved zeros, and bit-nibble padding are
protocol fields and are not controlled by `text_pad`.

### Configurable ASCII dword word order

`Server(ascii_dword_order="swapped")` is the default. Select
`Server(ascii_dword_order="client")` to retain the previous client-compatible
mapping, or pass `--ascii-dword-order swapped|client` on the CLI. This is an
endpoint setting, independent of the decimal ASCII address numbering policy.

| Mode | ASCII wire halves | Random-read bytes for stored words [0x5678, 0x1234] | Stored words after ASCII random-write value `12345678` |
|---|---|---|---|
| `swapped` (default) | Low word, then high word | `56781234` | [0x1234, 0x5678] |
| `client` | High word, then low word | `12345678` | [0x5678, 0x1234] |

Only the two four-character halves of each dword are exchanged; hex digit
order inside each word is preserved. Conversion applies in both directions
to random read (0403) response dwords and random write (1402) request dwords,
across 3E/4E and all profiles, including native iQ-R dword storage. Mixed word
entries, batch word/bit operations and random bit values are unchanged. Binary
stays little-endian with the low word at the lower address in either mode.

A pymcprotocol ASCII dword write/read roundtrip remains symmetric in both
modes. In `swapped` mode, its numeric dword interpretation differs from batch
word access or direct memory access. For example, the client writes numeric
0x12345678 as `12345678`; memory then contains [0x1234, 0x5678], and an ASCII
random read returns the same `12345678` string. With `client`, memory instead
contains [0x5678, 0x1234]. A client reading preloaded memory must choose the
mode appropriate to that memory's word interpretation.

Low-word-first ASCII on physical PLCs is **suspected and unverified**. The
new default is a simulator policy, not a verified claim about vendor behavior.

### Numbering and overflow policy

The only supported numbering policy is explicitly **compat**. Q descriptors
have two device-code characters and exactly six decimal address digits, even
for X/Y/B/W/SB/SW/DX/DY/ZR. A client request for `X0A` contains `X*000010` and
accesses point 10, not point 16. Transport detection never selects a numbering
policy. Raw `X*00000A` is rejected; no hexadecimal address autodetection occurs.

ASCII addresses are limited to 0..999999 by field width. The client's formatter
does not truncate addresses wider than six digits. Such packets fail exact
payload validation and return a nonzero end code, with no mutation and no
connection close. Tests cover batch, random, and random bit write overflow,
including valid-prefix/invalid-tail atomicity. Binary addressing retains its
existing three-byte synthetic range. Vendor-specific capacities remain open.

Numeric input permits lowercase hexadecimal but rejects signs, whitespace,
non-hex characters and extra/truncated payload data. Bad framing, invalid
header numbers or reserved fields close the connection; a structurally valid
frame with a bad command payload gets an error response in the same transport.

The 4096-byte restriction belongs to the client's single `recv(4096)`, not the
server. Raw-socket tests read complete ASCII batch responses up to the manual
960-word cap (3840 data characters). Use a length-framed raw reader for large
responses; a client roundtrip is not a reliable oracle for responses larger
than its receive buffer.


## CPU control and locking

### Layouts and validation

| Command | Meaning | Payload |
|---|---|---|
| 1001 | Run | mode uint16 (1 or 3), clear_mode uint8 (0/1/2), fixed uint8 zero |
| 1002 | Stop | fixed uint16 1 |
| 1003 | Pause | mode uint16 (1 or 3) |
| 1005 | Latch clear | fixed uint16 1 |
| 1006 | Reset | fixed uint16 1 |
| 1630 | **Unlock** | password length uint16 + literal ASCII password |
| 1631 | **Lock** | password length uint16 + literal ASCII password |

Command IDs above are hexadecimal. Binary numbers are little-endian; ASCII
numbers use the existing fixed-width hexadecimal reader (twice the byte width).
Passwords stay literal ASCII and case-sensitive. Shared handlers and `Reader`
parse control payloads in both encodings; no transport-specific control logic
is copied. Data handlers retain their existing binary normalization path.

After command/subcommand lookup, disabled authentication returns C059. A
server-wide lock rejects gated commands with C200 before their payload is
parsed. Otherwise, short/extra payloads and mismatched password lengths return
C057; invalid fields, wrong Q password size or non-ASCII password bytes return
C05C. A correctly formed but wrong password returns C201. State prerequisites
are checked after field validation. Failed requests change no memory, state,
reset count or lock flag. These error precedence choices are design
policy. Earlier ASCII data-command error mappings are preserved.

### State and clearing

`Server(initial_state='RUN')` accepts RUN, STOP or PAUSE. Each instance exposes
`state`, `reset_count` (initially zero), and `locked` (initially False).
Force modes are accepted without additional semantics and cannot bypass state or lock
rules.

| Operation | RUN | STOP | PAUSE |
|---|---|---|---|
| Run | RUN, success | RUN, success | RUN, success |
| Stop | STOP, success | STOP, success | STOP, success |
| Pause | PAUSE, success | C202 | PAUSE, success |
| Latch clear | C202 | STOP, success | C202 |
| Reset | C202 | STOP, success; increment reset_count | C202 |

State initialization and each accepted run/stop/pause/reset mirror SD203:
STOP=0, RUN=1, PAUSE=2. This is an **unverified synthetic encoding**, not a
manual-derived PLC register layout. A supplied Memory must permit SD203 access.
SD remains writable; the mirror is refreshed when those commands execute,
including idempotent commands. Latchclear and authentication do not transition
the CPU or refresh the mirror.

The Q profile's latch range table defaults to all L points. Pass
`latch_ranges={device: [(minimum, maximum), ...]}` to replace the default.
Spans are inclusive device-point ranges, copied at construction and validated
against profile address bounds. `{}` means no latched ranges. Clear operations
act only on sparse stored points; table spans may extend beyond a narrower
custom memory range without allocating or accessing those points.

- Latchclear clears only points inside latch ranges and requires STOP.
  Latch ranges are cleared by latchclear and preserved by remote_run(clear_mode=1).
- Run clear_mode 0 leaves all memory alone; 1 clears non-latch, non-special
  points; 2 clears every non-special point, including latch ranges. An
  idempotent run still honors its clear_mode.
- SM and SD are never cleared, even if included in a latch override. The
  separate SD203 state mirror still updates on a transition/idempotent control.
- Reset clears no memory, sets STOP, increments reset_count, sends success
  on the same connection and keeps it open.

The server's existing request lock covers validation, clearing, CPU updates and
the state mirror, so other wire requests cannot observe a partial operation.

The pinned client's `remote_reset` swallows receive/status errors and may sleep
and reconnect. Reset error tests therefore use raw sockets. Successful reset
tests forbid reconnect, assert the socket object stays the same, and send echo
afterward. The client's successful-reset socket timeout remains 1 second,
as described in DESIGN; the server does not alter that client behavior.

### Lock scope, sources and unresolved vendor claims

`Server(password=None)` disables both lock/unlock with C059. A configured Q
password must contain exactly four ASCII characters; other values are rejected
at construction. Lock state is **server-wide**, survives disconnect, and gates
only `LOCK_GATED = {1001,1002,1003,1005,1006}`. Data, echo and CPU-type commands
remain available. Lock/unlock with the correct password is idempotent; wrong
password changes nothing. Reset cannot bypass or clear the lock.

Server-wide, control-only gating is a simulator policy. Physical PLC lock scope
and behavior have not been verified; the password is not network authentication.

| Code | Name | Source | Status |
|---|---|---|---|
| C200 | LOCKED | memory | unverified |
| C201 | WRONG_PASSWORD | memory | unverified |
| C202 | INVALID_STATE | design | unverified |

C200, C201 and C202 are not supported by manual SH-081257 3.5; C203/C204 are the documented remote-password codes; remap tracked in issue #5. Both remain
unverified; their implemented values are unchanged. Error metadata permits
`source=manual|client|design|memory` and `status=verified|unverified`.

The SD203 encoding, C200/C201/C202 policies, synthetic latch policy, transition and
reset policies, and the vendor lock comparison need authoritative verification.
All M5 policy/byte-vector assertions are marked `pytest.mark.unverified`.


## Profiles and iQ-R

Q, L, QnA, iQ-L and iQ-R are selected explicitly by `Server(profile=...)` and
`Memory(profile=...)`. A supplied Memory must have the same named profile as
the Server; conflicting configuration raises ValueError. Profiles have their
own device/range and identity tables. The pinned client gives Q/L/QnA/iQ-L the
same supported common families and wire layout. The only per-profile difference is
the manual-derived batch caps (QnA is half the E71 capacity); no other capacities
are invented for those names.

### Verified client layouts (rows marked random-limit are manual-derived, SH-080008 p.98/105/108; code assignment unverified)

Source: the installed pinned pymcprotocol 0.3.0 `type3e.py` and
`mcprotocolconst.py`. All client branches listed in DESIGN were inspected:
descriptor construction, batch/random subcommands, bit-value widths and
password bounds.
The client normalizes plctype to its constants, including identity comparisons
used in some of these branches. Type4E inherits the same command encoding.

| Property | Q-class: Q, L, QnA, iQ-L | iQ-R |
|---|---|---|
| Binary address / device code | 3 / 1 bytes | 4 / 2 bytes |
| ASCII device code / decimal address | 2 / 6 characters | 4 / 8 characters |
| Word / bit data subcommand | 0000 / 0001 | 0002 / 0003 |
| Random bit-write value | 1 byte / 2 hex characters | 2 bytes / 4 hex characters |
| ASCII password length | Exactly 4 | 6–32 |
| Default synthetic point range | 0..0xFFFFFF | 0..0xFFFFFFFF |
| Random read max (`words + dwords`) | 192 | 96 |
| Random word/dword write max (`words*12 + dwords*14`) | 1920 | 960 |
| Random bit write max (`points`) | 188 | 94 |

All numeric binary fields remain little-endian. ASCII retains compat decimal
numbering, uppercase numeric output and lowercase-hex tolerance. Eight-digit
ASCII iQ-R addresses have a separate representational ceiling of 99,999,999;
overwidth packets return an error without truncation or mutation. Binary can
address the full synthetic uint32 range. The ASCII client formats SS/SC/SN
storage as STS*/STC*/STN* on iQ-R (SS/SC/SN on Q-class); parser input names
remain STS/STC/STN on both classes.

`Profile.wire` supplies the widths, subcommands and password bounds. Shared
descriptor parsing, ASCII normalization, batch/random handlers and control
handlers consume those values. No Q server/codec or command logic was copied.
Frame/encoding auto-detection remains independent of the selected profile.

Data requests with the other wire class's subcommands are rejected, including
empty or ambiguous payloads; the server never guesses the profile from data.
It keeps the connection usable for subsequent valid requests. Device codes
are checked as complete uint16 values on iQ-R, not truncated to their low byte.

There is a protocol limitation to the phrase "plctype mismatch": Q-class
names are wire-identical, and echo/CPU/control packets carry no wire-class
identifier. Such a client-name mismatch cannot be detected from those bytes.
The implemented check applies to addressed data commands; the server's named
profile always determines the capabilities and returned CPU identity.

### Synthetic identities and ranges

| Profile | CPU name | CPU code (hex) | Batch word cap (bin / ASCII) | Batch bit cap (bin / ASCII) |
|---|---|---|---|---|
| Q | VirtualPLC-Q | FFFF | 960 / 960 | 7168 / 3584 |
| L | VirtualPLC-L | FFFE | 960 / 960 | 7168 / 3584 |
| QnA | VirtualPLC-QnA | FFFD | 480 / 480 | 3584 / 1792 |
| iQ-L | VirtualPLC-iQ-L | FFFC | 960 / 960 | 7168 / 3584 |
| iQ-R | VirtualPLC-iQ-R | FFFB | 960 / 960 | 7168 / 3584 |

These are simulator identities, not actual Mitsubishi CPU models. Names are
filled to 16 bytes with `text_pad` (NUL by default). Batch point caps (`Profile.batch_max`
and `BATCH_MAX` in `profiles.py`, keyed by `(profile, wire, unit)`) are manual-derived
from SH-080008 (p.87/91/96, Ethernet E71 column); `QnA` shares the `Q-class` wire but
has lower batch caps. `batch()` rejects zero or over-limit points with `0xC051`
(`POINTS_OUT_OF_RANGE`) for word units and `0xC052` (`BIT_POINTS_OUT_OF_RANGE`) for bit
units (SH-081257 3.5; code assignment unverified, real-PLC verification still open in
#2). `--max-points` defaults to `None`; when set, the effective batch limit is
`min(manual_cap, max_points)`. Direct `Memory` calls are uncapped. Profile ranges are synthetic
address-width
ceilings, not vendor-verified capacities; custom Memory limits still override
per-family ranges. Default latch retention covers the selected profile's entire L range.
CPU state, reset, lock scope, SD203 mirror and clearing policies remain shared;
only password bounds change for iQ-R.

### Extra iQ-R families

All extra codes are copied from `DeviceConstants`, with decimal base 10.
Common devices retain the codes/bases/kinds listed in the common device table above.

| Family | Code (hex) | Model kind | Client reachability |
|---|---|---|---|
| LTS | 51 | bit | Yes |
| LTC | 50 | bit | Yes |
| LTN | 52 | native dword | Yes; client type metadata says bit |
| LSTS | 59 | bit | Yes |
| LSTC | 58 | bit (unverified coil interpretation) | Constant only; raw requests |
| LSTN | 5A | native dword | Yes |
| LCS | 55 | bit | Yes |
| LCC | 54 | bit | Yes |
| LCN | 56 | native dword | Yes |
| LZ | 62 | native dword | Yes |
| RD | 2C | word | Yes |

Two client inconsistencies are explicit:

- `get_devicetype('iQ-R', 'LTN')` returns bit. The command encoders do not use
  that function to select value widths or validate access. By simulator policy, the
simulator deliberately models LTN as native dword, rejects bit
  access, and records that interpretation as unverified.
- LSTC has code 58, but neither binary nor ASCII lookup nor get_devicetype
  handles its name. It is modeled as an independent bit family and tested via
  raw packets; the client generator excludes it with an explicit reason.

Z has neither a supported constant nor a client lookup path; it is not added.
LZ is supported and reported as dword by the client. Timer/counter contacts,
coils and values remain independent storage without execution.

### Native dword stride policy (unverified)

The client always encodes batch word values as uint16 and random dword values
as uint32, regardless of device family. It provides no authoritative physical
stride information. The selected simulator policy reconciles those encodings
with native dword storage as follows:

- Each LTN/LSTN/LCN/LZ address names one unsigned 32-bit point.
- A random dword at address n occupies that one point; the next dword at n+1
  is independent. On ordinary word devices, a dword still occupies n and n+1.
- Word access starts at the low half of native point n. A batch of k words
  streams low(n), high(n), low(n+1), high(n+1), and so on. Count remains a
  count of 16-bit words, as the client expects. An odd final write preserves
  the untouched high half; a single random word updates only the low half.
- Range validation uses ceil(k/2) native points and completes before mutation.
  Bit access is invalid. Sparse clearing and latch overrides address whole
  native points. Duplicate/overlapping random writes retain wire-order semantics.

Client roundtrips establish compatibility with these choices, not real-PLC
correctness. Native stride, LTN/LSTC interpretations, synthetic ranges and CPU
identities remain unverified vendor claims; policy/vector tests are marked
`pytest.mark.unverified`. Prior SD203, error-code and ASCII dword-order caveats
remain unverified.


## Unverified behavior

Empty or over-limit batch counts are rejected with C051 (word units) or C052
(bit units), and empty (total count 0) or over-limit random counts are rejected with
C053 (bits) or C054 (words/dwords) (manual-derived; C051/C052/C053/C054 assignment unverified,
not verified PLC behavior). Dwords over bit devices span 32
packed points with 16-point head alignment. Malformed random lengths use C057,
invalid access uses C05C, and range overflow uses C056; these mappings await
manual verification. ASCII dword order is configurable: `swapped` (low word
first) is the default and `client` (high word first) preserves client mapping.
The suspected real-PLC low-word-first ordering remains unverified. Nonzero
reserved fields close the connection. Per-request transport switching is a
simulator feature. See DESIGN's open items for remaining vendor checks.


## Lifecycle, snapshots, timers and routes

The package exports Server, Memory, FaultPlan and __version__. A context starts
on entry and stops/joins on exit. Use one lifecycle per instance. Ctrl+C uses
bounded waits on Windows; SIGTERM/SIGBREAK follow graceful cleanup. Forced
Windows TerminateProcess bypasses handlers. Bind errors exit 1 without a
traceback; invalid configuration exits 2. Verbose logging reports one-line
command/frame/wire/end-code summaries and close reasons, excluding payloads.
It is off by default; unexpected worker errors still report to stderr.

Memory.load(data) validates complete JSON before overlaying native points.
Memory.dump() groups contiguous stored points using the same schema; explicit
zeros are retained. Values are unsigned bits/words/native dwords. See
[seeding examples](../README.md#memory-seeding-snapshots-and-embedding).
Load/mutate before start and dump after stop. Direct memory operations have no
lock: live clients must use wire requests for synchronization. Limits use
inclusive native points. Repeated CLI limits use the last span per family;
latch spans accumulate and replace profile defaults.

The monitoring timer is parsed but ignored. The client accepts seconds
1..16383, encodes four 250 ms units per second and sets soc_timeout to seconds+1.
Its setaccessopt(timer_sec=0) is ignored; soc_timeout is an attribute, not an
access-option keyword. Routes echo but all network/PC/module-I/O/station values
alias one memory/state target. Zero-valued client options are ignored even
after nonzero settings.

Client device names are case-sensitive; hex suffixes can be lowercase. Raw
ASCII device names are case-insensitive. Unicode echo can pass client
str.isalnum() but is rejected as invalid ASCII/alphanumeric data without
closing the connection. SD203 mirrors accepted state changes in one direction:
writing SD203 never changes state. Errors leave connections usable for stop,
reset and further requests. Invalid client 4E serials fail before sending.
