# VirtualPLC

VirtualPLC is a local Mitsubishi MC protocol PLC simulator for testing Python
clients. It provides sparse device memory, CPU control and optional response
faults, with compatibility tests against pymcprotocol 0.3.0. Runtime code uses
only the Python standard library. Python 3.10 or newer is required.

## SAFETY

Use this simulator on localhost only. It has **no network authentication**;
the optional password only simulates PLC locking. Device ranges and CPU
identities are synthetic, and error-code meanings remain unverified. Never
connect it to real equipment or production networks. Binding beyond 127.0.0.1
prints a warning and does not add access controls.

## Install and run

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m virtual_plc --host 127.0.0.1 --port 5000
```

After activating the environment, the installed entry point is equivalent:

```text
virtual-plc --profile iQ-R --initial-state STOP --max-points 128 --idle-timeout 30
virtual-plc --profile Q --password A1b2 --fault-plan faults.json
virtual-plc --ascii-dword-order client
```

The default profile is Q, CPU state RUN, batch limit 4096 points, idle timeout
None (no timeout), ASCII dword order `swapped`, with no password or faults. `--port 0` asks the OS for an
available port. The startup address/profile/state banner is written to stderr.
See `virtual-plc --help` for options and [fault plans](docs/FAULTS.md) for the
JSON schema. On POSIX, use `.venv/bin/python` instead of the Windows path.

Install the client separately to use this example against the local server:

```powershell
.\.venv\Scripts\python.exe -m pip install pymcprotocol==0.3.0
```

```python
import pymcprotocol

client = pymcprotocol.Type3E(plctype="Q")
client.setaccessopt(commtype="binary")
client.connect("127.0.0.1", 5000)
try:
    client.batchwrite_wordunits("D0", [123, -45])
    print(client.batchread_wordunits("D0", 2))
finally:
    client.close()
```

## Supported features

Each supported command uses the shared codec/handlers across the following
frame, encoding and profile combinations. See [behavior](docs/BEHAVIOR.md)
for device codes, layouts, limits and exclusions.

| Commands | 3E binary | 3E ASCII | 4E binary | 4E ASCII | Profiles |
|---|---|---|---|---|---|
| Batch word/bit read/write (0401/1401) | Yes | Yes | Yes | Yes | Q, L, QnA, iQ-L, iQ-R |
| Random word/dword read/write (0403/1402) | Yes | Yes | Yes | Yes | All five |
| Random bit write (1402) | Yes | Yes | Yes | Yes | All five |
| Echo / CPU type (0619/0101) | Yes | Yes | Yes | Yes | All five |
| Run/stop/pause/latchclear/reset (1001/1002/1003/1005/1006) | Yes | Yes | Yes | Yes | All five |
| Unlock/lock (1630/1631, configured password) | Yes | Yes | Yes | Yes | All five |

Common devices include D/M/X/Y/B/W/R/ZR/SM/SD, L/F/V, SB/SW/DX/DY and
TS/TC/TN/CS/CC/CN/SS/SC/SN. iQ-R adds LTS/LTC/LTN/LSTS/LSTC/LSTN/LCS/LCC/LCN/LZ/RD;
LSTC requires raw requests because the pinned client cannot name it. Bit
commands require bit devices. Timers/counters store independent values without
executing a PLC program. Fault plans apply to all transports and profiles.

## Known divergences from a real PLC

- ASCII addresses use the pinned client's decimal text, including hex-base devices.
- ASCII dword order is configurable with `--ascii-dword-order swapped|client`
  or `Server(ascii_dword_order=...)`. The default `swapped` sends the low-word
  half first; `client` preserves pymcprotocol's high-word-first interpretation.
  Write/read dword roundtrips work in both modes, but batch-word/direct memory
  views differ. Binary and plain words are unchanged. Suspected physical PLC
  low-word-first ASCII behavior remains unverified; see [examples](docs/BEHAVIOR.md#configurable-ascii-dword-word-order).
- Lock state is server-wide, survives disconnect, and gates only CPU control
  commands. It is not authentication. Vendor lock scope is unverified.
- The default batch limit is 4096 **points**. The client performs a single
  `recv(4096)` in **bytes**; large responses require a length-framed raw reader.
- Native iQ-R dword devices use one 32-bit point per address; word accesses
  stream low/high halves. This stride and the LTN interpretation are unverified.
- Error codes are simulator policy pending manual checks. C200/C201 meanings
  may be swapped. CPU identities, ranges and the SD203 state encoding are synthetic.
- Reset normally succeeds in STOP on the same open connection, clearing no
  memory. Fault injection can exercise the client's timeout/reconnect path.

## Testing

Plain `pip install -e ".[dev]"` installs pytest, but tests also require the
separate hash-pinned `pymcprotocol==0.3.0` oracle in `tests/oracle_pin.txt`:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pip download --no-deps --only-binary=:all: --require-hashes -r tests/oracle_pin.txt -d .venv/oracle
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .venv/oracle --require-hashes -r tests/oracle_pin.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Retain the downloaded wheel to enable its SHA256/source comparison in addition
to the installed-version check. Tests bind localhost on ephemeral ports. The
`unverified` marker labels protocol claims awaiting vendor checks;
`client_misbehaviour` labels pinned-client quirks; `slow` covers real reset
sleep/reconnect cases. Table-driven tests enumerate applicable command/device/
profile/transport combinations with explicit exclusions.

See [DESIGN](docs/DESIGN.md), [BEHAVIOR](docs/BEHAVIOR.md) and
[FAULTS](docs/FAULTS.md). Licensed under the [MIT License](LICENSE).
