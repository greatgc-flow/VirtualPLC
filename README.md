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

## MELSEC iQ-F SLMP 1E mode (opt-in; source checkout)

For client testing of the **separate 1E** request/response format, use:

```powershell
# One synthetic PLC, two explicit listener protocols:
virtual-plc --slmp-1e --listen tcp:5000 --listen udp:5000

# Python API:
# with Server(slmp_1e=True, listeners=[("tcp", 0), ("udp", 0)]) as plc: ...
```

For the vendor-documented physical RUN/STOP switch edge case, an optional
**static simulator switch** can be selected:

```powershell
virtual-plc --slmp-1e --slmp-1e-run-switch STOP --initial-state STOP --port 5000
# Python: Server(slmp_1e=True, slmp_1e_run_switch="STOP", initial_state="STOP")
```

An authorized 13H remote RUN still acknowledges success but **CPU stays STOP**
when this optional selector is STOP. The original STOP owner is released by
that successful RUN, after which another TCP client may control the PLC.
This explicitly models Mitsubishi JY997D56001-K printed p.132; the static
switch is not a full CPU hardware model or physical-device verification.
Omit the option to retain the original default RUN transition. STOP requires
`--initial-state STOP` to prevent contradictory simulator initial state.

This opt-in mode is **1E-only** on all of that process's listeners.
It supports batch bit/word read/write `00H`–`03H`, random writes `04H` (up to 80 individual bits) and `05H` (up to 10 word or aligned bit-group items), remote `13H` RUN / `14H` STOP, and diagnostics `15H` / `16H` in binary and ASCII.
Batch responses have the normal 1E subheader/status, but diagnostics have
**different** reply layouts: `15H` returns only `F3H` (ASCII: `F3`),
and `16H` returns the original length plus data, without a batch status.
Loopback length is 1–254 bytes. Batch errors use special `5BH`
extended errors. In this bounded initial slice, supported simulated
devices are M/X/Y (bits) and D (words); bit devices also support aligned
16-point word access. Random writes validate the full list before a single atomic storage commit. TCP remote STOP is owned by the requesting connection: only that same live connection can RUN until explicit local `Server.reset_1e_remote_control()`. A disconnect **does not** release ownership (CPU remains STOP); UDP remote RUN/STOP receives a simulated `C05F` unsupported-policy error because it has no verifiable TCP session. The local reset releases ownership but deliberately keeps the simulator STOP. These are **simulator safety policies**, not verified FX5 error codes or physical reset timing. Invalid frames are closed/dropped rather than interpreted as 3E. Legacy default 3E/4E behavior is unchanged.

To inspect whether a remote STOP is still owned or orphaned without changing
CPU state, embedded users can call
`Server.get_1e_remote_control_status()`. It returns a local read-only
snapshot with `cpu_state`, `owned`, `owner_connected`, `orphaned` and
`owner_connection_id`. A disconnected owner is **not** released; only the
original connected client can RUN, or the local operator can use
`reset_1e_remote_control()`, which clears ownership while leaving STOP.
Connection IDs are local monotonic numbers, not authentication; socket-close
detection is asynchronous. The CLI has no network-accessible recovery command.

**Not FX5-ENET hardware parity:** 1E mode uses synthetic Q memory,
cannot be combined with `--ethernet-model` or a 3E fault plan, does not
implement full vendor device/firmware behavior or socket timers, and does not open system/MELSOFT ports. [1E packet contract and unsupported
features](docs/research/FX5_SLMP_FRAME_SCOPE_20261031.md) ·
[1E implementation issue #22](https://github.com/greatgc-flow/VirtualPLC/issues/22).
Each independent PLC still runs as its own OS process; TCP/UDP
listeners of one process share its CPU/memory.

## Offline physical-oracle preparation (source checkout)

For separately and manually captured read-only 1E 15H model and 16H loopback
responses, use `python -m virtual_plc.oracle plan`, `template`, and
`compare FILE --report REPORT.json`. This offline utility **never contacts
a PLC** and never certifies real hardware. See [offline oracle procedure](docs/PHYSICAL_ORACLE.md).

## FX5 vendor SLMP port preflight (offline, reference only)

This source checkout includes `inspect_reference_slmp_port(model, port)`
for `fx5_cpu_builtin` and `fx5_enet`. It distinguishes vendor
**recommended**, **permitted but not recommended**, **5549–5569 system
reserved**, and **port 0 simulator-only**. It never binds sockets or
enables an FX5 hardware profile. The CPU's 8 aggregate Ethernet connections
must not be confused with 16 simple-CPU-communication targets on FX5U/UC.
See [FX5 connection/port scope](docs/research/FX5_SLMP_PORT_SCOPE_20261031.md).

## GX Works2/3 model-specific Ethernet settings (opt-in)

GX Works2/3 is an editor, **not** the hardware identity. This source checkout
supports `qj71e71` (Q / GX Works2), `lj71e71` (L / GX Works2),
and `rj71en71` (iQ-R / GX Works3).
Factory defaults, validated JSON overrides and a nonbinding effective-settings
inspection are in the [Ethernet settings guide](docs/ETHERNET_MODEL_SETTINGS.md).
The [official-manual research matrix](docs/research/GXWORKS_ETHERNET_PARAMETERS_20261031.md)
documents model boundaries and unresolved physical fidelity.
See the [RnCPU/FX5 hardware gap matrix](docs/research/ETHERNET_HARDWARE_NEXT_20261031.md)
before using an unsupported model's defaults. The existing
`guide ethernet --json` exposes FX5 built-in, FX5-ENET and RnCPU built-in as
**reference-only, not runnable** hardware; unknown timer defaults remain unknown.

```powershell
# Inspect defaults and configurable ranges without listening:
virtual-plc --ethernet-model qj71e71 --show-effective-ethernet
virtual-plc --ethernet-model lj71e71 --show-effective-ethernet
virtual-plc --ethernet-model rj71en71 --show-effective-ethernet

# Load optional JSON changes, share PLC state across explicit TCP/UDP ports:
virtual-plc --ethernet-model qj71e71 --ethernet-config ethernet.json --listen tcp:5000 --listen udp:5000
virtual-plc guide ethernet --json
```

The hardware model automatically selects its matching wire profile in the CLI;
explicitly conflicting `--profile` values are errors. JSON overrides preserve
whether each key was explicitly specified, even if equal to its factory value.
Selecting a model simulates its binary/ASCII data-code setting and RUN-time
MC write permission. **Only those settings change runtime behavior**; module
TCP/IP retransmit, response monitoring and alive timers are explicitly marked
`reference_only`, not substituted for `--idle-timeout`. Legacy `--port 5000`
and Q behavior remain unchanged without a model selection. Independent PLCs
run in **separate OS processes**; all listeners within one process share the
same PLC state. The feature is currently in source; published v0.5.0 predates it.

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
  devices; opt into hexadecimal per-device addressing with `--ascii-numbering manual`
  or FX5-style **X/Y octal** with `--ascii-numbering fx5-octal` (D decimal,
  W/B hexadecimal; see [FX5 1E/3E scope](docs/research/FX5_SLMP_FRAME_SCOPE_20261031.md)).
  This address option does **not** enable an FX5-ENET hardware profile or SLMP
  1E packets; generic simulator 4E support is not an FX5 hardware claim.
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
