# Declarative response faults

`Server(fault_plan=None)` keeps the ordinary response path: no matching,
fault waits, alternate sender, or per-connection request (`nth`) counting. The
server always counts admitted TCP sessions, but that ordinal only matters to a plan.
Opt in with
`virtual_plc.faults.FaultPlan(steps)` or `FaultPlan.from_file(path)`.
See [behavior](BEHAVIOR.md) for the normal server API.

## One schema for Python and CLI

Python accepts the steps array below. A JSON file wraps it in a root object
containing only `steps`:

```json
{
  "steps": [
    {
      "match": {"command": "0x0619", "connection": 1, "nth": 1},
      "action": {"type": "delay", "seconds": 0.02}
    },
    {
      "match": {"command": "0x0401"},
      "times": 2,
      "action": {"type": "bad_end_code", "code": 49241}
    }
  ]
}
```

```powershell
.\.venv\Scripts\python.exe -m virtual_plc --host 127.0.0.1 --port 5000 --fault-plan faults.json
```

The CLI loads and validates the file before constructing or binding the server.
Bad files, unknown fields/actions or invalid arguments produce an argparse
error. Omitting the option is the default inert mode. An empty steps array is
valid but has no selected actions. The CLI defaults to Q/RUN; use `--initial-state STOP`
for reset scenarios.

Each step has `action`, optional `match` (default `{}`), and optional positive
integer `times` (default 1). Unknown fields are rejected. An action is an object
with a required `type` and the parameters listed below. Numeric times/pauses
must be finite, nonnegative and at most `threading.TIMEOUT_MAX`; byte counts and field values must be integers.

## Matching and ordering

`FaultPlan.select(command, *, nth, connection)` reserves and returns one copied
action dictionary, or None. It is called after dispatch under the server's
request lock. Selection and usage decrement are atomic under a plan lock.
No locks remain held during fault waits or network transmission.

- `match.command` is a uint16 integer or numeric string (`"0x0619"` is convenient
  in JSON). It matches the original MC command, including commands that return
  a normal error response.
- `match.connection` is the 1-based ordinal of TCP sessions this Server admitted
  (across all TCP listeners). Connections closed by the `max_clients` limit or
  during shutdown take no ordinal, and the ordinal restarts at 1 on each
  `start()` (internal 1E STOP-owner IDs stay unique across restarts).
- `match.nth` is the 1-based ordinal of all decoded requests on that connection,
  not the nth occurrence of a command. Mixed frame/encoding requests count in
  the same sequence. Malformed frames which cannot be decoded do not count.
- Specified selectors are ANDed; omitted selectors are wildcards. The first
  eligible step in declaration order wins. An earlier nonmatching step does
  not block a later step, and only one step applies to a request.
- A reserved use is consumed even if the peer disconnects or shutdown cancels
  delivery. It is not retried or refunded. Use a fresh plan for an independent
  run: counters belong to the plan; sharing one across servers shares remaining
  uses, while connection IDs remain local to each server.

## Actions

All faults are **post-dispatch**. A write or reset has already committed before
the delivery fault executes. Even `close_before_response` does not mean before
command execution. The pipeline is dispatch/reserve, encode, existing
`response_hook`, then fault action. A hook is still called when the fault will
drop or close. `truncate`, `corrupt_header`, `partial_send`, `delay` and
`close_after_response` operate on the hook's returned bytes, as does
`bad_end_code` with code 0. Exception: `bad_end_code` with code != 0 rebuilds the
abnormal response from the decoded request and discards the hook's bytes.

| Type | Parameters | Effect |
|---|---|---|
| `delay` | `seconds` | Wait, then send the complete response |
| `drop` | None | Send nothing; keep reading requests on the connection |
| `truncate` | `n` >= 0 | Send the first n bytes only; do not fix lengths or close |
| `bad_end_code` | `code`, integer 0..65535 | When code != 0, format as abnormal response with error info and no response data; code 0 keeps normal response |
| `close_before_response` | None | Close with no response bytes |
| `close_after_response` | None | Send the complete response, then close |
| `rst` | None | Set SO_LINGER to enabled/zero and close without shutdown |
| `silent_hold` | None | Send nothing and stop reading this connection until Server.stop() |
| `corrupt_header` | Optional `offset` (0..8, default 0), `xor` (1..255, default 1) | Flip selected bits in a header byte |
| `partial_send` | `chunks`: nonempty positive byte-count list; optional `pause` seconds (default 0) | Send those prefix chunks, then any remainder, pausing between nonempty chunks |

Header corruption is restricted to offsets shared by every response header.
A TCP response shorter than offset+1 bytes (for example a short `response_hook`
result) is sent unchanged and the connection stays open; the use is still consumed.
Truncating past the end preserves the response; n=0 sends nothing. For code != 0,
bad_end_code formats the response as an abnormal frame carrying error information per
SH-080008 (route, command, subcommand) with read data dropped and response length set
accordingly; code 0 leaves the normal response unchanged. Partial sends use sendall for each
chunk; oversized chunk sizes are clipped and no response bytes are omitted.
Chunk boundaries are send calls, not guaranteed TCP packet or recv boundaries.

Drop keeps a connection open subject to the ordinary socket idle timeout.
Silent hold differs: its worker waits until server shutdown, even if the client
abandons that socket, so use dedicated connections. Other clients remain
usable. Delay, hold and partial-send pauses all cancel promptly on Server.stop(),
which then closes clients and joins workers. The default idle timeout is None, so
ordinary idle sockets remain open until
EOF or server shutdown. Set `--idle-timeout` to bound idle clients.

## Pinned client observations and reset scenarios

The inspected 0.3.0 client reads only once per response (`recv(4096)`), does
not validate response subheaders, and reads status at fixed offsets. Binary
`int.from_bytes` on a missing status/value returns zero; ASCII conversion of a
missing status raises ValueError. Tests labelled **client-misbehaviour** use the
registered `client_misbehaviour` marker and establish:

- A one-byte binary response can make a word read appear successful with value
  zero, despite memory containing 0x1234. This is client behavior, not a valid
  MC response or successful server roundtrip.
- An equivalently truncated ASCII response raises a decode error.
- Flipping the response subheader's first byte is ignored by the real client
  on all four transports when the remaining status/data bytes are unchanged.

For reset, create `Server(initial_state='STOP', fault_plan=...)` with a once-only
step matching command `0x1006`. The slow tests use `silent_hold` (the silent
reset scenario) or `rst`, each on its own server and connection. They do not
patch client sleep or receive behavior. The client sets a 1 s receive timeout;
on failure it sleeps about 1 s and reconnects to the same address. Consequently,
hold takes about 2 s and RST about 1 s before reconnect. The new socket restores
the configured client timeout, echo works afterward, and reset_count is exactly
1: reconnect does not repeat the committed reset.

These four cases carry `pytest.mark.slow`. Reset uses the
same-connection success path when no fault is selected. Binary graceful EOF
may itself be interpreted as false success by this client; RST and silence are
used deliberately to exercise actual reconnect rather than claiming that any
close will do so.

## Limits

Faults, ordering, usage accounting and hold lifetime are explicit synthetic
policies, not new vendor-verified PLC behavior. TCP coalescing, scheduling and
the peer's precise EOF/reset exception are OS-dependent; RST tests verify the
actual platform linger setting (Windows ushort pair, POSIX int pair). No precise
packet timing or physical PLC behavior is asserted. Ranges, native stride, SD203 and
error semantics remain unverified; see [behavior](BEHAVIOR.md).

## UDP datagram response faults (opt-in)

UDP uses an independent UdpFaultPlan(steps), UdpFaultPlan.from_file(path)
(the same {"steps": [...]} file) or --udp-fault-plan FILE;
the TCP FaultPlan (which includes RST, close and partial_send) remains
rejected on all UDP listeners. The option defaults to None (no effect).
An empty UDP plan is valid. Example udp.json:

```json
{"steps":[{"match":{"command":"0x1401","nth":1,"peer":"127.0.0.1"},
           "action":{"type":"drop"}},
          {"times":2,"action":{"type":"delay","seconds":0.25}}]}
```

```text
virtual-plc --listen udp:5000 --udp-fault-plan udp.json
```

Python: from virtual_plc import Server, UdpFaultPlan; construct
Server(listeners=[('udp',0)], udp_fault_plan=UdpFaultPlan(steps)), or
UdpFaultPlan.from_file(path) to load a file.
An explicitly supplied UDP plan with TCP-only listeners raises ValueError
before binding. Use of a TCP FaultPlan with any UDP listener remains invalid.

Each step has required action and optional match/times (default times=1).
Allowed match fields: command (uint16 number or 0x-prefixed string),
nth (positive ordinal of eligible UDP responses, global across the plan,
not per peer/port), peer (numeric IPv4 or IPv6 source address, no port).
Under `--slmp-1e` (`slmp_1e=True`), `match.command` is the 1E command byte
(for example `0x03` for a 1E word batch write), not a 3E/4E command code.
A file may start with a UTF-8 BOM (Windows PowerShell 5.1 writes one); so may
`--fault-plan`, `--init` and `--ethernet-config` files.
All match fields must match; first eligible step wins, counts reserved
atomically. Malformed/oversized/empty UDP packets do not count.
Counters and reservations persist across stop/start with the same plan.
Plan configuration is deep copied; all unknown fields are rejected.

UDP actions (unknown types, missing or extra parameters raise ValueError
before binding; the CLI exits 2):

| Type | Parameters | Effect |
|---|---|---|
| `drop` | None | Discard the full UDP response datagram |
| `delay` | `seconds` | Wait, then send one complete response datagram |
| `duplicate` | None | Send the same response datagram twice; the request ran once |
| `truncate` | `n` >= 1 | Send one datagram holding only the first n bytes; lengths are not fixed |
| `corrupt_header` | Optional `offset` (0..8, default 0), `xor` (1..255, default 1) | Flip selected bits in one byte of the response datagram |

Every action occurs AFTER the original dispatch and after response_hook,
and operates on the hook's returned bytes; a write may have committed even
when the response is lost or damaged. Exactly one action applies per
response; actions do not combine. Server.stop() cancels pending delays, and
a stop between the two `duplicate` sends suppresses the second. Delay holds
just that UDP listener worker (outside the PLC request lock), not TCP or
other UDP listeners.

- `duplicate` re-sends identical bytes back to back from the same listener.
  The command, `response_hook` and the plan's `nth` each advance once. With
  `udp_metrics=True`, `sent` (or `send_errors`) counts each datagram, so one
  duplicated response adds 2.
- `truncate` with n at or past the response length sends the response
  unchanged. n=0 is rejected (use `drop`): truncate itself never produces an empty
  datagram. (A `response_hook` that returns `b""` is still sent as an empty
  datagram, twice under `duplicate`.)
- `corrupt_header` mirrors the TCP bounds (offsets shared by every 3E/4E
  response header). A datagram shorter than offset+1 bytes (for example a
  2-byte binary 1E reply, or a short hook result) is sent unchanged; the use
  is still consumed.

No retransmission, streaming, request-side fault, reorder, authentication
or timing guarantee is implied. Whether the two `duplicate` datagrams, or any
datagram, arrive and in which order is up to the network; loopback tests
only observe the send order. Reorder remains open #13 scope (see
[DESIGN](DESIGN.md)). No actual PLC or production network should be used.
