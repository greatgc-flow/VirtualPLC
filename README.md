# VirtualPLC

Virtual Mitsubishi MC protocol PLC for local testing. Not for industrial use.

**Status:** M7 complete on `v2/m0`: Q/L/QnA/iQ-L/iQ-R profiles with 3E/4E binary and ASCII batch and random
word/bit/dword access, echo, CPU type, and independent timer/counter storage.
CPU run/stop/pause, selective latch clearing, reset and server-wide locking follow
the agreed simulator policy. Optional declarative response faults are available through
`Server(fault_plan=...)` and CLI `--fault-plan FILE`. The full suite passes 2786 tests using the pinned client. Device capacities
remain synthetic and error codes await manual verification.
See [DESIGN](docs/DESIGN.md), [M2 notes](docs/M2.md), [M3/M4 notes](docs/M3_M4.md), [M5 notes](docs/M5.md), [M6 notes](docs/M6.md), [M7 schema](docs/M7.md), and
[migration notes](docs/MIGRATION.md).

With Python 3.10 or newer and PyPI access, run from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pip download --no-deps --only-binary=:all: --require-hashes -r tests/oracle_pin.txt -d .venv/oracle
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .venv/oracle --require-hashes -r tests/oracle_pin.txt
.\.venv\Scripts\python.exe -m pytest -q
```

On POSIX, use `.venv/bin/python` for the commands after environment creation.
Runtime dependencies are stdlib only; pytest is the development extra, and
`pymcprotocol==0.3.0` is a separate test oracle. The pin test checks the installed
version and, when the downloaded wheel is retained, its SHA256 and installed
package source. Missing oracle installations fail the test.

`tests/tables.py` contains immutable profiles, device codes/bases, commands,
and explicit reasons for excluding combinations from the Q transport matrix.
The migrated JSONL holds M1 scenario inputs. Tests start local servers on port 0;
timers/counters store values without executing a PLC program.
