# VirtualPLC

A local Mitsubishi MC protocol PLC simulator for client tests, with sparse
memory, CPU control and declarative faults. Python 3.10+, standard library only.

AI agents: run `virtual-plc guide` for a compact usage guide; use `--json` for data.

## 30-second quickstart

Install with `pip install virtual-plc`, then choose a recipe:

<!-- guide:run -->
```text
virtual-plc --port 5000 --text-pad 0x20
virtual-plc --profile iQ-R --port 5001 --initial-state STOP
virtual-plc --init seed.json --fault-plan faults.json --dump-on-exit saved.json
```
<!-- /guide:run -->

The third recipe needs the JSON files shown below. From a checkout, install
with `python -m pip install -e .`. `python -m virtual_plc` is the equivalent
entry point. For more startup details, run `virtual-plc guide run`.

Install the tested upstream client with `pip install pymcprotocol==0.3.0`.
This exact version is the repository's compatibility oracle; the separate
[client compatibility matrix](docs/CLIENT_COMPATIBILITY.md) distinguishes it
from our unreleased `greatgc-flow/pymcprotocol` fork and unverified real-PLC
behavior:

```python
from pymcprotocol import Type3E

client = Type3E(plctype="Q")
client.connect("127.0.0.1", 5000)
try:
    client.batchwrite_wordunits("D0", [123, -45])
    assert client.batchread_wordunits("D0", 2) == [123, -45]
finally:
    client.close()
```

For the iQ-R recipe (`virtual-plc --profile iQ-R --port 5001 --initial-state STOP`):

```python
from pymcprotocol import Type3E

client = Type3E(plctype="iQ-R")
try:
    client.connect("127.0.0.1", 5001)
    assert client.batchread_wordunits("D0", 1) == [0]
finally:
    client.close()
```

Local-only binding is enforced by default in the CLI **and Python API**.
Passwords simulate PLC locking; there is no network authentication. Never
connect to real equipment or production networks. If an isolated test network
really needs a non-loopback listener, explicitly opt in and set an idle timeout:

```text
virtual-plc --host 0.0.0.0 --allow-nonlocal --idle-timeout 30 --max-clients 16
```

The non-local override is **not authentication**; use only on a trusted,
isolated test network. `max_clients` defaults to 64; excess connections are
closed without allocating workers. Embedded servers use
`Server(host="0.0.0.0", allow_nonlocal=True, idle_timeout=30, max_clients=16)`.
A non-loopback host without explicit permission (or without an idle timeout
when permitted) raises a configuration error before listening.

## Multiple TCP/UDP listeners (unreleased source feature)

The legacy command `virtual-plc --port 5000` still opens **one TCP port**.
From an updated source checkout (this change is not included in published v0.5.0),
repeat `--listen` to expose several ports on **one shared virtual PLC**:

```powershell
virtual-plc --listen tcp:5000 --listen tcp:5001 --listen udp:5000
```

Each endpoint shares memory, CPU state, authentication-simulation lock and
the request serialization lock. Different transports can reuse the same
numeric port (TCP/5000 and UDP/5000). For a completely independent virtual
PLC with different memory, start another process. `--listen` replaces the
legacy `--port` option and may not be combined with it; `--host` applies
to every endpoint.

The same topology is available to embedded Python programs:

```python
from virtual_plc import Server

with Server(listeners=[("tcp", 0), ("udp", 0)]) as plc:
    print(plc.addresses)  # [("tcp", host, assigned_port), ("udp", host, assigned_port)]
    # Use a TCP client or an MC request datagram to either bound address.
```

For UDP, send **exactly one complete 3E/4E binary or ASCII MC request frame**
per datagram; replies are datagrams sent back to the source IP/port. Invalid,
truncated, concatenated or over-8192-byte datagrams are silently dropped.
UDP is connectionless: no TCP stream reassembly, session/idle timeout, or
retransmission is provided. Use application-level timeouts/retries and keep
UDP packets small enough to avoid IP fragmentation. Stock `pymcprotocol`
client connections are TCP; UDP clients must use a datagram-capable client.
The TCP-oriented `--fault-plan` is rejected if any UDP listener is enabled,
rather than pretending its close/RST/partial-send actions work for UDP.
`--max-clients` limits TCP sessions only.

Nonlocal network binds continue to require `--allow-nonlocal` and
`--idle-timeout`; that timeout does **not** add UDP session semantics.
There is no authentication or UDP rate limiting. Run on loopback or on
an isolated, trusted **test** network only; never connect to production PLCs.

## CLI reference

Run `virtual-plc guide options` for the option/default/meaning table generated
from the parser, or `virtual-plc --help`. For programs, use
`virtual-plc guide options --json`. Bad configuration exits 2 with a topic
hint; bind failures exit 1 without a traceback.

The stderr banner reports the bound address (including the assigned port for
`--port 0`), profile/state, idle timeout, text pad, dword order and fault plan.
Ctrl+C, SIGTERM and Windows SIGBREAK stop workers and save exit snapshots.
SIGBREAK needs a shared console; forced termination bypasses Python handlers.
`-v` logs request summaries and close reasons, excluding payloads/passwords.

| Guide topic | Contents |
|---|---|
| `virtual-plc guide run` | Installation, startup and shutdown |
| `virtual-plc guide options` | All flags and defaults, generated from argparse |
| `virtual-plc guide client` | Client reads/writes, control and addressing |
| `virtual-plc guide profiles` | Generated command/frame/wire/profile/device matrix |
| `virtual-plc guide embed` | Python API and pytest fixture |
| `virtual-plc guide faults` | Plan schema, actions and three examples |
| `virtual-plc guide memory` | Seeding, snapshots, ranges and devices |
| `virtual-plc guide troubleshoot` | Symptoms and fixes |
| `virtual-plc guide divergences` | Simulator policies and unverified PLC behavior |

Every topic accepts `--json`. Unknown topics list the choices and exit 2.

## Profiles, frames and encodings

Commands support 3E/4E and binary/ASCII on all profiles. Q, L, QnA and iQ-L
share a wire class; iQ-R uses different descriptors/subcommands. Client
`plctype` and server `--profile` must agree for iQ-R. Inspect
`virtual-plc guide profiles --json` for the current matrix and device kinds.

This local recipe covers every profile/frame/wire combination:

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

## Memory seeding, snapshots and embedding

Save seed.json (decimal address keys, unsigned native point values):

```json
{"D": {"100": [1, 2, 3]}, "M": {"0": [1, 0, 1]}}
```

`--init` loads before listening; `--dump-on-exit` saves the same schema after
graceful shutdown. The snapshot is written to a same-directory temporary file,
flushed and atomically replaced on successful completion. A failed write leaves
an existing snapshot untouched; abrupt process or OS termination may still
prevent saving the latest state. Dumps preserve explicit zeros and include
SD203. Loads
validate the complete snapshot before overlaying data. See
`virtual-plc guide memory` for bounds, retention and device names.

Latch ranges are cleared by latchclear and preserved by remote_run(clear_mode=1).
SM and SD are never cleared; latchclear requires STOP.

```python
from virtual_plc import Server, Memory, FaultPlan, __version__

memory = Memory()
memory.load({"D": {"100": [1, 2, 3]}})
with Server(memory=memory, fault_plan=FaultPlan([])) as server:
    print(server.address, __version__)
    # Connect clients here. Context exit stops and joins workers.
snapshot = memory.dump()
```

Seed before start/context entry; dump after stop. Direct Memory calls are not
synchronized with requests. Use clients for live writes. Server construction
initializes SD203; CLI seeding runs afterward. Writing SD203 changes the word
without changing CPU state. For a pytest fixture, run `virtual-plc guide embed`.

## Response faults

Save faults.json and pass `--fault-plan faults.json`:

```json
{"steps": [{"match": {"command": "0x0619"}, "times": 1,
            "action": {"type": "delay", "seconds": 0.02}}]}
```

Faults run after execution and do not roll back writes. Run
`virtual-plc guide faults` for the schema and examples; see
[FAULTS](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/FAULTS.md)
for delivery semantics.

## Troubleshooting

- Large reads: pinned upstream pymcprotocol 0.3.0 calls `recv(4096)` once. Split batches; the server's
  point limit is separate. A raw reader can follow response lengths.
- CPU names: default Q returns `"VirtualPLC-Q\x00\x00\x00\x00"`. The client
  retains NULs; `--text-pad 0x20` returns `"VirtualPLC-Q"`. Non-UTF-8 fill
  such as 0xFF causes client decoding failure.
- Reset requires STOP. On receive/status failure, the client waits about 1 s
  and reconnects. A normal reset keeps the connection open.
- With pinned upstream pymcprotocol 0.3.0, truncated or closed binary replies
  can look like status/value 0 because that client does not validate headers/lengths. This is not proof of success.
- Idle timeout is disabled by default; explicit timeouts close idle or
  incomplete connections. Reconnect afterward.

More fixes: `virtual-plc guide troubleshoot`. Protocol details:
[BEHAVIOR](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/BEHAVIOR.md).

## Known divergences from a real PLC

- CPU identities, ranges and SD203 state encoding are synthetic; SD203 mirrors
  state in one direction. CPU names default to NUL fill on both encodings;
  the client retains NULs. Physical fill remains unverified.
- ASCII addresses default to decimal-text compatibility, including hex-base
  devices; opt into manual hexadecimal addressing with `--ascii-numbering manual`.
  Dword order
  defaults to low-word-first (`swapped`); `client` selects high-word-first.
  Physical order is unverified; roundtrips remain symmetric.
- Locking is server-wide, survives disconnect and gates only CPU control.
  It provides no authentication. Native iQ-R dword stride is one 32-bit point
  per address; this and physical lock/reset policies are unverified.
- Timers/counters store values without execution. Monitoring timers are
  parsed/ignored; routes alias one memory/state. Error meanings await checks.

Run `virtual-plc guide divergences` for the compact list of simulator policies.

## Development and releases

```text
python -m pip install -e . -r requirements-dev.txt
python -m pytest -q
```

The dev extra installs pytest only. The test extra adds the compatible oracle
range declared in pyproject.toml. requirements-dev.txt is the only exact client
pin. Dependabot updates that file and pyproject; the coverage guard rejects
newly uncovered public methods, device constants and lookup-only names.

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
