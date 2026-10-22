# M1 production API required by tests

Test contract only: threaded TCP on localhost, port 0; no production stubs.

- `server.Server(host='127.0.0.1', port=0, profile='Q', memory=None,
  response_hook=None, max_points=4096, idle_timeout=2.0)`.
- `.start()` binds/listens and starts workers before returning; `.address`
  is `(host, actual_port)`. `.stop()` closes listener/clients and joins workers;
  it is synchronous and idempotent, including with incomplete client frames.
- Accepted sockets use TCP_NODELAY. EOF/malformed framing closes that client.
  Idle/incomplete clients close after `idle_timeout`; other clients stay usable.
- `response_hook(response_bytes) -> bytes` transforms each complete response
  after dispatch and before its full transmission. None means identity.
- M1 Q CPU identity is synthetic: `VirtualPLC-Q`, code `0xFFFF` (not vendor data).
  Wire body: 16 ASCII bytes padded with spaces, then a little-endian uint16.
- Echo body: little-endian uint16 length followed by echoed ASCII bytes.
- `memory.Memory(profile='Q', limits=None)` accepts optional inclusive
  `{device_name: (minimum, maximum)}` test ranges, in device points.
- `.read_words(device, head, count)` / `.read_bits(...)` return unsigned lists;
  `.write_words(device, head, values)` / `.write_bits(...)` return None.
- Memory is sparse, initially zero, isolated by instance and family. Invalid
  input raises ValueError before any mutation. Request operations are atomic.
- Word view of bit devices packs 16 points LSB first, with aligned heads.
  Bit access to word devices is invalid; SM/SD are writable.
- `codec.decode_request(frame_bytes)` returns an object with `.route`
  `(network, pc, io, station)`, `.timer`, `.command`, `.subcommand`, `.data`.
- `codec.encode_response(request, end_code=0, data=b'') -> bytes` echoes route.
- `codec.pack_words(values)` / `unpack_words(data)` use unsigned LE uint16.
- `codec.pack_bits(values)` / `unpack_bits(data, count)` use high nibble first,
  odd low nibble zero. Invalid values, padding or lengths raise ValueError.
- `decode_request` requires one exact 3E binary frame, minimum body 6 bytes;
  bad headers/lengths/trailing data raise ValueError. Dispatch validates data.
- `commands.ERROR_CODES` maps integer codes to dicts with `name`, `source`,
  `status`. Names: OK, POINTS_OUT_OF_RANGE, ADDRESS_OUT_OF_RANGE,
  UNSUPPORTED_COMMAND, REQUEST_DATA_ERROR, DATA_LENGTH_MISMATCH.
  DESIGN §7 rows initially have source='design', status='unverified'.
- Server validates whole requests before mutation and serializes each request.
  `max_points` is per-request, independent of the client's 4096-byte recv limit.
  Unknown subcommands, illegal access, and unknown devices return nonzero codes;
  exact codes not listed in DESIGN remain unspecified.
