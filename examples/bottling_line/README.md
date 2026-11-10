# Sample project: a bottling line, tested without a PLC

A step-by-step sample for **VirtualPLC** (a local Mitsubishi MC-protocol PLC
simulator) and **pymcprotocol** (the Python MC-protocol client). In five small
steps you go from "hello PLC" to a tested, fault-tolerant client — with no
hardware.

```text
  your code (the thing you ship)                  the simulated world
 ┌────────────────────────────┐   MC protocol   ┌───────────────────────────────┐
 │ LineController             │ ─────TCP──────► │ VirtualPLC  (virtual_plc)     │
 │  line_client.py            │   pymcprotocol  │  memory, CPU state, end codes │
 │  (retry, error handling)   │                 │  + optional fault plan        │
 └────────────────────────────┘                 └──────────────▲────────────────┘
                                                               │ also a client
                                                ┌──────────────┴────────────────┐
                                                │ PlantSimulator (plant.py)     │
                                                │  plays the PLC's ladder logic │
                                                └───────────────────────────────┘
```

> VirtualPLC simulates the PLC's **protocol and memory**, not a ladder program.
> `plant.py` shows the standard trick for a living line: a second client that
> polls request bits and writes status back, like the PLC program would.

**Safety:** loopback only. Never point this at a real PLC or a production
network — the sample writes to device memory.

## Setup (2 minutes)

```text
python -m pip install virtual-plc pymcprotocol==0.3.0 pytest
cd examples/bottling_line        # inside a VirtualPLC checkout, or copy this folder
```

Python 3.10+. Every script runs from this folder (they import each other).

## PLC primer (60 seconds)

- **Bit device** (`M`, `X`, `Y`): one on/off value, like a relay coil. **Word
  device** (`D`, `W`): a 16-bit number. `M10` is bit 10 of the `M` area;
  `D100` is word 100 of the `D` area.
- PLC words are integers only, so a temperature is stored scaled: `253` means
  25.3 °C (fixed point, factor 10). Agree on the scale once, in `plc_map.py`.
- MC protocol is request/reply over TCP: the client sends a *command* (for
  example `0x0401` = batch read) and the PLC answers with an *end code*. End
  code `0x0000` is success; anything else is the PLC saying "no".
- A real PLC runs its program in a repeating scan; clients exchange data with
  it only by reading and writing devices.
- Give every device exactly one writer. Two clients doing read-modify-write on
  the same device will eventually overwrite each other (the sample's plant is
  the only writer of `D101`/`D102`/`M10`/`M11`).

## The device map

Defined once in [`plc_map.py`](plc_map.py), mirrored in [`seed.json`](seed.json).

| Device | Direction | Meaning |
| --- | --- | --- |
| `M0` / `M1` | HMI → PLC | start / stop request (one-shot) |
| `M10` / `M11` | PLC → HMI | line running / alarm (latched) |
| `D100` | HMI → PLC | target bottle count |
| `D101` | PLC → HMI | bottles filled so far |
| `D102` | PLC → HMI | tank temperature, 0.1 °C units (`253` = 25.3 °C) |

## Step by step

| Step | File | You learn |
| --- | --- | --- |
| 1 | [`01_hello.py`](01_hello.py) | `Server(port=0)` + `Type3E`: write/read words and bits |
| 2 | [`02_line_demo.py`](02_line_demo.py) | a whole system: app + PLC + simulated ladder logic |
| 3 | [`03_fault_injection.py`](03_fault_injection.py) | `FaultPlan`: slow, lost, refused, disconnected |
| 4 | [`04_external_server.py`](04_external_server.py) | the `virtual-plc` CLI as a separate process |
| 5 | [`test_line_client.py`](test_line_client.py) | pytest fixtures — copy these into your project |

### Step 1 — hello PLC

```text
python 01_hello.py
```

```text
virtual PLC listening on 127.0.0.1:54225      (port differs every run)
D100..D101 = [123, -45]
M0..M2     = [1, 0, 1]
CPU type   = 'VirtualPLC-Q' (model code ffff)
```

Note the `-45`: pymcprotocol shows words as signed, the PLC stores them as
unsigned (`65491`). Same bits, different view.

### Step 2 — a living line

```text
python 02_line_demo.py
```

```text
idle                   running=False alarm=False count= 0/0  temp=25.0 C
run of 10 finished     running=False alarm=False count=10/10 temp=30.0 C
after overheating      running=False alarm=True  count= 1/20 temp=80.0 C
start refused (alarm)  running=False alarm=True  count= 1/5  temp=77.0 C
```

(The temperature in the last line varies by a few steps from run to run.)

### Step 3 — break it on purpose

```text
python 03_fault_injection.py
```

```text
slow PLC (delay 0.1 s)             -> OK count=3 temp=25.3 (reconnects=0)
lost reply (drop)                  -> OK count=3 temp=25.3 (reconnects=1)
connection closed (close_before_response) -> OK count=3 temp=25.3 (reconnects=1)
PLC error (end code 0xC051)        -> LineError end_code=0xC051 (not retried)
unsupported command (0xC059)       -> LineError end_code=0xC059 (not retried)
lost START reply (drop)            -> LineUnreachable: outcome unknown, not re-sent (reconnects=0)
```

Three kinds of failure, three policies — the core lesson of the sample:

| Symptom | Meaning | Policy in `line_client.py` |
| --- | --- | --- |
| socket timeout / reset on a read or absolute write | the PLC said **nothing** | close, reconnect, retry |
| socket timeout / reset on a one-shot request bit (`M0`/`M1`) | **unknown**: the PLC may have acted | never re-send; raise `LineUnreachable("... outcome unknown")`, caller checks `status()` |
| `MCProtocolError` / end code | the PLC said **no** | raise `LineError`, never retry |

Fault plans only damage the *reply*; the request has already run. The full
action list is in `virtual-plc guide faults`.

### Step 4 — simulator as a separate process

Terminal A:

```text
virtual-plc --port 5000 --init seed.json
```

Terminal B:

```text
python 04_external_server.py 5000
```

```text
LineStatus(running=False, alarm=False, target=0, count=0, temperature_c=25.0)
reconnects: 0
```

Restart terminal A with
`virtual-plc --port 5000 --init seed.json --fault-plan faults.json`
and rerun terminal B twice:

```text
PLC refused the request: PLC returned end code 0xC059      (run 1, exit code 2)
LineStatus(running=False, ...)  /  reconnects: 0           (run 2, exit code 0)
```

Run 1: the first read is dropped, the client reconnects and retries, and the
retry meets the second fault (end code `0xC059`), which is a "no" and is not
retried. Run 2 succeeds because each fault step is spent after one use.

### Step 5 — test it

```text
python -m pytest -q
```

Nine tests run in about two seconds: decoding, request bits, input validation,
a full run with the simulated ladder program, the alarm latch, and all failure
policies (including "never re-send a one-shot request bit").
The fixtures to copy:

```python
@pytest.fixture
def plc(memory):
    with Server(memory=memory, port=0) as server:   # fresh PLC, free port
        yield server                                # stops on exit

with LineController(*plc.address) as hmi: ...       # plc.address == (host, port)
```

## Adapting this to your project

1. Replace `plc_map.py` with your PLC's device list; update `seed.json`.
2. Keep `LineController`'s two-policy `_call`; change the operations.
3. Match the profile: `Type3E(plctype="iQ-R")` needs `virtual-plc --profile iQ-R`
   (or `Server(profile="iQ-R")`); client and simulator must agree.
4. Replace `plant.py` with whatever your PLC program does, or drop it and seed
   the state each test needs with `Memory.write_words(...)` before starting.
5. Never touch `Memory` while a server is running; go through a client.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `ModuleNotFoundError: plc_map` | run from this folder, not the repo root |
| `cannot listen` / port busy | pick another `--port`, or `--port 0` and read the banner |
| iQ-R errors | client `plctype` and server `--profile` must both be `iQ-R` |
| `UnsupportedComandError` | pymcprotocol's name for end code `0xC059` |
| big reads fail | pymcprotocol reads one 4096-byte chunk; keep batches under ~1000 words |

More: `virtual-plc guide` (compact usage), [README](../../README.md),
[behaviour](../../docs/BEHAVIOR.md), [client compatibility](../../docs/CLIENT_COMPATIBILITY.md).
