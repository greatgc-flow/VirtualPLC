# Declarative response faults

`Server(fault_plan=None)` keeps the ordinary response path: no matching,
fault waits, alternate sender, or connection/request counting. Opt in with
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
must be finite and nonnegative; byte counts and field values must be integers.

## Matching and ordering

`FaultPlan.select(command, *, nth, connection)` reserves and returns one copied
action dictionary, or None. It is called after dispatch under the server's
request lock. Selection and usage decrement are atomic under a plan lock.
No locks remain held during fault waits or network transmission.

- `match.command` is a uint16 integer or numeric string (`"0x0619"` is convenient
  in JSON). It matches the original MC command, including commands that return
  a normal error response.
- `match.connection` is the 1-based accept ordinal for this Server.
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
drop or close; transformations operate on its returned response bytes.

| Type | Parameters | Effect |
|---|---|---|
| `delay` | `seconds` | Wait, then send the complete response |
| `drop` | None | Send nothing; keep reading requests on the connection |
| `truncate` | `n` >= 0 | Send the first n bytes only; do not fix lengths or close |
| `bad_end_code` | `code`, integer 0..65535 | Replace only the end-code field, in the correct encoding/offset |
| `close_before_response` | None | Close with no response bytes |
| `close_after_response` | None | Send the complete response, then close |
| `rst` | None | Set SO_LINGER to enabled/zero and close without shutdown |
| `silent_hold` | None | Send nothing and stop reading this connection until Server.stop() |
| `corrupt_header` | Optional `offset` (0..8, default 0), `xor` (1..255, default 1) | Flip selected bits in a header byte |
| `partial_send` | `chunks`: nonempty positive byte-count list; optional `pause` seconds (default 0) | Send those prefix chunks, then any remainder, pausing between nonempty chunks |

Header corruption is restricted to offsets shared by every response header.
Truncating past the end preserves the response; n=0 sends nothing. Error-code
replacement leaves the declared length and body intact, intentionally allowing
an error code alongside success-shaped data. Partial sends use sendall for each
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
