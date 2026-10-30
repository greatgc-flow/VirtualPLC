**Scope:** I used only read tools. I had no grep or list tool, so I read each file directly and did not look for existing tests. Paths are under `src/pymcprotocol/`. `type3e.py` is abbreviated `t3e` and `mcprotocolconst.py` is `const`.

## (1) Findings against the VirtualPLC facts

| Fact | Status | Where |
|---|---|---|
| Error info after end code | **Not handled.** `_check_cmdanswer` reads only the end code (binary 3E idx 9, ASCII idx 18; 4E idx 13/26). `MCProtocolError` has no fields for network, station, module I/O, command or subcommand. These 9 binary bytes / 18 ASCII chars follow the end code and are ignored. | t3e:414-421; `mcprotocolerror.py:13-17`, `:31-41` |
| ASCII device numbers hex for X/Y/B/W/SB/SW/DX/DY/ZR | **Broken.** The client parses the number with the right base, then writes it back as decimal. `X10` becomes `000016` (X16 on the PLC) and `X1A` becomes `000026`. Binary mode is correct. | t3e:339, 342, 345 (`str(int(..., devicebase))`) |
| Random-access point limits | **Absent.** No client-side check. `randomread` and `randomwrite` only cap each count at 255 through the `"byte"` encode, and the error then reads "Exceeeded Device value range". Bit random write has no 188/94 check. | t3e:593-641, 643-685, 687-727 |
| Length mismatch → C057 | **No special handling.** C057 raises the generic `MCProtocolError`. The client never checks the response length field against the received bytes. | t3e:414-421 |

- **Limit pairs:** I assume 192/96, 1920/960 and 188/94 mean binary/ASCII. Please confirm against PROVENANCE.md. iQ-R devices are 4 bytes wider, so the write coefficients may differ for iQ-R.
- **Hex device names:** `_make_devicedata` splits type and number with `\D+`, so `XFFF` or `XA0` is parsed as a device named `XFFF`/`XA0` and raises `DeviceCodeError`. The message tells the user to write `X0FFF` (t3e:322, `const:27-30`).

## (2) Latent bugs

1. **Empty or short reply counts as success.** In binary mode `int.from_bytes(b"")` returns 0, so `_check_cmdanswer` sees end code 0 (t3e:419, 405). ASCII raises a vague `ValueError` instead.
2. **`_recv` makes one `recv(4096)` call with no framing.** It never reads the length field, so TCP fragmentation gives a partial frame. ASCII bit reads over about 4000 points are truncated (t3e:148-155).
3. **Reply headers are not validated.** There is no check of the D000/D400 subheader, and no check that the 4E serial matches the request.
4. **`setaccessopt` uses truthiness checks.** `network=0`, `pc=0`, `dest_moduleio=0`, `dest_modulesta=0` and `timer_sec=0` are silently ignored, so you can't reset them (t3e:228-263).
5. **Bare `except:` in encode and decode** mask every error as "Exceeeded Device value range" or "Could not decode byte to value" (t3e:387, 410). Device-number overflow in `_make_devicedata` (`to_bytes`, lines 332-336) escapes as a raw `OverflowError`.
6. **Word writes are signed-only.** `isSigned=True` rejects 32768..65535, and dwords have the same limit (t3e:530, 674, 677). Reads are always signed (t3e:455).
7. **`remote_reset` swallows every exception** with a bare `except` and reconnects, which hides `MCProtocolError`. It sets the socket timeout to 1s and never restores it. It also reconnects without closing the old socket (t3e:853-862).
8. **`MCProtocolError` problems:**
   - `errorcode` is a string like `"0xC059"`, not an int.
   - The class docstring is copied from `DeviceCodeError`.
   - `__init__` never calls `super().__init__`, so `args` is empty and pickling breaks.
   - The same missing `super().__init__` applies to `UnsupportedComandError`, `CommTypeError` and `PLCTypeError`.
   - `UnsupportedComandError` (C059) carries no code or error info, and its message wrongly assumes a CPU-direct connection.
   - The name has a typo ("Comand").
9. **Device constants:**
   - `LSTC` has a constant (`const:73`) but no branch in `get_binary_devicecode`, `get_ascii_devicecode` or `get_devicetype`.
   - `get_devicetype` returns BIT for `LTN` (`const:348-349`), but LTN is a dword device like `LSTN`/`LCN`. `get_devicetype` is also unused.
   - The device codes themselves match the manuals.
10. **`plctype is const.iQR_SERIES`** compares strings with `is` (t3e:331, 340, 715, 911, 946). It works only because the value is always set from the constant.
11. **No range or size validation on read sizes.** `batchread_*` and `batchwrite_*` don't check 1..960 words or 1..7168 bits. `randomwrite` and `randomread` also don't reject empty lists.

## (3) TDD work list (priority order)

1. **ASCII hex device numbers.** Fix t3e:339-345 to emit hex for base-16 devices, with a decimal check for D/M. Test: ASCII `_make_devicedata("X1A")` → `b"X*" + b"00001A"`, `"X10"` → `000010`, iQ-R `"W1F"` → `b"W***0000001F"`, `"D100"` → `000100`.
2. **Parse error responses.** Parse end code plus error info into `MCProtocolError` (add int `endcode`, `network`, `pc`, `module_io`, `station`, `command`, `subcommand`). Cover 3E and 4E, binary and ASCII. Test: feed a canned D000 frame with end code C059 and error info `00 FF FF03 00 0104 0000` to `_check_cmdanswer`, and assert every field.
3. **Truncated or empty reply.** Raise a clear error instead of treating it as success. Test: `_check_cmdanswer(b"")` and an 8-byte frame must raise. Also check the subheader and length field, and the 4E serial.
4. **Random-access limit checks.** Add `ValueError` before sending, parametrised by comm type and PLC type once the pairs are confirmed. Test: 193 words, 190+3 dwords, write `words*12+dwords*14 > 1920`, and 189 bits must raise with no socket call. The exact boundary values must pass.
5. **Framed receive.** Loop on the length field. Test: a fake socket returning a frame in 3 chunks must reassemble, and a 5000-char ASCII frame must not be truncated.
6. **`setaccessopt` zero values.** Use `is not None`. Test: `setaccessopt(network=5)` then `network=0` leaves `network == 0`, and the same for `pc`.
7. **Exception hygiene.** Keep the original `errorcode`, add the int `endcode`, call `super().__init__`, fix the docstring, and make C057 and C059 distinct subclasses that still carry the error info. Test: `pickle.loads(pickle.dumps(e))` round-trips, `e.endcode == 0xC057`, and `str(e)` includes the command.
8. **Device constants and unsigned words.** Add `LSTC`, correct `LTN` to dword, and allow unsigned 0..65535 word writes. Test: the iQ-R `LSTC` code is 0x58, `get_devicetype(iQR, "LTN")` is dword, and `batchwrite_wordunits("D0", [65535])` encodes `FF FF`.
session: sess_cf7e9a8451402821 resumed gen1
