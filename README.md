# VirtualPLC

A local Mitsubishi MC protocol simulator for client tests. Sparse device
memory, CPU control and declarative faults use only the Python standard
library. Python 3.10 or newer is required.

## Safety

Use localhost only. There is no network authentication: passwords simulate
PLC locking. Ranges, CPU identities and some error meanings are synthetic or
unverified. Never connect to real equipment or production networks. Non-local
binds print a warning, not an access control. Localhost, ::1 and IPv4 loopback
addresses are recognized as local.

## Quickstart

```text
python -m pip install virtual_plc
virtual-plc --port 5000 --text-pad 0x20
```

From a checkout, use `python -m pip install -e .`. The equivalent module entry
point is `python -m virtual_plc`. Install pymcprotocol separately for clients:

```python
from pymcprotocol import Type3E

client = Type3E(plctype="Q")
client.setaccessopt(commtype="ascii")
client.connect("127.0.0.1", 5000)
try:
    client.batchwrite_wordunits("D0", [123, -45])
    assert client.batchread_wordunits("D0", 2) == [123, -45]
finally:
    client.close()
```

## CLI reference

This is the canonical option reference; `virtual-plc --help` is also available.
The stderr startup banner lists the bound address/profile/state, effective
idle timeout, text pad, dword order and fault-plan path. Ctrl+C, SIGTERM and
Windows SIGBREAK stop workers and exit 0. Windows SIGBREAK needs a shared
console; forced termination bypasses handlers and cannot save an exit snapshot.

| Option | Default | Meaning |
|---|---|---|
| `--host HOST` | `127.0.0.1` | IPv4/IPv6 bind address |
| `--port PORT` | `5000` | Integer 0..65535; 0 chooses an available port |
| `--profile NAME` | `Q` | Q, L, QnA, iQ-L, iQ-R |
| `--initial-state STATE` | `RUN` | RUN, STOP or PAUSE |
| `--password TEXT` | Disabled | Q-class: 4 ASCII chars; iQ-R: 6–32; not authentication |
| `--max-points N` | `4096` | Positive batch point limit |
| `--idle-timeout SECONDS` | None | Positive finite idle timeout; omitted means no timeout |
| `--ascii-dword-order MODE` | `swapped` | Low-word-first; `client` keeps high-word-first |
| `--text-pad BYTE` | `0x00` | Integer byte 0..255; `0x20` is space |
| `--fault-plan FILE` | None | Declarative fault JSON |
| `--init FILE` | None | Load memory JSON before listening |
| `--limit DEV:LO-HI` | Profile ceiling | Repeatable inclusive point limit; last per device wins |
| `--latch-range DEV:LO-HI` | All L points | Repeatable retained spans; replaces defaults |
| `--dump-on-exit FILE` | None | Save memory JSON after graceful shutdown |
| `-v`, `--verbose` | Off | Log request summaries and connection-close reasons |
| `--version` | — | Installed distribution version |
| `-h`, `--help` | — | Show usage |

Bad configuration exits 2 before bind. Bind failures print
`cannot listen on host:port: reason` and exit 1 without a traceback. Range
endpoints accept decimal or 0x notation, independent of client address syntax.
Request summaries exclude passwords and payload contents.

## Profiles, frames and encodings

All commands support every frame/encoding pair on each profile. Addressed
iQ-R packets have different descriptors/subcommands: client `plctype` and
server `--profile` must agree for iQ-R. Q-class names are wire-identical but
return different synthetic identities.

| Server recipe | Client plctype | Wire class |
|---|---|---|
| `virtual-plc --profile Q` | `Q` | Q-class |
| `virtual-plc --profile L` | `L` | Q-class |
| `virtual-plc --profile QnA` | `QnA` | Q-class |
| `virtual-plc --profile iQ-L` | `iQ-L` | Q-class |
| `virtual-plc --profile iQ-R` | `iQ-R` | iQ-R |

For an iQ-R server with 4E ASCII, use this client (binary uses
`setaccessopt(commtype="binary")`; 3E uses Type3E):

```python
from pymcprotocol import Type4E

client = Type4E(plctype="iQ-R")
client.setaccessopt(commtype="ascii")
client.connect("127.0.0.1", 5000)
try:
    client.randomwrite([], [], ["D0"], [0x12345678])
    assert client.randomread([], ["D0"]) == ([], [0x12345678])
finally:
    client.close()
```

This local recipe covers the complete profile x frame x wire product:

```python
from itertools import product
from pymcprotocol import Type3E, Type4E
from virtual_plc import Server

for profile in ("Q", "L", "QnA", "iQ-L", "iQ-R"):
    with Server(profile=profile) as server:
        for kind, wire in product((Type3E, Type4E), ("binary", "ascii")):
            client = kind(plctype=profile)
            client.setaccessopt(commtype=wire)
            client.connect(*server.address)
            try:
                client.batchwrite_wordunits("D0", [123])
                assert client.batchread_wordunits("D0", 1) == [123]
            finally:
                client.close()
```

| Commands | 3E binary | 3E ASCII | 4E binary | 4E ASCII | Profiles |
|---|---|---|---|---|---|
| Batch word/bit R/W (0401/1401) | Yes | Yes | Yes | Yes | All five |
| Random word/dword R/W (0403/1402) | Yes | Yes | Yes | Yes | All five |
| Random bit write (1402) | Yes | Yes | Yes | Yes | All five |
| Echo / CPU type (0619/0101) | Yes | Yes | Yes | Yes | All five |
| Run/stop/pause/latchclear/reset | Yes | Yes | Yes | Yes | All five |
| Unlock/lock (1630/1631) | Yes | Yes | Yes | Yes | All five; password configured |

Common devices include D/M/X/Y/B/W/R/ZR/SM/SD, L/F/V, SB/SW/DX/DY and
TS/TC/TN/CS/CC/CN/SS/SC/SN. iQ-R adds
LTS/LTC/LTN/LSTS/LSTC/LSTN/LCS/LCC/LCN/LZ/RD. LSTC is raw-only because the
client cannot name it; Z is unsupported. Bit commands require bit families.
Timers/counters store values without executing PLC logic. See
[behavior](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/BEHAVIOR.md).

## Memory seeding, snapshots and embedding

Save this as seed.json:

```json
{"D": {"100": [1, 2, 3]}, "M": {"0": [1, 0, 1]}}
```

```text
virtual-plc --init seed.json --limit D:0-102 --latch-range D:100-101 --dump-on-exit saved.json
```

Addresses are decimal JSON keys. Values are unsigned native points: bits 0/1,
words 0..65535, native dwords 0..4294967295. Dumps group contiguous stored
points, including explicit zeros and SD203, using the same schema. Loads
validate the complete snapshot before overlaying stored data.

```python
from virtual_plc import Server, Memory, FaultPlan, __version__

memory = Memory()
memory.load({"D": {"100": [1, 2, 3]}})
with Server(memory=memory, fault_plan=FaultPlan([])) as server:
    print(server.address, __version__)
    # Connect clients here. Context exit stops and joins workers.
snapshot = memory.dump()
```

Seed before start/context entry; dump after stop. Direct Memory operations
are not synchronized with wire requests, so never load/mutate/dump concurrently.
Live writes should use clients: each request validates/applies under one lock.
Server construction initializes SD203; CLI seeding runs afterward. Writing
SD203 changes that word but does not change CPU state.

A pytest fixture:

```python
import pytest
from virtual_plc import Server, Memory

@pytest.fixture
def plc():
    memory = Memory()
    memory.write_words("D", 0, [123])
    with Server(memory=memory) as server:
        yield server
```

## Response faults

Save faults.json and pass `--fault-plan faults.json`:

```json
{"steps": [{"match": {"command": "0x0619"}, "times": 1,
            "action": {"type": "delay", "seconds": 0.02}}]}
```

Faults run after execution and do not roll back writes. Delay/drop/truncate/
error/close/RST/hold/corruption/partial-send policies are described in
[FAULTS](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/FAULTS.md).

## Troubleshooting

- Large responses: pymcprotocol performs one `recv(4096)` in bytes. The server
  default is 4096 points, a different limit. Split requests or use a raw reader
  that follows response lengths.
- CPU names: default Q returns `"VirtualPLC-Q\x00\x00\x00\x00"`. The client
  removes spaces but retains NULs. Select `--text-pad 0x20` for `"VirtualPLC-Q"`.
  Non-UTF-8 fill such as 0xFF causes client decoding failure in either encoding.
- Reset: the client uses a 1 s receive timeout and sleeps about 1 s before
  reconnecting after receive/status failure. Normal reset requires STOP and
  keeps the socket open. Use raw sockets to observe swallowed reset errors.
- False success: missing header/length validation means truncated or gracefully
  closed binary responses can decode as status/value 0. This is not proof of
  success. Silence/RST can exercise actual reconnect behavior.
- Idle closes: no timeout is enabled by default; explicit positive idle timeouts
  close idle or incomplete connections, after which clients must reconnect.
- Monitoring timer: parsed but ignored. `setaccessopt(timer_sec=seconds)` sends
  seconds*4 and sets `soc_timeout=seconds+1`. Zero is ignored. `soc_timeout` is
  an attribute, not a setaccessopt keyword.
- Routes: responses echo routes but every route aliases the same memory/state.
  Client zero-valued route options are ignored even after nonzero values.
- Spelling/Unicode: client device names are case-sensitive; hex suffixes can
  be lowercase. Raw ASCII names are case-insensitive. Unicode echo can pass
  client validation but is rejected by the server without disconnecting.

## Known divergences from a real PLC

- CPU identities/ranges/SD203 encoding are synthetic. SD203 is a one-way state
  mirror. CPU-name fill defaults to NUL in binary and ASCII, and the pinned
  client retains those NULs; use `--text-pad 0x20` for the previous name.
  Physical PLC fill remains unverified.
- ASCII addresses use decimal text even for hex-base devices. Default dword
  order `swapped` puts the low word first; `client` keeps high-word-first
  interpretation. Roundtrips are symmetric but batch-word views differ.
  Physical PLC ASCII order is unverified.
- Locking is server-wide, survives disconnect, and gates only CPU control.
  It provides no authentication. Physical lock scope is unverified.
- Native iQ-R dword stride is one 32-bit point per address; word operations
  stream low/high halves. This stride and the LTN interpretation are unverified.
- Error codes await manual checks; C200/C201 may be swapped. Timers/counters
  store independent values without execution.

## Development and releases

```text
python -m pip install -e . -r requirements-dev.txt
python -m pytest -q
```

The dev extra installs pytest only. The test extra adds the compatible oracle
range in requirements-oracle.txt. Reproducible tests use the exact client pin
in requirements-dev.txt. Dependabot updates that file and pyproject; the
coverage guard rejects newly uncovered public methods/device constants.

The [wheel hash](https://github.com/greatgc-flow/VirtualPLC/blob/main/tests/oracle_pin.txt)
is checked when a matching-version wheel is retained under .venv/oracle. A
bumped oracle skips only the stale artifact-hash check; the full suite and
coverage guard still run. Oracle watch installs the latest client and changes
only that run's local version expectation, without committing the change.

```text
python -m pip install build twine
python -m build
python -m twine check dist/*
```

CI tests Windows/Linux on Python 3.10–3.13 and installs built wheels in clean
environments. Tags must match pyproject version; trusted publishing requires
the PyPI publisher and GitHub environment pypi to be configured.

See [DESIGN](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/DESIGN.md),
[BEHAVIOR](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/BEHAVIOR.md)
and [FAULTS](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/FAULTS.md).
Licensed under [MIT](https://github.com/greatgc-flow/VirtualPLC/blob/main/LICENSE).
