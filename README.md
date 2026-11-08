# VirtualPLC

A local Mitsubishi MC protocol PLC simulator for client tests, with sparse
memory, CPU control and declarative faults. Python 3.10+, standard library only.

AI agents: run `virtual-plc guide` for a compact usage guide; use `--json` for data.

1E error codes and `OutOfRange`: [BEHAVIOR](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/BEHAVIOR.md#slmp-1e-transport-opt-in) and [memory API semantics](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/BEHAVIOR.md#lifecycle-snapshots-timers-and-routes); `compare_observations` / `observation_template`: [PHYSICAL_ORACLE](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/PHYSICAL_ORACLE.md).

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

For local UDP diagnostics, see [UDP observability](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/BEHAVIOR.md#udp-observability-opt-in).

## UDP response faults (optional, unreleased)

UDP listeners support the independent drop/delay plan; see [FAULTS](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/FAULTS.md#udp-datagram-response-faults-opt-in).

## Standalone UDP client example (source checkout)

The pinned `pymcprotocol==0.3.0` client uses TCP. For UDP, use the
stdlib-only, **IPv4 loopback-only** [3E binary D0 reader](examples/udp_read_d0.py).
It sends exactly one complete request datagram and validates the sender,
frame header, length, status and word size; malformed replies fail closed.
No retry, authentication, physical PLC compatibility or nonlocal target.

```text
python -m virtual_plc --listen udp:5000
python examples/udp_read_d0.py 5000
```

Seed D0 via an `--init` JSON file if you want a nonzero response.
See [client compatibility](docs/CLIENT_COMPATIBILITY.md) for the distinction
between this raw UDP example and the tested TCP-only pinned client.

## CLI reference

Run `virtual-plc guide options` for the generated flag/default table, or `virtual-plc --help`; see `virtual-plc guide run` for quick-start flags.

| Guide topic | Contents |
|---|---|
| `virtual-plc guide run` | Installation, startup and shutdown |
| `virtual-plc guide options` | All flags and defaults, generated from argparse |
| `virtual-plc guide client` | Client reads/writes, control and addressing |
| `virtual-plc guide profiles` | Generated command/frame/wire/profile/device matrix |
| `virtual-plc guide ethernet` | Hardware model settings, overrides and offline reference JSON |
| `virtual-plc guide embed` | Python API and pytest fixture |
| `virtual-plc guide faults` | Plan schema, actions and examples |
| `virtual-plc guide memory` | Seeding, snapshots, ranges and devices |
| `virtual-plc guide troubleshoot` | Symptoms and fixes |
| `virtual-plc guide divergences` | Simulator policies and unverified PLC behavior |

Every topic accepts `--json`.

## MELSEC iQ-F SLMP 1E mode (opt-in; source checkout)

Enable with `--slmp-1e`; this selects a separate 1E-only parser on synthetic Q memory. See [BEHAVIOR](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/BEHAVIOR.md#slmp-1e-transport-opt-in) for command bounds, diagnostics, remote-control policy and error codes; this is not FX5 hardware parity.

## Offline physical-oracle preparation (source checkout)

For separately and manually captured read-only 1E 15H model and 16H loopback
responses, use `python -m virtual_plc.oracle plan`, `template`, and
`compare FILE --report REPORT.json`. This offline utility **never contacts
a PLC** and never certifies real hardware. See [offline oracle procedure](docs/PHYSICAL_ORACLE.md).

## FX5 vendor SLMP port preflight (offline reference)

These offline helpers exist only in a source checkout; published v0.5.0 predates them.
Offline helper `inspect_reference_slmp_port(model, port)` checks vendor recommended and reserved port ranges; see `virtual-plc guide ethernet --json` and [FX5 port scope](docs/research/FX5_SLMP_PORT_SCOPE_20261031.md).

## RnCPU built-in service connection settings (offline reference)

Service-specific connection rules for RnCPU built-in Ethernet (auto-open UDP vs per-GOT TCP); see `virtual-plc guide ethernet --json` and [RnCPU service connection scope](docs/research/RNCPU_BUILTIN_SERVICE_CONNECTIONS_20261101.md).

## FX5 CPU firmware compatibility (offline reference)

Offline helper `inspect_reference_fx5_simple_cpu_communication(model, firmware)` checks model/firmware support gates; see `virtual-plc guide ethernet --json` and [FX5 firmware matrix](docs/research/FX5_CPU_FIRMWARE_SIMPLE_COMM_20261101.md).

## FX5-ENET existence-check settings (offline reference)

Offline helper `inspect_reference_fx5_enet_alive_timers()` validates module alive-check timer ranges; see `virtual-plc guide ethernet --json` and [FX5-ENET source matrix](docs/research/FX5_ENET_ALIVE_REFERENCE_20261101.md).

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

Minimal example:

```json
{"steps": [{"match": {"command": "0x0619"}, "action": {"type": "delay", "seconds": 0.02}}]}
```

See [FAULTS](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/FAULTS.md) for the contract.

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

`virtual-plc guide divergences` (`DIVERGENCES` in `virtual_plc/guide.py`) is the canonical list of simulator policies and unverified PLC behavior; see [BEHAVIOR](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/BEHAVIOR.md) for wire protocol details.

## Repository safeguards and verified handoff

For the **unreleased source repository**, use the
[branch/release gate checklist](docs/governance/BRANCH_RELEASE_GATES_20261102.md)
before configuring `main` protection or creating a `v*` tag.
The checked-in [latest handoff prompt](docs/handoff/START_NEW_CHAT_VIRTUALPLC_20261102.md)
records technical state and CI evidence; fetch remote main first.
An active GitHub ruleset cannot be inferred from a successful CI run.

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

See [DESIGN](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/DESIGN.md), [BEHAVIOR](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/BEHAVIOR.md) and [FAULTS](https://github.com/greatgc-flow/VirtualPLC/blob/main/docs/FAULTS.md).
Licensed under [MIT](https://github.com/greatgc-flow/VirtualPLC/blob/main/LICENSE).

### RnCPU built-in Ethernet remote RUN/STOP setting check (offline reference)

These offline helpers exist only in a source checkout; published v0.5.0 predates them.
Offline helper `inspect_reference_rncpu_remote_opening()` checks vendor opening settings; see `virtual-plc guide ethernet --json` and [RnCPU opening guide](docs/research/RNCPU_REMOTE_OPENING_SAFETY_20261101.md).

### R04CPU built-in Ethernet A038H offline timer preflight

Offline helper `inspect_reference_rncpu_data_timers()` validates R04CPU timer references; see `virtual-plc guide ethernet --json` and [R04CPU timer guide](docs/research/RNCPU_R04CPU_A038H_DATA_TIMER_REFERENCE_20261101.md).

### R04CPU built-in Ethernet external-device settings (offline)

Offline helper `inspect_reference_rncpu_external_device()` checks user slot and port ranges; see `virtual-plc guide ethernet --json` and [R04CPU port matrix](docs/research/RNCPU_R04CPU_EXTERNAL_DEVICE_PORTS_20261101.md).

### R04CPU external-device multi-entry offline review

Offline helper `inspect_reference_rncpu_external_device_batch()` lints multiple configuration rows; see `virtual-plc guide ethernet --json` and [R04CPU batch lint guide](docs/research/RNCPU_R04CPU_BATCH_LINT_20261101.md).
