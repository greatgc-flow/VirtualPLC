# VirtualPLC v2 — Design (SDD, pre-TDD)

Status: APPROVED cc (round 4); cx round-4 blocks applied verbatim (peer rounds 1-4 done: cx, cc; ag quota exhausted until ~2026-10-24).
Goal: a virtual Mitsubishi MC-protocol PLC that recursively and MECE-covers every wire-visible feature of
[pymcprotocol](https://github.com/greatgc-flow/pymcprotocol) 0.3.0 (the client). Default profile: **Q series**.
Not for industrial use. Binds 127.0.0.1 by default.

## 1. Verified client facts (src/pymcprotocol, v0.3.0)
- Only `plctype == iQ-R` changes wire format (type3e.py:331,340,435,472,520,556,607,663,704,715,911,946). Q, L, QnA, iQ-L share one **wire class**.
- Client sends one `send`, reads one `recv(4096)` (type3e.py:94,148-155); never validates response subheader/serial/length; reads end code at fixed offset (3E bin 9, 3E ascii 18, 4E bin 13, 4E ascii 26).
- Only end code 0xC059 raises a distinct error; any other non-zero is generic (mcprotocolerror.py).
- ASCII device numbers are sent as **decimal text** even for hex-numbered devices X,Y,B,W,SB,SW,DX,DY,ZR (type3e.py:339).
- Truncated binary response decodes status 0 == success (type3e.py:419) — client misbehaviour, label in tests.
- `remote_reset` sets a 1 s socket timeout; on any receive/status failure it sleeps 1 s and reconnects (connect restores the configured `soc_timeout`); on success the existing socket keeps the 1 s timeout (type3e.py:853-862, 123).
- Random cmds: <=255 words and <=255 dwords per request; word values signed 16-bit, dword signed 32-bit, checked client-side.
- Echo: 1-960 alphanumeric chars. CPU type: 16-char space-padded name + code. LSTC unreachable from the client.
- Falsy options (`network=0`, `pc=0`, `timer_sec=0`) ignored by `setaccessopt`.

## 2. Decisions (consensus cx+cc, with amendments)
| ID | Decision |
|---|---|
| D1 | `archive/m1-m29` tag on old branch; new branch `v2/m0`; main history untouched. Drop gates/evidence/progress docs/scripts. Migrate only: concrete scenarios from `suite/catalog/test_cases.jsonl` (fragmentation, atomicity, concurrency), compat round-trips + wheel-hash pin, fixture provenance labels. Closing PR #1 happens after v2 M0 lands. |
| D2 | Five named profiles (Q, L, QnA, iQ-L, iQ-R) mapped to two wire classes (`Q-class`, `iQ-R`). Same wire class != same capabilities; ranges/CPU names are per profile. A Q-class server receiving iQ-R subcommands (0x0002/0x0003) returns an error. |
| D3 | Layout `virtual_plc/{server,codec,commands,memory,profiles,__main__}.py`; tables in Python. stdlib + pytest only. One lock per request; validate whole request before any mutation; each response fully written via `sendall`/checked send loop; `TCP_NODELAY`; tests bind port 0. |
| D4 | Tests generated from tables over **applicable** combinations only (explicit exclusions with reasons). Oracles: (i) real pymcprotocol 0.3.0 = *client-compat*; (ii) hand-authored expected bytes in test code, independent of `codec.py`/tables/client = *manual-derived* (never "manual-correct", never "capture"). Oracle pin = PyPI 0.3.0 wheel hash (verify checkout matches). |
| D5 | Numbering policy is explicit per endpoint/profile (`compat` default = decimal text as client sends). Never autodetect. `manual` policy (hex digits) later; discriminator test address `X0A`. Also record suspected divergence: ASCII dword word-order. All manual claims from memory are marked `unverified`. |
| D6 | Milestones below. 4096 is a *client receive limit*, documented separately from server limits; large valid responses tested with a raw-socket client. |
| D7a | Timers/counters (TS/TC/TN, CS/CC/CN, SS/SC/SN): independent storage, no timer execution. Own milestone step. |
| D7b | SM/SD writable by default; per-range read-only table starts empty. |
| D7c | Dword on word devices = two consecutive words, low word at lower address. Native-dword devices (LTN etc., iQ-R) need explicit stride rules at M6. |
| D7d | Lock/unlock semantics deferred to M5 (affected commands, connection vs server scope, failed auth, disconnect/reset). |
| D7e | Error-table rows carry `source: manual|client|design` + `status: verified|unverified`. Tests never hard-assert `unverified` rows without the marker; reported separately. |

## 3. Memory model
- Sparse unsigned storage per device family. Bit devices: 1 bit/point. Word view of a bit device: for head address h, response word j bit i == point h+16j+i (LSB first; `M16` word-read yields M16..M31); head must be a multiple of 16 (unverified vs real PLC -> reject otherwise, flagged). Bit access to word devices (D etc.): rejected with error.
- Overlapping/duplicate random-write entries applied in request order.
- Validation (range, count, legality) completes before any write (atomic).

## 4. Codec (Q wire class, M1)
- 3E binary request: `50 00 | net | pc | io(2 LE) | stn | len(2 LE)=2+cmd+sub+data | timer(2) | cmd(2) | sub(2) | data`.
- Response: `D0 00 | net pc io stn | len(2) | end(2) | data` (end code first inside len).
- Batch read/write (cmd 0401/1401), sub 0000 (word) / 0001 (bit): `addr(3 LE) devcode(1) points(2)`; words LE; bits 2/byte high nibble first, odd count padded low nibble 0.
- Server: length-framed parser (total = 9 + len), fragmentation, merged requests, clean EOF; malformed frame -> close.

## 5. Milestones
| M | Scope | Exit criteria |
|---|---|---|
| M0 | Scaffold, migration, pinned oracle, test generator skeleton, `pytest` green | `pytest` runs; old assets archived |
| M1 | Transport + error table + 3E binary Q: batch word/bit R/W for D,M,X,Y,B,W,R,ZR,SM,SD; echo (0619) and cputype (0101); response-transform hook seam; basic disconnect/timeout tests | Real client round-trips every M1 cell; manual-derived vectors pass |
| M2 | Random read/write (+bit random write, mixed word/dword) | boundary counts 0/1/255 via client; 256 via raw-socket helper (client rejects it, test that separately) |
| M2b | Timers/counters, SB, SW, DX, DY, L, F, V | per-device base/range table complete |
| M3 | 3E ASCII (incl. ascii overflow policy, uppercase out/lowercase in) | cross product generated |
| M4 | 4E (serial echo, reserved zeros) | |
| M5 | Control: run/stop/pause/latchclear/reset, lock/unlock; CPU state machine | semantics decided before coding |
| M6 | iQ-R profile (4+2 addressing, LT*/LST*/LC*/LZ/RD, pw 6-32, 2-byte random bit) | |
| M7 | Fault injection (delay/drop/truncate/bad end code/reset reconnect) on the M1 hook | truncation tests labelled client-misbehaviour |
Extension point = command registry dict (no extension milestone).

## 6. M1 test-case seeds (TDD input)
T1 batch word write->read roundtrip D0..D(n); T2 bit roundtrip incl. odd count; T3 word read over M (16-pt packing); T4 hex-base devices X/Y/B/W/ZR addressing; T5 range overflow -> end code; T6 points=0 / over-limit -> end code; T7 unsupported command -> 0xC059; T8 iQ-R subcommand on Q profile -> error; T9 fragmented request (1 byte at a time); T10 two requests in one segment; T11 EOF mid-frame; T12 atomic failure (partial-range write mutates nothing); T13 concurrent clients, no torn writes; T14 echo 1/960 chars; T15 cputype name+code; T16 large valid response via raw socket (>4096) accepted by server; T18 word-read of `M16` observes M16..M31 (not M256..); T17 golden request bytes: client encoder vs hand-authored vectors.

## 7. End-code table (M1; all `unverified` until manual cross-check)
0x0000 OK; 0xC051 points out of range; 0xC056 address out of range; 0xC059 unsupported command; 0xC05C request data error; 0xC061 data length mismatch. No row yet for: iQ-R subcommand on Q profile, bit access to D, unaligned bit-device head -> T8 asserts only non-zero end code until added.

Response bodies (add at M1 start): cputype = 16-char space-padded name + 2-byte code; echo = 2-byte length + echoed data.

## 8. Open items
Authoritative per-series limits/ranges; ASCII overflow policy; native dword stride; SM/SD per-range RO; lock scope; reset behaviour; exact client pin; real-PLC unaligned bit-head word reads.
