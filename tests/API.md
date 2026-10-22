# M1–M6 production API required by tests

- `server.Server(host='127.0.0.1', port=0, profile='Q', memory=None,
  response_hook=None, max_points=4096, idle_timeout=2.0,
  initial_state='RUN', latch_ranges=None, password=None)`.
- `.start()` binds/listens and starts workers before returning; `.address` is `(host, actual_port)`.
- `.stop()` synchronously closes clients/listener and joins workers; idempotent, including incomplete frames.
- Accepted sockets use TCP_NODELAY; EOF, bad framing or `idle_timeout` closes only that client.
- `response_hook(response_bytes) -> bytes` transforms each complete encoded response; None means identity.
- Q/L/QnA/iQ-L/iQ-R have synthetic CPU identities; names are padded to 16 ASCII characters (see M6).
- Echo response: length uint16 + text. ASCII encodes numeric fields as uppercase hex.
- `memory.Memory(profile='Q', limits=None)` accepts inclusive `{device: (min, max)}` point ranges.
- Profile devices expose `code`, `base`, `kind`, `minimum`, `maximum`; ranges remain synthetic.
- `.read_words(device, head, count)` / `.read_bits(...)` return unsigned lists.
- `.write_words(device, head, values)` / `.write_bits(...)` return None; invalid input raises ValueError.
- Memory is sparse, initially zero and isolated by instance/family; no timer/counter execution.
- Native dword heads address 32-bit points; word counts stream low/high halves, preserving an untouched half.
- Bit-device word views pack 16 bits LSB first at aligned heads; bit access to word devices is invalid.
- `codec.decode_request(frame_bytes)` returns `.frame`, `.wire`, `.serial`, `.route`
  `(network, pc, io, station)`, `.timer`, `.command`, `.subcommand`, raw wire `.data`.
- `codec.encode_response(request, end_code=0, data=b'') -> bytes` echoes route/serial.
- `codec.pack_words(values)` / `unpack_words(data)` use unsigned LE uint16.
- `codec.pack_bits(values)` / `unpack_bits(data, count)` use high nibble first, odd low nibble zero.
- Frames auto-detect 3E/4E, binary/ASCII per request; reserved fields must be zero; bad framing raises ValueError.
- `commands.ERROR_CODES[code]` has `name`, `source`, `status`; all current rows remain unverified.
- Each request validates before mutation under one lock; `max_points` limits batch points, not response bytes.
- Random counts are uint8; zero is empty/no-op. Responses put words before dwords; dwords store low word first.
- Duplicate/overlapping random writes apply in wire order. SS/SC/SN use STS/STC/STN client names.
- `Profile.wire` selects widths/subcommands; ASCII compat addresses use 6 (Q-class) / 8 (iQ-R) decimal digits.
- `.state` is RUN/STOP/PAUSE (default RUN); SD203 mirrors STOP=0, RUN=1, PAUSE=2 (unverified).
- `.last_force` records the last accepted run/pause force flag; initially False, with no extra force semantics.
- `.reset_count` starts at zero; successful reset requires STOP, replies on the same connection and keeps it open.
- Reset sets STOP and clears no memory; state mirroring still writes SD203. SD203 must be addressable.
- Profile `LATCH` defaults to all L points; `latch_ranges={device: [(lo, hi), ...]}` replaces it; `{}` disables retention.
- Latchclear requires STOP and clears only latch ranges. Run clear modes: 0 none, 1 non-latch, 2 all non-special.
- SM/SD are writable and never cleared. `.latch_ranges` contains a copied, validated table of inclusive point spans.
- `.locked` starts False and survives disconnect; password None disables lock/unlock with C059.
- Passwords are ASCII: Q-class exactly 4 characters, iQ-R 6–32; invalid configuration raises ValueError.
- `commands.LOCK_GATED` contains run/stop/pause/latchclear/reset; all data/echo/cputype commands stay available.
- See [M5](../docs/M5.md) for control policy and [M6](../docs/M6.md) for profiles, exclusions and unverified stride.
